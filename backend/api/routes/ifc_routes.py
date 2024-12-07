from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import tempfile
import os
import logging
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
import ifcopenshell
from ifcopenshell.util.unit import calculate_unit_scale
from services.ifc.properties import get_common_properties, get_object_type
from services.ifc.quantities import (
    get_volume_from_properties,
    get_area_from_properties,
    get_dimensions_from_properties
)
from services.lca.materials import MaterialService
from fastapi.responses import JSONResponse
from services.ifc.splitter import StoreySpiltterService
import shutil
from fastapi.responses import FileResponse
import zipfile

router = APIRouter()

logger = logging.getLogger(__name__)

def init_ifcopenshell(file_path: str, scale: float):
    """Initialize ifcopenshell in each process"""
    global ifc_file, unit_scale, material_service
    try:
        ifc_file = ifcopenshell.open(file_path)
        unit_scale = scale
        material_service = MaterialService(ifc_file)
    except Exception as e:
        logger.error(f"Error initializing process: {str(e)}")
        ifc_file = None
        unit_scale = 1.0
        material_service = None

def process_element_parallel(element_id):
    """Process a single element in parallel"""
    try:
        element = ifc_file.by_id(element_id)
        if not element:
            return None

        # Get all properties first
        volumes = get_volume_from_properties(element)
        areas = get_area_from_properties(element)
        dimensions = get_dimensions_from_properties(element)
        materials = material_service.get_layer_volumes_and_materials(
            element, volumes, unit_scale
        )
        common_props = get_common_properties(element)
        
        # Get basic properties that don't need complex objects
        global_id = element.GlobalId if hasattr(element, 'GlobalId') else None
        element_type = element.is_a()
        element_name = element.Name if hasattr(element, 'Name') else None
        
        # Get predefined type safely
        try:
            predefined_type = getattr(element, "PredefinedType", None)
            if predefined_type:
                if hasattr(predefined_type, "is_a"):
                    if predefined_type.is_a() == "IfcLabel":
                        predefined_type = predefined_type.wrappedValue
                else:
                    predefined_type = str(predefined_type)
        except Exception:
            predefined_type = None
            
        object_type = get_object_type(element)
        
        # Convert measurements to mm
        volume_scale = unit_scale ** 3  # For volumes (m³ to mm³)
        area_scale = unit_scale ** 2    # For areas (m² to mm²)
        
        # Scale volumes
        if volumes["net"] is not None:
            volumes["net"] *= volume_scale
        if volumes["gross"] is not None:
            volumes["gross"] *= volume_scale
            
        # Scale areas
        if areas["net"] is not None:
            areas["net"] *= area_scale
        if areas["gross"] is not None:
            areas["gross"] *= area_scale
            
        # Scale linear dimensions
        if dimensions["length"] is not None:
            dimensions["length"] *= unit_scale
        if dimensions["width"] is not None:
            dimensions["width"] *= unit_scale
        if dimensions["height"] is not None:
            dimensions["height"] *= unit_scale
        
        # Create result dictionary with only serializable data
        return {
            "id": str(element_id),
            "globalId": global_id,
            "type": element_type,
            "predefinedType": predefined_type,
            "objectType": object_type,
            "name": element_name,
            "level": None,
            "volume": volumes["net"] if volumes["net"] is not None else (volumes["gross"] if volumes["gross"] is not None else 0),
            "netVolume": volumes["net"] if volumes["net"] is not None else None,
            "grossVolume": volumes["gross"] if volumes["gross"] is not None else None,
            "netArea": areas["net"],
            "grossArea": areas["gross"],
            "length": dimensions["length"],
            "width": dimensions["width"],
            "height": dimensions["height"],
            "materials": materials,
            "loadBearing": common_props["loadBearing"],
            "isExternal": common_props["isExternal"]
        }
    except Exception as element_error:
        logger.error(f"Error processing element {element_id}: {str(element_error)}")
        return None

def process_chunk(chunk_ids):
    """Process a chunk of elements"""
    results = []
    for element_id in chunk_ids:
        try:
            element = ifc_file.by_id(element_id)
            if element:
                result = process_element_parallel(element_id)
                if result:
                    results.append(result)
        except Exception as e:
            logger.error(f"Error processing element {element_id}: {str(e)}")
    return results

