from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "IFC Processing API"
    
    # Add any additional configuration settings here
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_FILE_TYPES: set[str] = {".ifc"}
    
    class Config:
        case_sensitive = True

settings = Settings() 