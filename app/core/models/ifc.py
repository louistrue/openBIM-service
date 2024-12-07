from typing import Optional, List, Dict, Literal
from pydantic import BaseModel, Field, ConfigDict

class Material(BaseModel):
    """Material information for an IFC element"""
    name: str
    volume: Optional[float] = None
    fraction: Optional[float] = None
    thickness: Optional[float] = None

class Element(BaseModel):
    """IFC building element with properties and quantities"""
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123",
                "globalId": "2O2Fr$t4X7Zf8NOew3FLBD",
                "type": "IfcWall",
                "name": "Basic Wall:Interior - 165 Plaster - Partition:2095493",
                "volume": 2.31,
                "materials": [{"name": "Plaster", "volume": 2.31, "fraction": 1.0}]
            }
        }
    )

    id: str = Field(description="Internal ID of the element")
    globalId: Optional[str] = Field(None, description="IFC Global ID")
    type: str = Field(description="IFC entity type (e.g. IfcWall)")
    predefinedType: Optional[str] = Field(None, description="IFC predefined type")
    objectType: Optional[str] = Field(None, description="Object type from type object")
    name: Optional[str] = Field(None, description="Name of the element")
    level: Optional[str] = Field(None, description="Building storey name")
    
    # Quantities
    volume: float = Field(0, description="Volume in mm³")
    netVolume: Optional[float] = Field(None, description="Net volume in mm³")
    grossVolume: Optional[float] = Field(None, description="Gross volume in mm³")
    netArea: Optional[float] = Field(None, description="Net area in mm²")
    grossArea: Optional[float] = Field(None, description="Gross area in mm²")
    length: Optional[float] = Field(None, description="Length in mm")
    width: Optional[float] = Field(None, description="Width in mm")
    height: Optional[float] = Field(None, description="Height in mm")
    
    # Properties
    materials: List[Material] = Field(
        default_factory=list,
        description="List of materials with volumes"
    )
    loadBearing: Optional[bool] = Field(None, description="Whether element is load bearing")
    isExternal: Optional[bool] = Field(None, description="Whether element is external")

class ProcessingStatus(BaseModel):
    """Status update during IFC processing"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "progress": 45.5,
                "processed": 455,
                "total": 1000,
                "status": "processing"
            }
        }
    )

    progress: float = Field(description="Processing progress percentage (0-100)")
    processed: int = Field(description="Number of processed elements")
    total: int = Field(description="Total number of elements to process")
    status: Literal["processing", "complete", "error"] = Field(
        description="Current processing status"
    )
    elements: Optional[List[Element]] = Field(
        None,
        description="Processed elements (only in final response)"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if status is 'error'"
    )

class StoreyFile(BaseModel):
    """Information about a split storey IFC file"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "storey_name": "Level 1",
                "storey_id": "2O2Fr$t4X7Zf8NOew3FLBD",
                "file_name": "1-Level_1.ifc",
                "file_path": "/tmp/splits/1-Level_1.ifc"
            }
        }
    )

    storey_name: str = Field(description="Name of the building storey")
    storey_id: str = Field(description="IFC Global ID of the storey")
    file_path: str = Field(description="Full path to the generated IFC file")
    file_name: str = Field(description="Name of the generated IFC file")

class SplitResponse(BaseModel):
    """Response for storey split operation"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "storeys": [
                    {
                        "storey_name": "Level 1",
                        "storey_id": "2O2Fr$t4X7Zf8NOew3FLBD",
                        "file_name": "1-Level_1.ifc"
                    }
                ],
                "zip_file": "storeys.zip"
            }
        }
    )

    storeys: List[StoreyFile] = Field(description="List of generated storey files")
    zip_file: str = Field(description="Name of the ZIP file containing all storeys")