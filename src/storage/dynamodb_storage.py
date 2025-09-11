"""DynamoDB storage implementation for session management."""

import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError

from .base import SessionStorage
from src.models import SessionCookie
from src.config import settings

logger = logging.getLogger(__name__)


class DynamoDBSessionStorage(SessionStorage):
    """DynamoDB implementation of session storage."""

    def __init__(self):
        self.table_name = settings.dynamodb_table_name
        self.region = settings.dynamodb_region
        
        # Initialize DynamoDB client
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            self.dynamodb = boto3.resource(
                'dynamodb',
                region_name=self.region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key
            )
        else:
            # Use default credentials (IAM role, environment, etc.)
            self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
        
        self.table = self.dynamodb.Table(self.table_name)

    async def store_session(
        self, 
        session_id: str, 
        provider: str, 
        cookies: List[SessionCookie],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store session data in DynamoDB."""
        try:
            # Convert cookies to serializable format
            cookies_data = []
            for cookie in cookies:
                cookies_data.append({
                    'name': cookie.name,
                    'value': cookie.value,
                    'domain': cookie.domain,
                    'path': cookie.path,
                    'secure': cookie.secure,
                    'http_only': cookie.http_only
                })

            # Calculate TTL (Time To Live) for DynamoDB
            ttl = int((datetime.utcnow() + timedelta(minutes=settings.session_timeout_minutes)).timestamp())

            item = {
                'session_id': session_id,
                'provider': provider,
                'cookies': cookies_data,
                'metadata': metadata or {},
                'created_at': datetime.utcnow().isoformat(),
                'last_accessed': datetime.utcnow().isoformat(),
                'ttl': ttl
            }

            self.table.put_item(Item=item)
            logger.info(f"Session {session_id} stored successfully in DynamoDB")
            return True

        except ClientError as e:
            logger.error(f"Failed to store session {session_id} in DynamoDB: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error storing session {session_id}: {e}")
            return False

    async def get_session(
        self, 
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve session data from DynamoDB."""
        try:
            response = self.table.get_item(Key={'session_id': session_id})
            
            if 'Item' not in response:
                logger.info(f"Session {session_id} not found in DynamoDB")
                return None

            item = response['Item']
            
            # Update last accessed time
            item['last_accessed'] = datetime.utcnow().isoformat()
            self.table.put_item(Item=item)
            
            logger.info(f"Session {session_id} retrieved successfully from DynamoDB")
            return item

        except ClientError as e:
            logger.error(f"Failed to retrieve session {session_id} from DynamoDB: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving session {session_id}: {e}")
            return None

    async def list_active_sessions(
        self, 
        provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List active sessions from DynamoDB."""
        try:
            if provider:
                # Query by provider using GSI (Global Secondary Index)
                response = self.table.query(
                    IndexName='provider-index',  # Assumes GSI exists
                    KeyConditionExpression='provider = :provider',
                    ExpressionAttributeValues={':provider': provider}
                )
            else:
                # Scan all items (expensive operation)
                response = self.table.scan()

            sessions = response.get('Items', [])
            
            # Filter out expired sessions
            current_time = datetime.utcnow()
            active_sessions = []
            
            for session in sessions:
                try:
                    last_accessed = datetime.fromisoformat(session['last_accessed'])
                    if current_time - last_accessed < timedelta(minutes=settings.session_timeout_minutes):
                        active_sessions.append(session)
                except (KeyError, ValueError):
                    # Skip sessions with invalid timestamps
                    continue

            logger.info(f"Found {len(active_sessions)} active sessions")
            return active_sessions

        except ClientError as e:
            logger.error(f"Failed to list sessions from DynamoDB: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing sessions: {e}")
            return []

    async def delete_session(
        self, 
        session_id: str
    ) -> bool:
        """Delete session data from DynamoDB."""
        try:
            self.table.delete_item(Key={'session_id': session_id})
            logger.info(f"Session {session_id} deleted successfully from DynamoDB")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete session {session_id} from DynamoDB: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting session {session_id}: {e}")
            return False

    async def is_session_valid(
        self, 
        session_id: str
    ) -> bool:
        """Check if session is still valid."""
        session_data = await self.get_session(session_id)
        if not session_data:
            return False

        try:
            last_accessed = datetime.fromisoformat(session_data['last_accessed'])
            current_time = datetime.utcnow()
            return current_time - last_accessed < timedelta(minutes=settings.session_timeout_minutes)
        except (KeyError, ValueError):
            return False
