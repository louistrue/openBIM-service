from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends, BackgroundTasks
from typing import List, Optional, Annotated, Dict, Any
import tempfile
import os
import logging
import math
import ifcopenshell
import httpx
import asyncio
import uuid
from pydantic import BaseModel, HttpUrl
from app.services.ifc.properties import get_common_properties, get_object_type, get_model_metadata
from app.services.ifc.quantities import (
    get_volume_from_properties,
    get_area_from_properties,
    get_dimensions_from_properties
)
from app.services.lca.materials import MaterialService
from app.services.ifc.units import get_project_units, convert_unit_value
from app.services.ifc.constituents import compute_constituent_fractions
from .common import _round_value, get_ifc_classes

def generate_unique_id() -> str:
    """Generate a unique task ID."""
    return str(uuid.uuid4())

# Models for callback functionality
class CallbackConfig(BaseModel):
    url: HttpUrl
    token: str

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/extract-building-elements",
    summary="Extract Detailed Building Element Data",
    description="""
    Extracts comprehensive information about building elements including properties, 
    quantities, materials, and their relationships. Can optionally send results to a callback URL.

    If callback_config is provided:
    - The endpoint returns immediately with a task ID
    - Progress updates (10%) are sent to the callback URL
    - Final results are sent to the callback URL
    - All callback requests include the provided token in Authorization header

    Output Structure:
    ```json
    {
      "metadata": {
        "total_elements": 3,
        "total_pages": 1,
        "current_page": 1,
        "page_size": 50,
        "ifc_classes": [],  // Filtered classes if specified
        "units": {
          "length": "METRE",
          "area": "METRE²",
          "volume": "METRE³"
        }
      },
      "elements": [
        {
          "id": "3DqaUydM99ehywE4_2hm1u",  // Unique element GUID
          "ifc_class": "IfcWall",           // IFC entity type
          "object_type": "Basic Wall:Holz Aussenwand_470mm",  // Type name
          "properties": {
            "loadBearing": true,   // Common properties
            "isExternal": true
          },
          "quantities": {
            "volume": {
              "net": 31.90906,    // Net volume (excluding openings)
              "gross": 32.38024   // Gross volume (including openings)
            },
            "area": {
              "net": 68.89412,    // Net surface area
              "gross": 68.89412   // Gross surface area
            },
            "dimensions": {
              "length": 19.684,   // Base quantities
              "width": 0.47,
              "height": 3.5
            }
          },
          "materials": [           // List of material names
            "_Holz_wg",
            "_Staenderkonstruktion_ungedaemmt_wg"
          ],
          "material_volumes": {    // Detailed material information
            "_Holz_wg": {
              "fraction": 0.04255,  // Volume fraction of total
              "volume": 1.35783,    // Absolute volume in m³
              "width": 0.02        // Layer width in m
            }
          }
        }
      ]
    }
    ```

    Features:
    - Paginated results for handling large models
    - Optional filtering by IFC classes
    - Consistent unit system (metric)
    - Complete material layering information
    - Accurate quantity calculations
    - Common property extraction
    - Optional callback URL for async processing
    """)
