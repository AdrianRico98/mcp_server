from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    # MCP Server Configuration
    mcp_server_port: int = 8000
    mcp_server_host: str = "localhost"
    
    # FastAPI Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    api_title: str = "MCP Client API"
    api_description: str = "API para interactuar con el servidor MCP de gestión de archivos"
    api_version: str = "1.0.0"
    
    # LLM Configuration
    model_id: str = "gemini-2.5-flash"
    gemini_token: str = os.getenv("GEMINI_TOKEN", "")
    
    # Session Configuration
    max_sessions: int = 100
    session_timeout_minutes: int = 60
    
    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # CORS Configuration
    cors_origins: list = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list = ["*"]
    cors_allow_headers: list = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Instancia global de configuración
settings = Settings()