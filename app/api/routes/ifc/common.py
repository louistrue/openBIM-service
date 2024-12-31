from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from typing import List, Optional, Annotated

# Shared utility functions
def _round_value(value: float, digits: int = 3) -> float:
    """Round float value to specified number of digits."""
    if isinstance(value, (int, float)):
        return round(value, digits)
    return value

# Shared dependencies
async def get_ifc_classes(
    enable_filter: Annotated[bool, Query(description="Enable filtering by IFC classes")] = False,
    ifc_classes: Optional[List[str]] = Query(
        default=None,
        description="IFC classes to include when filtering is enabled. Add multiple values by clicking '+' below.",
        example=["IfcWall", "IfcSlab"],
    )
) -> Optional[List[str]]:
    """Filter IFC classes. Enable filtering first, then add one or more IFC classes."""
    if not enable_filter:
        return None
        
    if not ifc_classes:
        return None
        
    # Clean up each class name
    cleaned_classes = []
    for cls in ifc_classes:
        # Remove "List [", "]" and clean up quotes and spaces
        cls = cls.replace("List [", "").replace("]", "").strip().strip('"\'')
        if cls:  # Only add non-empty strings
            cleaned_classes.append(cls)
    return cleaned_classes if cleaned_classes else None 