async def extract_building_elements(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    page: Optional[int] = Query(1, ge=1, description="Page number (default: 1)"),
    page_size: Optional[int] = Query(50, ge=1, le=10000, description="Items per page (default: 50)"),
    filtered_classes: Optional[List[str]] = Depends(get_ifc_classes),
    exclude_properties: Annotated[bool, Query(description="Exclude element properties")] = False,
    exclude_quantities: Annotated[bool, Query(description="Exclude quantities")] = False,
    exclude_materials: Annotated[bool, Query(description="Exclude material information")] = False,
    exclude_width: Annotated[bool, Query(description="Exclude material widths")] = False,
    exclude_constituent_volumes: Annotated[bool, Query(description="Exclude constituent volumes")] = False,
    callback_config: Optional[CallbackConfig] = None
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

    async def process_and_callback():
        try:
            ifc_file = ifcopenshell.open(temp_path)
            units = get_project_units(ifc_file)
            length_unit = units.get("LENGTHUNIT", {"type": "LENGTHUNIT", "name": "METER"})
            material_service = MaterialService(ifc_file)

            # Get and filter building elements
            building_elements = ifc_file.by_type("IfcBuildingElement")
            if filtered_classes:
                building_elements = [e for e in building_elements if e.is_a() in filtered_classes]

            total_elements = len(building_elements)
            total_pages = math.ceil(total_elements / page_size)
            
            # Calculate pagination indices
            start_idx = (page - 1) * page_size
            end_idx = min(start_idx + page_size, total_elements)
            
            # Process elements in chunks for progress updates
            elements = []
            chunk_size = max(1, total_elements // 10)  # 10% chunks
            
            async with httpx.AsyncClient() as client:
                for i in range(0, total_elements, chunk_size):
                    chunk = building_elements[i:i + chunk_size]
                    
                    # Process chunk
                    for element in chunk:
                        element_data = {
                            "id": element.GlobalId,
                            "ifc_class": element.is_a(),
                            "object_type": get_object_type(element)
                        }

                        if not exclude_properties:
                            element_data["properties"] = get_common_properties(element)

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

                        if not exclude_materials:
                            materials = material_service.get_element_materials(element)
                            if materials:
                                element_data["materials"] = materials
                                
                                element_volume = get_volume_from_properties(element)
                                if isinstance(element_volume, dict):
                                    element_volume = element_volume.get('net', element_volume.get('value', 0.0))
                                
                                if not exclude_constituent_volumes and element_volume:
                                    material_associations = element.HasAssociations
                                    has_constituent_volumes = False
                                    
                                    for rel in material_associations:
                                        if rel.is_a('IfcRelAssociatesMaterial'):
                                            relating_material = rel.RelatingMaterial
                                            if relating_material.is_a('IfcMaterialConstituentSet'):
                                                unit_scale = length_unit.get("scale_to_mm", 1.0)
                                                
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
                                                        
                                                        material_key = material_name
                                                        counter = 1
                                                        while material_key in element_data["material_volumes"]:
                                                            material_key = f"{material_name} ({counter})"
                                                            counter += 1
                                                        
                                                        element_data["material_volumes"][material_key] = {
                                                            "fraction": _round_value(fraction, 5),
                                                            "volume": _round_value(convert_unit_value(constituent_volume, length_unit), 5),
                                                        }
                                                        if not exclude_width:
                                                            element_data["material_volumes"][material_key]["width"] = convert_unit_value(constituent_widths[constituent] / 1000.0, length_unit)  # Convert mm to m
                                                    
                                                        total_fraction += fraction
                                                    
                                                    # Only keep volumes if fractions sum to approximately 1
                                                    if abs(total_fraction - 1.0) > 0.001:
                                                        element_data.pop("material_volumes", None)

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

                        elements.append(element_data)
                    
                    # Send progress update if callback configured
                    if callback_config:
                        progress = min(100, int((i + len(chunk)) / total_elements * 100))
                        if progress % 10 == 0:  # Send update every 10%
                            try:
                                await client.post(
                                    str(callback_config.url),
                                    headers={"Authorization": callback_config.token},
                                    json={
                                        "status": "processing",
                                        "progress": progress,
                                        "total_elements": total_elements,
                                        "processed_elements": i + len(chunk)
                                    }
                                )
                            except Exception as e:
                                logger.error(f"Failed to send progress update: {str(e)}")

            # Prepare final response
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
                "model_info": get_model_metadata(ifc_file),
                "elements": elements[start_idx:end_idx]  # Only return requested page
            }

            # Send final result if callback configured
            if callback_config:
                try:
                    await client.post(
                        str(callback_config.url),
                        headers={"Authorization": callback_config.token},
                        json={
                            "status": "completed",
                            "progress": 100,
                            "result": response
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to send final result: {str(e)}")
            
            return response

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error processing IFC file: {error_msg}")
            if callback_config:
                try:
                    async with httpx.AsyncClient() as client:
                        await client.post(
                            str(callback_config.url),
                            headers={"Authorization": callback_config.token},
                            json={
                                "status": "error",
                                "error": error_msg
                            }
                        )
                except Exception as callback_error:
                    logger.error(f"Failed to send error update: {str(callback_error)}")
            raise HTTPException(status_code=400, detail=error_msg)
        finally:
            # Cleanup temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    if callback_config:
        # Start processing in background and return immediately
        task_id = generate_unique_id()
        background_tasks.add_task(process_and_callback)
        return {"task_id": task_id, "message": "Processing started. Results will be sent to callback URL."}
    else:
        # Process synchronously and return result
        return await process_and_callback()