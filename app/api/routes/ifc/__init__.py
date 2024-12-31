from fastapi import APIRouter
from . import process, split_by_storey, property_values, elements_info, geometry, extract_elements

router = APIRouter()

# Include all the route modules
router.include_router(process.router, tags=["IFC Processing"])
router.include_router(split_by_storey.router, tags=["IFC Processing"])
router.include_router(property_values.router, tags=["IFC Processing"])
router.include_router(elements_info.router, tags=["IFC Processing"])
router.include_router(geometry.router, tags=["IFC Processing"])
router.include_router(extract_elements.router, tags=["IFC Processing"]) 