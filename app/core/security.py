from fastapi import Security, HTTPException, Depends, Request
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_429_TOO_MANY_REQUESTS, HTTP_401_UNAUTHORIZED
from .config import settings
import time
from collections import defaultdict
from typing import Dict, Tuple

# Rate limiting settings
RATE_LIMIT_DURATION = 60  # seconds
MAX_ATTEMPTS = 10  # maximum attempts per duration

# Store for rate limiting
# Format: {ip_address: (number_of_attempts, start_time)}
rate_limit_store: Dict[str, Tuple[int, float]] = defaultdict(lambda: (0, 0.0))

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_client_ip(request: Request) -> str:
    # For testing environments, return a default IP
    if request.client is None:
        return "test-client"
    return request.client.host

def check_rate_limit(ip_address: str) -> None:
    attempts, start_time = rate_limit_store[ip_address]
    current_time = time.time()
    
    # Reset rate limit if duration has passed
    if current_time - start_time >= RATE_LIMIT_DURATION:
        rate_limit_store[ip_address] = (1, current_time)
        return
    
    # Check if too many attempts
    if attempts >= MAX_ATTEMPTS:
        time_remaining = int(RATE_LIMIT_DURATION - (current_time - start_time))
        raise HTTPException(
            status_code=HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many authentication attempts. Please try again in {time_remaining} seconds"
        )
    
    # Increment attempts
    rate_limit_store[ip_address] = (attempts + 1, start_time)

async def get_api_key(
    request: Request,
    api_key_header: str = Security(api_key_header)
):
    # Get client IP and check rate limit
    client_ip = get_client_ip(request)
    check_rate_limit(client_ip)
    
    if not api_key_header or api_key_header not in settings.API_USER_KEYS:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key"
        )
    return api_key_header 