@router.post("/process-ifc")
async def process_ifc(file: UploadFile = File(...)):
    tmp_file_path = None
    try:
        logger.info(f"Processing file: {file.filename}")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ifc') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file.flush()
            tmp_file_path = tmp_file.name
        
        async def process_and_stream():
            try:
                main_ifc = ifcopenshell.open(tmp_file_path)
                logger.info("IFC file opened successfully")
                
                # Calculate unit scale
                unit_scale = calculate_unit_scale(main_ifc) * 1000.0  # Convert to mm
                logger.info(f"Unit scale factor to mm: {unit_scale}")
                
                building_elements = main_ifc.by_type("IfcBuildingElement")
                total_elements = len(building_elements)
                logger.info(f"Found {total_elements} building elements")
                
                # Get element IDs
                element_ids = [element.id() for element in building_elements]
                chunk_size = 1000
                elements = []
                processed_count = 0
                
                # Use ProcessPoolExecutor
                num_processes = max(multiprocessing.cpu_count() - 1, 1)
                
                with ProcessPoolExecutor(
                    max_workers=num_processes,
                    initializer=init_ifcopenshell,
                    initargs=(tmp_file_path, unit_scale)
                ) as executor:
                    futures = []
                    for i in range(0, total_elements, chunk_size):
                        chunk_ids = element_ids[i:i + chunk_size]
                        future = executor.submit(process_chunk, chunk_ids)
                        futures.append(future)
                    
                    for future in futures:
                        chunk_results = future.result()
                        valid_results = [r for r in chunk_results if r is not None]
                        elements.extend(valid_results)
                        
                        processed_count += chunk_size
                        progress = min(processed_count / total_elements * 100, 100)
                        
                        yield json.dumps({
                            "progress": progress,
                            "processed": min(processed_count, total_elements),
                            "total": total_elements,
                            "status": "processing"
                        }, ensure_ascii=False).strip() + "\n"
                
                yield json.dumps({
                    "progress": 100,
                    "processed": total_elements,
                    "total": total_elements,
                    "status": "complete",
                    "elements": elements
                }, ensure_ascii=False).strip() + "\n"
                
            except Exception as e:
                logger.error(f"Error processing file: {str(e)}")
                yield json.dumps({
                    "status": "error",
                    "error": str(e)
                }, ensure_ascii=False).strip() + "\n"
            finally:
                if tmp_file_path:
                    try:
                        os.unlink(tmp_file_path)
                        logger.info("Temporary file cleaned up")
                    except Exception as cleanup_error:
                        logger.error(f"Error cleaning up temporary file: {str(cleanup_error)}")

        return StreamingResponse(
            process_and_stream(),
            media_type="application/x-ndjson",
            headers={
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-cache"
            }
        )

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/elements/{file_id}")
async def get_elements(file_id: str):
    return {"message": "Not implemented yet"}

@router.post("/split-by-storey")
async def split_by_storey(file: UploadFile = File(...)):
    tmp_file_path = None
    output_dir = None
    try:
        logger.info(f"Processing file for storey split: {file.filename}")
        
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
        
        # Create zip file
        zip_path = os.path.join(output_dir, "storeys.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file_info in result_files:
                zipf.write(
                    file_info["file_path"], 
                    arcname=file_info["file_name"]
                )
        
        # Return the zip file
        response = FileResponse(
            zip_path,
            media_type='application/zip',
            filename='storeys.zip',
            headers={
                "Content-Disposition": "attachment; filename=storeys.zip"
            }
        )
        
        # Clean up after response is sent
        response.background = lambda: cleanup_files(tmp_file_path, output_dir)
        
        return response

    except Exception as e:
        logger.error(f"Error splitting file by storey: {str(e)}")
        # Clean up on error
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        if output_dir and os.path.exists(output_dir):
            shutil.rmtree(output_dir)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

def cleanup_files(tmp_file_path: str, output_dir: str):
    """Clean up temporary files after response is sent."""
    try:
        if tmp_file_path and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        if output_dir and os.path.exists(output_dir):
            shutil.rmtree(output_dir)
    except Exception as e:
        logger.error(f"Error cleaning up files: {str(e)}")