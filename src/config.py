import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Config
    APP_NAME: str = "Audit Pit-Crew"
    ENV: str = "development"
    
    # GitHub Config
    GITHUB_APP_ID: str
    GITHUB_PRIVATE_KEY: str
    GITHUB_WEBHOOK_SECRET: str
    
    # Worker Config
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Security: Default scan timeout
    MAX_SCAN_TIME_SECONDS: int = 300
    
    class Config:
        # This tells Pydantic to look for the .env file in the root directory
        env_file = ".env"
        env_file_encoding = 'utf-8'

# Create a global settings object
settings = Settings()
