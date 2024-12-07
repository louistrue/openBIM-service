from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.ifc_routes import router

app = FastAPI(
    title="IFC Processing API",
    description="API for processing IFC files with various operations",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router, prefix="/api/ifc", tags=["IFC Processing"]) 