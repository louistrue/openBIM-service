from pydantic import BaseModel, Field
from typing import List, Optional, Union

class PropertyValue(BaseModel):
    """Property value information for an element"""
    guid: str = Field(..., description="Global ID of the element")
    value: Optional[Union[str, float, int, bool]] = Field(None, description="Property value")
    data_type: str = Field(..., description="IFC data type of the value")

class PropertyValuesResponse(BaseModel):
    """Response model for property values query"""
    values: List[PropertyValue] = Field(..., description="List of property values")
    total_elements: int = Field(..., description="Total number of elements found")