"""S3-compatible object storage abstraction."""

from __future__ import annotations

import asyncio
import io
from pathlib import Path
from typing import BinaryIO

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from .config import settings
from .instrumentation import get_logger

logger = get_logger()


class S3Storage:
    """S3-compatible object storage client."""
    
    def __init__(self):
        self.client = None
        self.bucket_name = settings.s3_bucket_name
        
        if BOTO3_AVAILABLE and settings.s3_access_key and settings.s3_secret_key:
            self._initialize_client()
    
    def _initialize_client(self):
        """Initialize S3 client with credentials."""
        session_kwargs = {
            "aws_access_key_id": settings.s3_access_key,
            "aws_secret_access_key": settings.s3_secret_key,
            "region_name": settings.s3_region,
        }
        
        session = boto3.Session(**session_kwargs)
        
        client_kwargs = {}
        if settings.s3_endpoint_url:
            client_kwargs["endpoint_url"] = settings.s3_endpoint_url
        
        self.client = session.client("s3", **client_kwargs)
        
        # Ensure bucket exists
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"S3 bucket '{self.bucket_name}' connected successfully")
        except ClientError:
            logger.warning(f"S3 bucket '{self.bucket_name}' not accessible, creating...")
            try:
                self.client.create_bucket(Bucket=self.bucket_name)
                logger.info(f"S3 bucket '{self.bucket_name}' created")
            except Exception as e:
                logger.error(f"Failed to create S3 bucket: {e}")
    
    def is_available(self) -> bool:
        """Check if S3 storage is available."""
        return self.client is not None
    
    async def upload_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload bytes to S3.
        
        Returns:
            str: S3 URL or local path if S3 not available
        """
        if not self.is_available():
            logger.warning("S3 not configured, falling back to local storage")
            return self._save_local(key, data)
        
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=data,
                    ContentType=content_type,
                )
            )
            
            url = f"s3://{self.bucket_name}/{key}"
            logger.info(f"Uploaded to S3: {url}")
            return url
            
        except Exception as e:
            logger.error(f"S3 upload failed: {e}, falling back to local")
            return self._save_local(key, data)
    
    async def upload_file(self, key: str, file_path: Path, content_type: str = "application/octet-stream") -> str:
        """Upload file to S3."""
        with open(file_path, "rb") as f:
            data = f.read()
        return await self.upload_bytes(key, data, content_type)
    
    async def download_bytes(self, key: str) -> bytes:
        """Download bytes from S3."""
        if not self.is_available():
            raise RuntimeError("S3 not configured")
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.get_object(Bucket=self.bucket_name, Key=key)
            )
            return response["Body"].read()
        except ClientError as e:
            logger.error(f"S3 download failed: {e}")
            raise
    
    async def download_to_file(self, key: str, file_path: Path):
        """Download S3 object to file."""
        data = await self.download_bytes(key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)
    
    async def delete(self, key: str):
        """Delete object from S3."""
        if not self.is_available():
            return
        
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.client.delete_object(Bucket=self.bucket_name, Key=key)
            )
            logger.info(f"Deleted from S3: {key}")
        except Exception as e:
            logger.error(f"S3 delete failed: {e}")
    
    async def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate presigned URL for temporary access.
        
        Args:
            key: S3 object key
            expires_in: URL expiration in seconds
            
        Returns:
            str: Presigned URL
        """
        if not self.is_available():
            raise RuntimeError("S3 not configured")
        
        try:
            loop = asyncio.get_event_loop()
            url = await loop.run_in_executor(
                None,
                lambda: self.client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": key},
                    ExpiresIn=expires_in,
                )
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise
    
    def _save_local(self, key: str, data: bytes) -> str:
        """Fallback to local file storage."""
        local_path = Path("artifacts") / key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(data)
        return str(local_path)


# Global instance
s3_storage = S3Storage()
