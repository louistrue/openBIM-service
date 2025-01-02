from fastapi import Request
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv
import logging
from starlette.status import HTTP_401_UNAUTHORIZED
from ..core.analytics import capture_event
import uuid
import sys

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)

# Get API keys from environment
API_USER_KEYS = os.getenv("API_USER_KEYS", "[]")
if isinstance(API_USER_KEYS, str):
    import json
    try:
        API_USER_KEYS = json.loads(API_USER_KEYS)
    except json.JSONDecodeError:
        API_USER_KEYS = []

def is_swagger_request(request: Request, referer: str) -> bool:
    """Determine if request is coming from Swagger UI"""
    swagger_paths = [
        "/docs",
        "/redoc", 
        "/openapi.json",
        "/favicon.ico",
        "/docs/oauth2-redirect",
        "/docs/swagger-ui-bundle.js",
        "/docs/swagger-ui.css",
        "/docs/swagger-ui-standalone-preset.js"
    ]
    return any(request.url.path.endswith(path) for path in swagger_paths) or "/docs" in referer

async def api_key_middleware(request: Request, call_next):
    # Get request details
    full_path = request.url.path
    base_url = str(request.base_url).rstrip('/')
    referer = request.headers.get("referer", "unknown")
    user_agent = request.headers.get("user-agent", "unknown")
    api_key = request.headers.get("X-API-Key", "")
    
    # Determine request type
    is_docs = is_swagger_request(request, referer)
    is_api_call = not is_docs and full_path.startswith("/api")
    
    # Generate a consistent ID for API users based on their API key
    if api_key and not is_docs:
        # Use first and last 4 chars of API key as distinct_id
        distinct_id = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else api_key
    else:
        # For Swagger UI or anonymous users, generate UUID
        distinct_id = str(uuid.uuid4())

    # Prepare analytics properties
    properties = {
        # Event properties (these will show up in PostHog)
        'event_type': 'api_request',
        'is_api_call': is_api_call,
        'is_swagger_ui': is_docs,
        'endpoint': full_path.split('?')[0],  # Remove query parameters
        'request_method': request.method,
        'api_key_prefix': api_key[:4] if api_key and not is_docs else None,
        'api_key_suffix': api_key[-4:] if api_key and not is_docs else None,
        
        # PostHog standard properties (prefixed with $)
        '$current_url': str(request.url),
        '$host': base_url,
        '$browser': user_agent,
        '$os': sys.platform,
        '$pathname': full_path,
        
        # Additional context
        'client_ip': request.client.host if request.client else 'unknown',
        'environment': 'development',
        'referer': referer,
        'user_agent': user_agent
    }
    
    try:
        # Use capture_event directly instead of capture_pageview since we want a custom event name
        capture_event(
            distinct_id=distinct_id,
            event_name='api_request',
            properties={
                '$current_url': str(request.url),
                **properties  # Include all our custom properties
            }
        )
    except Exception as e:
        logger.error(f"Failed to capture analytics: {e}", exc_info=True)
    
    # Allow Swagger UI access without API key
    if is_docs:
        return await call_next(request)
    
    # For API endpoints, require valid API key
    if full_path.startswith("/api"):
        if not api_key:
            return JSONResponse(
                status_code=HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or missing API Key"}
            )
            
        if api_key not in API_USER_KEYS:
            return JSONResponse(
                status_code=HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or missing API Key"}
            )
    
    return await call_next(request) 