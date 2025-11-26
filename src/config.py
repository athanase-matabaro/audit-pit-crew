import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Pydantic V2 configuration options
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        # FIX 1: Allows environment variables not defined in this model (like the old GITHUB_PRIVATE_KEY) to be ignored.
        extra='ignore', 
        case_sensitive=False
    )
    
    # App Config
    APP_NAME: str = "Audit Pit-Crew"
    ENV: str = "development"
    
    # GitHub Config
    GITHUB_APP_ID: str
    # This expects the file path to the .pem key
    GITHUB_PRIVATE_KEY_PATH: str 
    GITHUB_WEBHOOK_SECRET: str
    
    # Worker Config
    # FIX 2: Use the Docker service name 'redis' instead of 'localhost'
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Security: Default scan timeout
    MAX_SCAN_TIME_SECONDS: int = 300

# Create a global settings object
settings = Settings()
