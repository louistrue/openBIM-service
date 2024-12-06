from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import ifcopenshell
import tempfile
import os
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/process-ifc")
async def process_ifc(file: UploadFile = File(...)):
    tmp_file = None
    try:
        # Log the uploaded file info
        logger.info(f"Processing file: {file.filename}")
        
        # Create a temporary file to store the uploaded IFC
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.ifc')
        content = await file.read()
        tmp_file.write(content)
        tmp_file.flush()
        
        logger.info(f"Temporary file created: {tmp_file.name}")
        
        try:
            # Parse IFC file using IfcOpenShell
            ifc_file = ifcopenshell.open(tmp_file.name)
            logger.info("IFC file opened successfully")
            
            # Get all building elements
            elements = []
            building_elements = ifc_file.by_type("IfcBuildingElement")
            logger.info(f"Found {len(building_elements)} building elements")
            
            for element in building_elements:
                try:
                    # Get element properties
                    props = {}
                    if hasattr(element, 'IsDefinedBy'):
                        for definition in element.IsDefinedBy:
                            if hasattr(definition, 'RelatingPropertyDefinition'):
                                prop_set = definition.RelatingPropertyDefinition
                                if hasattr(prop_set, 'HasProperties'):
                                    for prop in prop_set.HasProperties:
                                        if hasattr(prop, 'Name') and hasattr(prop, 'NominalValue'):
                                            props[prop.Name] = prop.NominalValue.wrappedValue

                    # Get element level (building storey)
                    level = None
                    if hasattr(element, 'ContainedInStructure'):
                        containers = element.ContainedInStructure
                        if containers and hasattr(containers[0], 'RelatingStructure'):
                            level = containers[0].RelatingStructure.Name

                    element_data = {
                        "id": str(element.id()),
                        "type": element.is_a(),
                        "name": element.Name if hasattr(element, 'Name') else None,
                        "level": level,
                        "properties": props
                    }
                    elements.append(element_data)
                    
                except Exception as element_error:
                    logger.error(f"Error processing element {element.id()}: {str(element_error)}")
                    continue

            logger.info(f"Successfully processed {len(elements)} elements")
            return {"elements": elements}

        except Exception as ifc_error:
            logger.error(f"Error processing IFC file: {str(ifc_error)}")
            raise HTTPException(status_code=500, detail=f"Error processing IFC file: {str(ifc_error)}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # Clean up temporary file
        if tmp_file:
            try:
                tmp_file.close()
                os.unlink(tmp_file.name)
                logger.info("Temporary file cleaned up")
            except Exception as cleanup_error:
                logger.error(f"Error cleaning up temporary file: {str(cleanup_error)}")

@app.get("/api/elements/{file_id}")
async def get_elements(file_id: str):
    # TODO: Implement persistent storage and retrieval of parsed elements
    return {"message": "Not implemented yet"} 