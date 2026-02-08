"""
Career Cortex - Centralized Configuration Module

This module provides a single source of truth for all configuration settings.
All credentials and settings are loaded from environment variables.
"""

import os
from dataclasses import dataclass
from typing import Optional

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, rely on system environment variables


@dataclass
class Settings:
    """
    Application settings loaded from environment variables.
    
    Usage:
        from config import settings
        db_host = settings.DB_HOST
    """
    
    # Database Configuration
    DB_HOST: str = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "job_agent")
    DB_CHARSET: str = os.getenv("DB_CHARSET", "utf8mb4")
    
    # Ollama/LLM Configuration
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
    OLLAMA_TEMPERATURE: float = float(os.getenv("OLLAMA_TEMPERATURE", "0.0"))
    
    # API Configuration
    API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
    API_PORT: int = int(os.getenv("API_PORT", "5000"))
    API_DEBUG: bool = os.getenv("API_DEBUG", "true").lower() == "true"
    API_URL: str = os.getenv("API_URL", "http://127.0.0.1:5000")
    
    # Scraper Configuration
    CHROME_HEADLESS: bool = os.getenv("CHROME_HEADLESS", "true").lower() == "true"
    SCROLL_PAUSE_TIME: int = int(os.getenv("SCROLL_PAUSE_TIME", "2"))
    MAX_SCROLLS: int = int(os.getenv("MAX_SCROLLS", "20"))
    
    # Cache Configuration
    CACHE_DURATION: int = int(os.getenv("CACHE_DURATION", "300"))
    
    # Pagination Defaults
    DEFAULT_PAGE_SIZE: int = int(os.getenv("DEFAULT_PAGE_SIZE", "20"))
    MAX_PAGE_SIZE: int = int(os.getenv("MAX_PAGE_SIZE", "100"))
    
    def validate(self) -> bool:
        """
        Validate that required settings are configured.
        Returns True if valid, raises ValueError if not.
        """
        if not self.DB_PASSWORD:
            raise ValueError(
                "DB_PASSWORD environment variable is required. "
                "Please create a .env file or set the environment variable."
            )
        return True
    
    def get_db_config(self) -> dict:
        """Get database connection configuration as a dictionary."""
        return {
            "host": self.DB_HOST,
            "port": self.DB_PORT,
            "user": self.DB_USER,
            "password": self.DB_PASSWORD,
            "database": self.DB_NAME,
            "charset": self.DB_CHARSET,
        }


# Global settings instance
settings = Settings()


def get_db_connection():
    """
    Create and return a new database connection using configured settings.
    
    Returns:
        mysql.connector.connection.MySQLConnection: Database connection object
        
    Raises:
        mysql.connector.Error: If connection fails
    """
    import mysql.connector
    
    return mysql.connector.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        charset=settings.DB_CHARSET,
        collation=f"{settings.DB_CHARSET}_unicode_ci"
    )


def check_ollama_connection() -> bool:
    """
    Check if Ollama is running and accessible.
    
    Returns:
        bool: True if Ollama is accessible, False otherwise
    """
    try:
        import ollama
        ollama.list()
        return True
    except Exception:
        return False
