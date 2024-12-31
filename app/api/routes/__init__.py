from fastapi import APIRouter
from .ifc import router as ifc_router

router = APIRouter()
router.include_router(ifc_router, prefix="/ifc")
