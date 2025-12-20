"""
Configuration management using environment variables.
Loads from .env file if present.
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)


class Settings:
    """
    Application settings loaded from environment variables.
    """
    
    # Discord Bot Settings
    DISCORD_TOKEN: str = os.getenv("BOT_TOKEN", "")
    PREFIX: str = os.getenv("PREFIX", "!")
    
    # qBittorrent Settings (optional)
    QBIT_HOST: Optional[str] = os.getenv("QBIT_HOST", None)
    QBIT_USERNAME: Optional[str] = os.getenv("QBIT_USERNAME", None)
    QBIT_PASSWORD: Optional[str] = os.getenv("QBIT_PASSWORD", None)
    QBIT_CONTAINER_NAME: str = os.getenv("QBIT_CONTAINER_NAME", "qbittorrent")
    
    # Add more service configurations here as needed
    # Example:
    # SOME_SERVICE_API_KEY: Optional[str] = os.getenv("SOME_SERVICE_API_KEY", None)
    
    def validate(self):
        """Validate required settings."""
        if not self.DISCORD_TOKEN:
            raise ValueError("BOT_TOKEN is required in environment variables or .env file")


# Create settings instance
settings = Settings()

# Validate on import
try:
    settings.validate()
except ValueError as e:
    print(f"Warning: {e}")


# For backward compatibility
BOT_TOKEN = settings.DISCORD_TOKEN
