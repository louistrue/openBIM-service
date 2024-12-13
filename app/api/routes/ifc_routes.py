from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
import tempfile
import os
import logging
import json
from typing import AsyncGenerator
import ifcopenshell
from app.services.ifc.properties import get_common_properties, get_object_type
from app.services.ifc.quantities import (
    get_volume_from_properties,
    get_area_from_properties,
    get_dimensions_from_properties
)
from app.services.lca.materials import MaterialService
from app.services.ifc.splitter import StoreySpiltterService
from app.services.ifc.units import get_project_units, convert_unit_value, LengthUnit
import zipfile
import shutil

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/process")
async def process_ifc(file: UploadFile = File(...)) -> StreamingResponse:
    """Process an IFC file and stream the results"""
    if not file.filename.endswith('.ifc'):
        raise HTTPException(status_code=400, detail="Invalid file type. Must be an IFC file.")
        
    # Save uploaded file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.ifc') as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_path = temp_file.name

    try:
        ifc_file = ifcopenshell.open(temp_path)
        units = get_project_units(ifc_file)
        length_unit = units.get("LENGTHUNIT", {"type": "LENGTHUNIT", "name": "METER"})
        material_service = MaterialService(ifc_file)

        async def generate_response():
            try:
                # Get total elements for progress tracking 
                building_elements = ifc_file.by_type("IfcBuildingElement")
                total_elements = len(building_elements)
                
                # Initial progress
                yield json.dumps({
                    "status": "processing",
                    "progress": 0,
                    "processed": 0,
                    "total": total_elements
                }) + "\n"
                
                elements = []
                last_progress = 0
                for i, element in enumerate(building_elements, 1):
                    # Basic properties
                    element_data = {
                        "id": element.id(),
                        "type": element.is_a(),
                        "properties": get_common_properties(element),
                        "object_type": get_object_type(element)
                    }

                    # Add quantities
                    volume = get_volume_from_properties(element)
                    if volume:
                        element_data["volume"] = convert_unit_value(volume, length_unit)
                    
                    area = get_area_from_properties(element)
                    if area:
                        element_data["area"] = convert_unit_value(area, length_unit)
                    
                    dimensions = get_dimensions_from_properties(element)
                    if dimensions:
                        element_data["dimensions"] = convert_unit_value(dimensions, length_unit)

                    # Add materials
                    materials = material_service.get_element_materials(element)
                    if materials:
                        element_data["materials"] = materials
                        
                        # Add material volumes if available
                        material_volumes = material_service.get_material_volumes(element)
                        if material_volumes:
                            element_data["material_volumes"] = {
                                mat: {
                                    "volume": convert_unit_value(info["volume"], length_unit),
                                    "fraction": info["fraction"]
                                }
                                for mat, info in material_volumes.items()
                            }

                    elements.append(element_data)
                    
                    # Report progress at 5% intervals
                    current_progress = (i / total_elements) * 100
                    if current_progress >= last_progress + 5 or i == total_elements:
                        yield json.dumps({
                            "status": "processing",
                            "progress": current_progress,
                            "processed": i,
                            "total": total_elements
                        }) + "\n"
                        last_progress = current_progress

                # Final response with all elements
                yield json.dumps({
                    "status": "complete",
                    "elements": elements
                }) + "\n"

            except Exception as e:
                yield json.dumps({
                    "status": "error",
                    "message": str(e)
                }) + "\n"
                raise

        async def cleanup_background():
            """Clean up files after response is sent"""
            try:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")

        return StreamingResponse(
            generate_response(),
            media_type="application/x-ndjson",
            headers={
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-cache"
            },
            background=cleanup_background
        )

    except Exception as e:
        # Cleanup on error
        os.unlink(temp_path)
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/split-by-storey")
async def split_by_storey(file: UploadFile = File(...)):
    """Split an IFC file by storey and return as zip"""
    if not file.filename.endswith('.ifc'):
        raise HTTPException(status_code=400, detail="Invalid file type. Must be an IFC file.")

    tmp_file_path = None
    output_dir = None
    try:
        # Save uploaded file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ifc') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file.flush()
            tmp_file_path = tmp_file.name
        
        # Process the file
        ifc_file = ifcopenshell.open(tmp_file_path)
        splitter = StoreySpiltterService(ifc_file)
        result_files, output_dir = splitter.split_by_storey()
        
        if not result_files:
            raise HTTPException(status_code=400, detail="No storeys found in the IFC file")
        
        # Create zip file
        zip_path = os.path.join(output_dir, "storeys.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file_info in result_files:
                zipf.write(
                    file_info["file_path"], 
                    arcname=file_info["file_name"]
                )

        async def cleanup_background():
            """Clean up files after response is sent"""
            try:
                if tmp_file_path and os.path.exists(tmp_file_path):
                    os.unlink(tmp_file_path)
                if output_dir and os.path.exists(output_dir):
                    shutil.rmtree(output_dir)
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")

        return FileResponse(
            zip_path,
            media_type='application/zip',
            filename='storeys.zip',
            background=cleanup_background
        )
        
    except Exception as e:
        # Clean up on error
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        if output_dir and os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        raise HTTPException(status_code=400, detail=str(e))