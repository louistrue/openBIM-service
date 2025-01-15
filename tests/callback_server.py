from fastapi import FastAPI, Request
import uvicorn
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.post("/callback")
async def callback(request: Request):
    # Get authorization header
    auth_token = request.headers.get("Authorization")
    
    # Get callback data
    data = await request.json()
    
    # Log the received data
    logger.info(f"Received callback at {datetime.now().isoformat()}")
    logger.info(f"Authorization token: {auth_token}")
    logger.info(f"Data: {data}")
    
    return {"status": "received"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001) 