from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import tempfile
import os
import json
import logging
import ifcopenshell
from app.services.ifc.properties import get_common_properties, get_object_type
from app.services.ifc.quantities import (
    get_volume_from_properties,
    get_area_from_properties,
    get_dimensions_from_properties
)
from app.services.lca.materials import MaterialService
from app.services.ifc.units import get_project_units, convert_unit_value
from .common import _round_value

router = APIRouter()
logger = logging.getLogger(__name__)
@router.post("/process", 
    summary="Stream Building Element Analysis",
    description="""
    Analyzes building elements from an IFC file and streams the results in NDJSON format (Newline Delimited JSON).
    
    The response is streamed as a series of JSON objects, each on a new line:
    
    1. Progress updates during processing:
    ```json
    {"status": "processing", "progress": 25.5, "processed": 50, "total": 196}
    ```
    
    2. Final result with complete element data:
    ```json
    {
      "status": "complete",
      "elements": [
        {
          "id": "489",
          "ifc_entity": "IfcBeam",
          "properties": {
            "loadBearing": true,
            "isExternal": false
          },
          "object_type": "Beam Type",
          "volume": {
            "net": null,
            "gross": 0.09863
          },
          "area": {},
          "dimensions": {
            "length": 2476.229,
            "width": null,
            "height": null
          },
          "materials": ["wood - pine"],
          "material_volumes": {
            "wood - pine": {
              "volume": 9.863e-05,
              "fraction": 1.0,
              "width": null
            }
          }
        }
      ]
    }
    ```
    
    The streamed format allows for real-time progress monitoring and handling of large IFC files.
    Each line is a complete JSON object that can be parsed independently.
    """)
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