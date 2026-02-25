from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "quanlykeyveo3-api"
    API_V1_STR: str = "/api/v1"
    
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Supabase / DB
    DATABASE_URL: str
    
    # License Keys
    JWT_PRIVATE_KEY: str
    JWT_PUBLIC_KEY: str
    
    # System Config
    MIN_VERSION: str = "1.0.0"
    MAINTENANCE_MODE: bool = False
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
