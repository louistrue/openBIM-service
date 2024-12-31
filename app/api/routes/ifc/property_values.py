from fastapi import APIRouter, UploadFile, File, HTTPException, Query
import tempfile
import os
import logging
import ifcopenshell
from app.core.models.property_values import PropertyValue, PropertyValuesResponse
from app.services.ifc.property_values import get_property_values

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/property-values", 
    response_model=PropertyValuesResponse,
    summary="Extract Property Values by IFC Class",
    description="""
    Extracts specific property values for all elements of a given IFC class.
    Supports wildcard matching for property set names.
    
    Parameters:
    - ifc_class: The IFC class to search (e.g., 'IfcWall', 'IfcSlab', 'IfcWindow')
    - property_path: Path to the property in format 'PsetName.PropertyName'
    
    Property Path Examples:
    - '*Common.IsExternal' - Matches 'Pset_WallCommon.IsExternal', 'Pset_SlabCommon.IsExternal', etc.
    - 'Pset_WallCommon.LoadBearing' - Exact match for wall load-bearing property
    
    Example Response:
    ```json
    {
      "values": [
        {
          "guid": "1dvQlSPDlRHf2uvSkxW_x3",
          "value": 1,
          "data_type": "IfcBoolean"
        },
        {
          "guid": "2VflvzVsroGh8lACjVt1SS",
          "value": 0,
          "data_type": "IfcBoolean"
        }
      ],
      "total_elements": 2
    }
    ```
    
    Notes:
    - The GUID in the response can be used to identify specific elements
    - The data_type field indicates the IFC type of the property value
    - Boolean values are represented as 1 (true) and 0 (false)
    - Properties that don't exist for an element are omitted from results
    """)
async def get_property_values_for_class(
    file: UploadFile = File(...),
    ifc_class: str = Query(..., description="IFC class name (e.g., 'IfcWall')"),
    property_path: str = Query(
        ..., 
        description="Property path in format 'PsetName.PropertyName'. Supports wildcards in PsetName (e.g., '*Common.LoadBearing')"
    )
) -> PropertyValuesResponse:
    """
    Get property values for all elements of a specific IFC class.
    
    The property path should be in the format 'PsetName.PropertyName'.
    You can use wildcards in the PsetName part, e.g., '*Common.LoadBearing'
    will match both 'Pset_WallCommon.LoadBearing' and 'Pset_SlabCommon.LoadBearing'.
    
    Returns a list of property values with their GUIDs and data types.
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
        
        # Get property values using the service function
        values = get_property_values(ifc_file, ifc_class, property_path)
        
        # Convert to response model
        return PropertyValuesResponse(
            values=[
                PropertyValue(
                    guid=value.guid,
                    value=value.value,
                    data_type=value.data_type
                ) for value in values
            ],
            total_elements=len(values)
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing property values: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)