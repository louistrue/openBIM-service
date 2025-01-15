import requests
from pathlib import Path
import os
from dotenv import load_dotenv
import logging
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
API_URL = "http://localhost:8000/api/ifc/extract-building-elements"
CALLBACK_URL = "http://localhost:8001/callback"
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    raise ValueError("API_KEY must be set in .env file")

# Test file path - update this to your IFC file path
TEST_FILE = Path("tests/data/4_DT.ifc")

if not TEST_FILE.exists():
    raise FileNotFoundError(f"Test file not found: {TEST_FILE}")

logger.info("Starting callback test...")

# Prepare headers
headers = {
    "X-API-Key": API_KEY,
    "Accept": "application/json"
}

# Prepare the request
try:
    with open(TEST_FILE, "rb") as f:
        # Create the multipart form-data request
        files = {
            "file": (TEST_FILE.name, f, "application/x-step"),
        }
        
        # Create the multipart encoded form fields
        form = {
            "callback_config.url": CALLBACK_URL,
            "callback_config.token": "test-token"
        }
        
        logger.info(f"Sending request to {API_URL}")
        logger.info(f"Callback URL: {CALLBACK_URL}")
        logger.info(f"Form data: {form}")
        
        # Send request with both files and form fields
        response = requests.post(
            API_URL,
            headers=headers,
            files=files,
            data=form
        )
        
        # Check response
        response.raise_for_status()
        result = response.json()
        
        logger.info(f"Initial response: {result}")
        logger.info("Request sent successfully. Check callback server logs for updates.")

except Exception as e:
    logger.error(f"Error occurred: {str(e)}")
    if hasattr(e, 'response') and hasattr(e.response, 'text'):
        logger.error(f"Response text: {e.response.text}")
    raise 