from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Body, Depends
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from typing import AsyncGenerator, List, Optional
import tempfile
import os
import logging
import json
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
from app.services.ifc.constituents import compute_constituent_fractions
import zipfile
import shutil
import math

router = APIRouter()
logger = logging.getLogger(__name__)

def _round_value(value: float, digits: int = 3) -> float:
    """Round float value to specified number of digits."""
    if isinstance(value, (int, float)):
        return round(value, digits)
    return value

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
                        "ifc_entity": element.is_a(),
                        "properties": get_common_properties(element),
                        "object_type": get_object_type(element)
                    }

                    # Add quantities
                    volume = get_volume_from_properties(element)
                    if volume:
                        element_data["volume"] = {
                            "net": _round_value(volume["net"], 5) if "net" in volume else None,
                            "gross": _round_value(volume["gross"], 5) if "gross" in volume else None
                        }
                    
                    area = get_area_from_properties(element)
                    if area:
                        element_data["area"] = convert_unit_value(area, length_unit)
                    
                    dimensions = get_dimensions_from_properties(element)
                    if dimensions:
                        element_data["dimensions"] = {
                            "length": _round_value(dimensions["length"]),
                            "width": _round_value(dimensions["width"]),
                            "height": _round_value(dimensions["height"])
                        }

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
                                    "fraction": info["fraction"],
                                    "width": convert_unit_value(info["width"], length_unit) if "width" in info else None
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

# Dependency function to handle IFC class filtering
async def get_ifc_classes(
    enable_filter: bool = Query(False, description="Enable filtering by IFC classes (default: false)"),
    ifc_classes: Optional[List[str]] = Query(
        default=None,
        description="IFC classes to include when filtering is enabled. Add multiple values by clicking '+' below.",
        example=["IfcWall", "IfcSlab"],  # Show multiple examples
    )
) -> Optional[List[str]]:
    """Filter IFC classes. Enable filtering first, then add one or more IFC classes."""
    if not enable_filter:
        return None
        
    if ifc_classes:
        # Clean up each class name
        cleaned_classes = []
        for cls in ifc_classes:
            # Remove "List [", "]" and clean up quotes and spaces
            cls = cls.replace("List [", "").replace("]", "").strip().strip('"\'')
            if cls:  # Only add non-empty strings
                cleaned_classes.append(cls)
        return cleaned_classes
    return None

@router.post("/extract-building-elements",
    description="""
    Extract building element data from IFC file. Only specify parameters to override defaults:
    
    Minimal example (using all defaults):
    `/extract-building-elements`
    
    Filter by IFC classes (must enable filtering first):
    `/extract-building-elements?enable_filter=true&ifc_classes=IfcWall&ifc_classes=IfcSlab`
    
    Include widths:
    `/extract-building-elements?exclude_width=false`
    
    Include constituent volumes:
    `/extract-building-elements?exclude_constituent_volumes=false`
    """)
