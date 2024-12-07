import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import os
from dotenv import load_dotenv
import logging
from pathlib import Path
import time
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_session():
    session = requests.Session()
    
    # Configure retries
    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[502, 503, 504],
        allowed_methods=["POST"]
    )
    
    # Configure adapter with longer timeouts
    adapter = HTTPAdapter(
        max_retries=retries,
        pool_connections=1,
        pool_maxsize=1,
        pool_block=True
    )
    
    session.mount('https://', adapter)
    session.verify = False  # Disable SSL verification
    return session

# Load environment variables
env_path = Path('.env')
load_dotenv(verbose=True)

# Configuration
API_URL = "https://openbim-service-production.up.railway.app/api/ifc/process"
API_KEY = os.getenv("API_KEY")
TEST_FILE = "tests/data/CBB-F10-kBP.ifc"

if not API_KEY:
    raise ValueError("API_KEY must be set in .env file")

logger.info("Starting IFC processing test...")

headers = {
    "X-API-Key": API_KEY,
    "Accept": "application/x-ndjson"
}

session = create_session()

try:
    logger.info("Sending request to API...")
    with open(TEST_FILE, "rb") as f:
        files = {
            "file": (os.path.basename(TEST_FILE), f, "application/x-step")
        }
        
        response = session.post(
            API_URL,
            headers=headers,
            files=files,
            timeout=300  # 5 minutes timeout
        )
        response.raise_for_status()
        
        output_dir = Path("tests/output")
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"api_response_{os.path.basename(TEST_FILE)}.jsonl"
        
        last_logged_progress = 0
        with open(output_file, "w", encoding="utf-8") as out_f:
            for line in response.iter_lines():
                if line:
                    data = json.loads(line.decode('utf-8'))
                    out_f.write(json.dumps(data) + "\n")
                    
                    if data["status"] == "complete":
                        logger.info("✅ Processing complete!")
                        logger.info(f"📊 Processed {len(data.get('elements', []))} elements")
                        logger.info(f"💾 Results saved to: {output_file}")
                    elif data["status"] == "processing":
                        current_progress = int(data.get('progress', 0))
                        if current_progress >= last_logged_progress + 10:
                            logger.info(f"⏳ Processing: {current_progress}%")
                            last_logged_progress = current_progress

except requests.exceptions.RequestException as e:
    logger.error(f"❌ API request failed: {str(e)}")
    if hasattr(e, 'response') and e.response is not None:
        logger.error(f"Response: {e.response.text}")
except Exception as e:
    logger.error(f"❌ Script error: {str(e)}") 