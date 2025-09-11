"""Storage factory for creating storage instances based on environment."""

import logging
from typing import Union
from enum import Enum

from .base import SessionStorage
from .mock_storage import MockSessionStorage
from .dynamodb_storage import DynamoDBSessionStorage
from ..config import settings

logger = logging.getLogger(__name__)


class StorageType(str, Enum):
    """Storage type enumeration."""
    MOCK = "mock"
    DYNAMODB = "dynamodb"
    LOCAL = "local"  # Alias for mock


class StorageFactory:
    """Factory for creating storage instances."""
    
    @staticmethod
    def create_storage(storage_type: str = None) -> SessionStorage:
        """
        Create a storage instance based on the specified type.
        
        Args:
            storage_type: Type of storage to create. If None, uses settings.storage_type
            
        Returns:
            SessionStorage instance
            
        Raises:
            ValueError: If storage_type is not supported
        """
        if storage_type is None:
            storage_type = settings.storage_type
        
        storage_type = storage_type.lower()
        
        logger.info(f"Creating storage instance of type: {storage_type}")
        
        if storage_type in [StorageType.MOCK, StorageType.LOCAL]:
            logger.info("Using MockSessionStorage for local development")
            return MockSessionStorage()
            
        elif storage_type == StorageType.DYNAMODB:
            logger.info("Using DynamoDBSessionStorage for production")
            return DynamoDBSessionStorage()
            
        else:
            raise ValueError(f"Unsupported storage type: {storage_type}. "
                           f"Supported types: {[t.value for t in StorageType]}")
    
    @staticmethod
    def get_available_storage_types() -> list[str]:
        """Get list of available storage types."""
        return [t.value for t in StorageType]
    
    @staticmethod
    def validate_storage_config(storage_type: str) -> bool:
        """
        Validate that the storage configuration is correct.
        
        Args:
            storage_type: Type of storage to validate
            
        Returns:
            bool: True if configuration is valid, False otherwise
        """
        storage_type = storage_type.lower()
        
        if storage_type == StorageType.DYNAMODB:
            # Check required DynamoDB settings
            required_settings = [
                'dynamodb_table_name',
                'dynamodb_region'
            ]
            
            missing_settings = []
            for setting in required_settings:
                if not getattr(settings, setting, None):
                    missing_settings.append(setting)
            
            if missing_settings:
                logger.error(f"Missing required DynamoDB settings: {missing_settings}")
                return False
            
            # Check if AWS credentials are available
            if not (settings.aws_access_key_id and settings.aws_secret_access_key):
                logger.warning("AWS credentials not provided. Will use default credential chain.")
            
            return True
            
        elif storage_type in [StorageType.MOCK, StorageType.LOCAL]:
            # Mock storage doesn't require additional configuration
            return True
            
        else:
            logger.error(f"Unknown storage type: {storage_type}")
            return False
