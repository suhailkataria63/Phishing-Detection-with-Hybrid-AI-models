from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "phish-detector-api"
    cors_allow_origins: str = "http://localhost:3000"

settings = Settings()
