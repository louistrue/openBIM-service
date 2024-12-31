from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends
from typing import Dict, Any, Optional, List
import tempfile
import os
import logging
import math
import ifcopenshell
from .common import get_ifc_classes

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/elements-info",
    summary="Get detailed technical information about IFC elements",
    description="""Get complete technical information about IFC elements following the IFC schema structure.
    Returns detailed data including GlobalIds, ownership history, geometry placements, and relationships.

    This endpoint provides raw IFC data useful for:
    - Technical analysis of IFC files
    - Debugging IFC structure issues 
    - Understanding complete element definitions
    - Accessing all IFC attributes and relationships

    The response includes:
    - Full IFC schema properties for each element
    - Nested relationships and references
    - Complete ownership and history data
    - Geometric placement information
    - All IFC attributes as defined in the schema

    Example response structure:
    ```json
    {
      "metadata": {
        "total_elements": 299,
        "total_pages": 6,
        "current_page": 1,
        "page_size": 50,
        "filtered_classes": []
      },
      "elements": [
        {
          "GlobalId": "2_LMFlUBniGem7M0zzhZCM",
          "Name": "Rafter 71 x 171",
          "ObjectType": "Rafter 71 x 171",
          "OwnerHistory": {
            "OwningUser": { ... },
            "OwningApplication": { ... },
            "CreationDate": 1412774152
          },
          "ObjectPlacement": { ... },
          "ifc_class": "IfcBeam"
        }
      ]
    }
    ```

    For simpler element data focused on properties and quantities,
    use the /extract-building-elements endpoint instead.""")
    
async def get_elements_info(
    file: UploadFile = File(...),
    page: Optional[int] = Query(1, ge=1, description="Page number (default: 1)"),
    page_size: Optional[int] = Query(50, ge=1, le=10000, description="Items per page (default: 50)"),
    filtered_classes: Optional[List[str]] = Depends(get_ifc_classes)
) -> Dict[str, Any]:

    if not file.filename.endswith('.ifc'):
        raise HTTPException(status_code=400, detail="Invalid file type. Must be an IFC file.")
        
    # Save uploaded file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.ifc') as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_path = temp_file.name

    try:
        ifc_file = ifcopenshell.open(temp_path)
        
        # Get all elements or filter by class if specified
        if filtered_classes:
            elements = []
            for class_name in filtered_classes:
                elements.extend(ifc_file.by_type(class_name))
        else:
            # Fix: Get all elements by using "IfcProduct" as the base class
            elements = ifc_file.by_type("IfcProduct")

        # Calculate pagination
        total_elements = len(elements)
        total_pages = math.ceil(total_elements / page_size)
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total_elements)
        
        # Get info for paginated elements
        elements_info = []
        for element in elements[start_idx:end_idx]:
            try:
                # Get element info using get_info_2
                info = element.get_info_2(
                    include_identifier=True,
                    recursive=True,  # Must be True for get_info_2
                    return_type=dict,
                    ignore=()
                )
                
                # Add element type for easier filtering
                info['ifc_class'] = element.is_a()
                elements_info.append(info)
                
            except Exception as e:
                logger.warning(f"Error getting info for element {element.id()}: {str(e)}")
                continue

        response = {
            "metadata": {
                "total_elements": total_elements,
                "total_pages": total_pages,
                "current_page": page,
                "page_size": page_size,
                "filtered_classes": filtered_classes if filtered_classes else []
            },
            "elements": elements_info
        }

        return response

    except Exception as e:
        logger.error(f"Error processing IFC file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)