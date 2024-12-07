import uvicorn
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Current working directory: %s", os.getcwd())
    logger.info("Python path: %s", os.environ.get("PYTHONPATH"))
    
    try:
        # Try importing the app to check for issues
        from app.main import app
        logger.info("Successfully imported app")
        
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except Exception as e:
        logger.error("Failed to start server: %s", str(e), exc_info=True) 