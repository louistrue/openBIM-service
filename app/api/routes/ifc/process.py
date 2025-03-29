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
    get_dimensions_from_properties,
    clear_quantity_caches
)
from app.services.lca.materials import MaterialService
from app.services.ifc.units import get_project_units, convert_unit_value
from .common import _round_value
import gc

router = APIRouter()
logger = logging.getLogger(__name__)

# Maximum file size (50MB)
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB in bytes

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
    
    # Check file size before processing
    file_size = 0
    temp_file = None
    temp_path = None
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ifc') as temp_file:
            temp_path = temp_file.name
            chunk_size = 8192  # 8KB chunks
            
            while chunk := await file.read(chunk_size):
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE:
                    # Clean up and raise error
                    temp_file.close()
                    os.unlink(temp_path)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size is {MAX_FILE_SIZE/1024/1024:.1f}MB"
                    )
                temp_file.write(chunk)
            
            # Rewind file for reading
            temp_file.flush()
        
        ifc_file = ifcopenshell.open(temp_path)
        units = get_project_units(ifc_file)
        length_unit = units.get("LENGTHUNIT", {"type": "LENGTHUNIT", "name": "METER"})
        material_service = MaterialService(ifc_file)
        
        async def generate_response():
            try:
                # Clear caches before processing
                clear_quantity_caches()
                clear_property_caches()
                gc.collect()
                
                total_elements = len(ifc_file.by_type("IfcProduct"))
                processed = 0
                
                for element in ifc_file.by_type("IfcProduct"):
                    try:
                        element_data = {
                            "id": element.id(),
                            "ifc_entity": element.is_a(),
                            "properties": get_common_properties(element),
                            "object_type": get_object_type(element)
                        }

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

                        materials = material_service.get_element_materials(element)
                        if materials:
                            element_data["materials"] = materials
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
                        
                        # Stream each element immediately
                        yield json.dumps({
                            "status": "element",
                            "data": element_data
                        }) + "\n"
                        
                        processed += 1
                        if processed % 50 == 0:
                            # Clear caches periodically during processing
                            clear_quantity_caches()
                            clear_property_caches()
                            gc.collect()
                            
                        # Yield progress
                        progress = (processed / total_elements) * 100
                        yield f'{{"status": "processing", "progress": {progress:.1f}, "processed": {processed}, "total": {total_elements}}}\n'
                        
                    except Exception as e:
                        logger.error(f"Error processing element {element.id()}: {str(e)}")
                        continue
                
                # Clear caches after processing
                clear_quantity_caches()
                clear_property_caches()
                gc.collect()
                
                # Yield final result
                yield '{"status": "complete"}\n'
                
            finally:
                # Clean up temp file and clear memory
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except Exception as e:
                        logger.error(f"Error cleaning up temp file: {str(e)}")
                
                # Force garbage collection
                gc.collect()

        return StreamingResponse(
            generate_response(),
            media_type="application/x-ndjson",
            headers={
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-cache"
            }
        )

    except Exception as e:
        # Ensure cleanup on any error
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass
        
        # Clear caches and force garbage collection
        clear_quantity_caches()
        clear_property_caches()
        gc.collect()
        
        raise HTTPException(status_code=400, detail=str(e))