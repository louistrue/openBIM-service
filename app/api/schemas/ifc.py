from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict
from app.core.models.ifc import Element

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

    progress: float = Field(
        description="Processing progress percentage (0-100)"
    )
    processed: int = Field(
        description="Number of processed elements"
    )
    total: int = Field(
        description="Total number of elements to process"
    )
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

    storey_name: str = Field(
        description="Name of the building storey"
    )
    storey_id: str = Field(
        description="IFC Global ID of the storey"
    )
    file_path: str = Field(
        description="Full path to the generated IFC file"
    )
    file_name: str = Field(
        description="Name of the generated IFC file"
    )

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

    storeys: List[StoreyFile] = Field(
        description="List of generated storey files"
    )
    zip_file: str = Field(
        description="Name of the ZIP file containing all storeys"
    ) 