async def extract_building_elements(
    file: UploadFile = File(...),
    page: Optional[int] = Query(1, ge=1, description="Page number (default: 1)"),
    page_size: Optional[int] = Query(50, ge=1, le=10000, description="Items per page (default: 50)"),
    filtered_classes: Optional[List[str]] = Depends(get_ifc_classes),
    exclude_properties: Optional[bool] = Query(False, description="Exclude element properties (default: false)"),
    exclude_quantities: Optional[bool] = Query(False, description="Exclude quantities (default: false)"),
    exclude_materials: Optional[bool] = Query(False, description="Exclude material information (default: false)"),
    exclude_width: Optional[bool] = Query(True, description="Exclude material widths (default: true)"),
    exclude_constituent_volumes: Optional[bool] = Query(True, description="Exclude constituent volumes (default: true)")
):
    """
    Extract detailed information about building elements from an IFC file.
    By default includes all available data except widths and constituent volumes.
    Only specify parameters to override defaults.
    """
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

        # Get and filter building elements
        building_elements = ifc_file.by_type("IfcBuildingElement")
        if filtered_classes:  # filtered_classes will be None if enable_filter is False
            building_elements = [e for e in building_elements if e.is_a() in filtered_classes]

        # Calculate pagination
        total_elements = len(building_elements)
        total_pages = math.ceil(total_elements / page_size)
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_elements)
        
        # Track elements with invalid material fractions
        invalid_material_fractions = []
        
        # Process only the elements for current page
        elements = []
        for element in building_elements[start_idx:end_idx]:
            # Basic properties (always included)
            element_data = {
                "id": element.GlobalId,
                "ifc_class": element.is_a(),
                "object_type": get_object_type(element)
            }

            # Optional properties
            if not exclude_properties:
                element_data["properties"] = get_common_properties(element)

            # Optional quantities
            if not exclude_quantities:
                quantities = {}
                
                volume = get_volume_from_properties(element)
                if volume:
                    quantities["volume"] = {
                        "net": _round_value(volume["net"], 5) if "net" in volume else None,
                        "gross": _round_value(volume["gross"], 5) if "gross" in volume else None
                    }
                
                area = get_area_from_properties(element)
                if area:
                    quantities["area"] = convert_unit_value(area, length_unit)
                
                dimensions = get_dimensions_from_properties(element)
                if dimensions:
                    quantities["dimensions"] = {
                        "length": _round_value(dimensions["length"]),
                        "width": _round_value(dimensions["width"]),
                        "height": _round_value(dimensions["height"])
                    }
                
                if quantities:
                    element_data["quantities"] = quantities

            # Optional materials
            if not exclude_materials:
                materials = material_service.get_element_materials(element)
                if materials:
                    element_data["materials"] = materials
                    
                    # Get base element volume for constituent calculations
                    element_volume = get_volume_from_properties(element)
                    if isinstance(element_volume, dict):
                        element_volume = element_volume.get('net', element_volume.get('value', 0.0))
                    
                    # Try constituent volumes first if enabled
                    if not exclude_constituent_volumes and element_volume:
                        material_associations = element.HasAssociations
                        has_constituent_volumes = False
                        
                        for rel in material_associations:
                            if rel.is_a('IfcRelAssociatesMaterial'):
                                relating_material = rel.RelatingMaterial
                                if relating_material.is_a('IfcMaterialConstituentSet'):
                                    # Get unit scale factor for conversion to mm
                                    unit_scale = length_unit.get("scale_to_mm", 1.0)
                                    
                                    # Compute constituent fractions based on widths
                                    constituent_fractions, constituent_widths = compute_constituent_fractions(
                                        ifc_file,
                                        relating_material,
                                        [element],
                                        unit_scale
                                    )
                                    
                                    if constituent_fractions:
                                        has_constituent_volumes = True
                                        element_data["material_volumes"] = {}
                                        total_fraction = 0.0
                                        
                                        for constituent, fraction in constituent_fractions.items():
                                            material_name = constituent.Material.Name if constituent.Material else "Unknown"
                                            constituent_volume = float(element_volume) * float(fraction)
                                            
                                            # Create unique key for each constituent
                                            material_key = material_name
                                            counter = 1
                                            while material_key in element_data["material_volumes"]:
                                                material_key = f"{material_name} ({counter})"
                                                counter += 1
                                            
                                            element_data["material_volumes"][material_key] = {
                                                "fraction": fraction,
                                                "volume": convert_unit_value(constituent_volume, length_unit),
                                            }
                                            if not exclude_width:
                                                element_data["material_volumes"][material_key]["width_mm"] = constituent_widths[constituent]
                                        
                                            total_fraction += fraction
                                        
                                        # Only keep volumes if fractions sum to approximately 1
                                        if abs(total_fraction - 1.0) > 0.001:
                                            element_data.pop("material_volumes", None)
                                            invalid_material_fractions.append({
                                                "element_id": element.GlobalId,
                                                "element_type": element.is_a(),
                                                "total_fraction": total_fraction
                                            })
                    # Fall back to standard material volumes if no constituent volumes were added
                    if "material_volumes" not in element_data:
                        material_volumes = material_service.get_material_volumes(element)
                        if material_volumes:
                            total_fraction = sum(info["fraction"] for info in material_volumes.values())
                            if abs(total_fraction - 1.0) <= 0.001:
                                # Get material layer set if available
                                material_layer_set = None
                                material_layer_usage = None
                                for rel in element.HasAssociations:
                                    if rel.is_a('IfcRelAssociatesMaterial'):
                                        relating_material = rel.RelatingMaterial
                                        if relating_material.is_a('IfcMaterialLayerSet'):
                                            material_layer_set = relating_material
                                            break
                                        elif relating_material.is_a('IfcMaterialLayerSetUsage'):
                                            material_layer_usage = relating_material
                                            material_layer_set = relating_material.ForLayerSet
                                            if material_layer_set:
                                                break

                                # Create a mapping of material names to their layers
                                material_to_layer = {}
                                if material_layer_set and material_layer_set.MaterialLayers:
                                    for layer in material_layer_set.MaterialLayers:
                                        if layer.Material:
                                            material_to_layer[layer.Material.Name] = layer

                                element_data["material_volumes"] = {}
                                for mat, info in material_volumes.items():
                                    volume_data = {
                                        "fraction": _round_value(info["fraction"], 5),  # 5 digits for fraction
                                        "volume": _round_value(convert_unit_value(info["volume"], length_unit), 5)  # 5 digits for volume
                                    }
                                    
                                    # Add width if requested
                                    if not exclude_width and "width" in info:
                                        volume_data["width"] = info["width"]  # Width is already in meters
                                    
                                    element_data["material_volumes"][mat] = volume_data

                            else:
                                invalid_material_fractions.append({
                                    "element_id": element.GlobalId,
                                    "element_type": element.is_a(),
                                    "total_fraction": total_fraction
                                })

                    # Add constituent widths if requested (when not using constituent volumes)
                    if not exclude_width and exclude_constituent_volumes:
                        material_associations = element.HasAssociations
                        for rel in material_associations:
                            if rel.is_a('IfcRelAssociatesMaterial'):
                                relating_material = rel.RelatingMaterial
                                if relating_material.is_a('IfcMaterialConstituentSet'):
                                    # Get unit scale factor for conversion to mm
                                    unit_scale = length_unit.get("scale_to_mm", 1.0)
                                    
                                    # Compute constituent fractions based on widths
                                    constituent_fractions, constituent_widths = compute_constituent_fractions(
                                        ifc_file,
                                        relating_material,
                                        [element],
                                        unit_scale
                                    )
                                    
                                    if constituent_fractions:
                                        element_data["material_constituents"] = {
                                            constituent.Name: {
                                                "fraction": fraction,
                                                "material": constituent.Material.Name if constituent.Material else None,
                                                "width_mm": constituent_widths[constituent]
                                            }
                                            for constituent, fraction in constituent_fractions.items()
                                        }

            elements.append(element_data)

        # Clean up the temporary file
        if os.path.exists(temp_path):
            os.unlink(temp_path)

        # Modify the response to include debug logs
        response = {
            "metadata": {
                "total_elements": total_elements,
                "total_pages": total_pages,
                "current_page": page,
                "page_size": page_size,
                "ifc_classes": filtered_classes if filtered_classes else [],
                "units": {
                    "length": length_unit["name"],
                    "area": f"{length_unit['name']}²",
                    "volume": f"{length_unit['name']}³"
                }
            },
            "elements": elements
        }

        # Add warnings if there are invalid material fractions
        if invalid_material_fractions:
            response["metadata"]["warnings"] = {
                "invalid_material_fractions": {
                    "message": "Some elements have material fractions that don't sum to 1.0",
                    "affected_elements": invalid_material_fractions
                }
            }

        return response

    except Exception as e:
        # Cleanup on error
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise HTTPException(status_code=400, detail=str(e))