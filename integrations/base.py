"""
Base integration class that all service integrations should inherit from.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from core.errors import IntegrationError


class BaseIntegration(ABC):
    """
    Abstract base class for all service integrations.
    
    All integrations should inherit from this class and implement
    the required methods.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the integration with configuration.
        
        Args:
            config: Dictionary containing configuration for the integration
        """
        self.config = config
        self._connected = False
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the integration."""
        pass
    
    @property
    def is_connected(self) -> bool:
        """Check if the integration is currently connected."""
        return self._connected
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the service.
        
        Returns:
            True if connection successful, False otherwise
            
        Raises:
            IntegrationError: If connection fails
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        Disconnect from the service.
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the service is healthy and accessible.
        
        Returns:
            True if service is healthy, False otherwise
        """
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the integration.
        
        Returns:
            Dictionary containing status information
        """
        return {
            "name": self.name,
            "connected": self.is_connected,
            "config_loaded": self.config is not None
        }

