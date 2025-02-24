from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from .middleware.api_key import api_key_middleware
from .core import analytics
from .services.cleanup import TempFileCleanupService
import asyncio

app = FastAPI(
    title="IFC Service API",
    description="REST API for processing IFC files",
    version="0.0.2",
    openapi_version="3.1.0"
)

# Initialize cleanup service
cleanup_service = TempFileCleanupService(max_file_age_hours=24)

@app.on_event("startup")
async def startup_event():
    # Start cleanup service
    asyncio.create_task(cleanup_service.start())
    
    # Initialize analytics
    print("Initializing analytics...")
    if analytics.posthog is None:
        print("Failed to initialize PostHog!")
    else:
        print("PostHog initialized successfully")

@app.on_event("shutdown")
async def shutdown_event():
    # Stop cleanup service
    await cleanup_service.stop()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add middleware
app.middleware("http")(api_key_middleware)

# Include the router
app.include_router(router, prefix="/api")