from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import tempfile
import os
import logging
import ifcopenshell
import zipfile
import shutil
from app.services.ifc.splitter import StoreySpiltterService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/split-by-storey",
    summary="Split IFC by Building Storeys",
    description="""
    Splits an IFC file into multiple IFC files, one for each building storey, and returns them as a zip archive.
    
    Each resulting IFC file:
    - Contains all elements associated with a specific storey
    - Maintains complete IFC structure and relationships
    - Includes its own IfcProject, IfcSite, and IfcBuilding entities
    - Preserves all material definitions, property sets, and type information
    
    Example for a 3-storey building:
    ```
    Input: building.ifc (containing 3 storeys)
    Output: storeys.zip containing:
      - ground_floor.ifc
        - IfcProject #1
        - IfcSite #1
        - IfcBuilding #1
        - IfcBuildingStorey (Ground Floor)
        - All elements on ground floor
      
      - first_floor.ifc
        - IfcProject #2
        - IfcSite #2
        - IfcBuilding #2
        - IfcBuildingStorey (First Floor)
        - All elements on first floor
      
      - second_floor.ifc
        - IfcProject #3
        - IfcSite #3
        - IfcBuilding #3
        - IfcBuildingStorey (Second Floor)
        - All elements on second floor
    ```
    
    Note: Each split file is a complete, valid IFC file that can be opened independently.
    This means some entities (like IfcProject) are duplicated across files to maintain
    proper IFC structure and relationships.
    """)
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