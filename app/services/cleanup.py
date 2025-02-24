import os
import asyncio
import logging
import tempfile
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class TempFileCleanupService:
    def __init__(self, max_file_age_hours: int = 24):
        self.max_file_age = timedelta(hours=max_file_age_hours)
        self.is_running = False
        self.cleanup_interval = timedelta(hours=1)  # Run cleanup every hour
        
    async def start(self):
        """Start the periodic cleanup service"""
        if self.is_running:
            return
            
        self.is_running = True
        while self.is_running:
            try:
                await self.cleanup_temp_files()
            except Exception as e:
                logger.error(f"Error during temp file cleanup: {str(e)}")
            
            # Wait for next cleanup interval
            await asyncio.sleep(self.cleanup_interval.total_seconds())
    
    async def stop(self):
        """Stop the cleanup service"""
        self.is_running = False
    
    async def cleanup_temp_files(self):
        """Clean up temporary files older than max_file_age"""
        temp_dir = tempfile.gettempdir()
        current_time = datetime.now()
        files_removed = 0
        
        logger.info(f"Starting cleanup of temporary files in {temp_dir}")
        
        for filename in os.listdir(temp_dir):
            if not filename.endswith('.ifc'):
                continue
                
            filepath = os.path.join(temp_dir, filename)
            try:
                # Get file stats
                stats = os.stat(filepath)
                last_modified = datetime.fromtimestamp(stats.st_mtime)
                
                # Check if file is older than max age
                if current_time - last_modified > self.max_file_age:
                    os.unlink(filepath)
                    files_removed += 1
                    logger.debug(f"Removed old temporary file: {filepath}")
            except FileNotFoundError:
                # File might have been deleted by another process
                continue
            except Exception as e:
                logger.error(f"Error processing file {filepath}: {str(e)}")
        
        logger.info(f"Cleanup completed. Removed {files_removed} old temporary files") 