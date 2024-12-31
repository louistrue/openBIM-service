from typing import List, Set
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "IFC Processing API"
    
    # Add any additional configuration settings here
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_FILE_TYPES: Set[str] = {".ifc"}
    
    # API Key settings
    API_KEY: str  # Single key for tests
    API_USER_KEYS: List[str] = []  # List of valid user keys
    
    # PostHog settings
    POSTHOG_API_KEY: str
    POSTHOG_HOST: str = "https://us.i.posthog.com"
    
    class Config:
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()