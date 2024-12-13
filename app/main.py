from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.ifc_routes import router
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
from typing import Dict, Any
from app.middleware.api_key import api_key_middleware
import os
import tempfile
from datetime import datetime, timedelta
import asyncio
import logging

logger = logging.getLogger(__name__)

# Define schemas for request/response models
class HTTPValidationError(BaseModel):
    detail: str

class ValidationError(BaseModel):
    loc: list[str]
    msg: str
    type: str

app = FastAPI(
    title="IFC Processing API",
    description="API for processing IFC files with various operations",
    version="0.0.1",
    swagger_ui_parameters={"persistAuthorization": True}
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add this after the CORS middleware
app.middleware("http")(api_key_middleware)

# File upload limit
app.state.max_upload_size = 1024 * 1024 * 1024  # 1GB

# Include routes
app.include_router(router, prefix="/api/ifc", tags=["IFC Processing"])

# Modified cleanup function
async def cleanup_old_files():
    """Clean up files older than 1 hour"""
    while True:
        try:
            temp_dir = tempfile.gettempdir()
            threshold = datetime.now() - timedelta(hours=1)
            
            for filename in os.listdir(temp_dir):
                filepath = os.path.join(temp_dir, filename)
                try:
                    # Check if file is older than threshold
                    if os.path.getctime(filepath) < threshold.timestamp():
                        if filename.endswith('.ifc') or filename.endswith('.zip'):
                            os.unlink(filepath)
                            logger.info(f"Cleaned up old file: {filepath}")
                except Exception as e:
                    logger.error(f"Error cleaning up {filepath}: {str(e)}")
                    
            # Wait for an hour before next cleanup
            await asyncio.sleep(3600)  # 1 hour in seconds
        except Exception as e:
            logger.error(f"Error in cleanup task: {str(e)}")
            await asyncio.sleep(60)  # Wait a minute before retrying if there's an error

@app.on_event("startup")
async def start_cleanup_task():
    """Start the background cleanup task"""
    asyncio.create_task(cleanup_old_files())

# Customize OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add components section with schemas
    openapi_schema["components"] = {
        "schemas": {
            "HTTPValidationError": {
                "title": "HTTPValidationError",
                "type": "object",
                "properties": {
                    "detail": {
                        "title": "Detail",
                        "type": "string"
                    }
                }
            },
            "ValidationError": {
                "title": "ValidationError",
                "type": "object",
                "properties": {
                    "loc": {
                        "title": "Location",
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "msg": {
                        "title": "Message",
                        "type": "string"
                    },
                    "type": {
                        "title": "Error Type",
                        "type": "string"
                    }
                }
            },
            "MultipartFormData": {
                "title": "File Upload",
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "format": "binary",
                        "title": "File"
                    }
                }
            }
        }
    }
    
    # Fix file upload schema references
    for path in openapi_schema["paths"].values():
        for operation in path.values():
            if "requestBody" in operation:
                content = operation["requestBody"].get("content", {})
                if "multipart/form-data" in content:
                    content["multipart/form-data"]["schema"] = {
                        "$ref": "#/components/schemas/MultipartFormData"
                    }
            
            # Fix validation error schema references
            if "responses" in operation:
                if "422" in operation["responses"]:
                    operation["responses"]["422"]["content"] = {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/HTTPValidationError"
                            }
                        }
                    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi