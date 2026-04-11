"""Cloudflare R2 storage client (S3-compatible API).

Provides upload, delete, and URL generation for video files.
Gracefully degrades when R2 credentials are not configured.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class R2Client:
    """S3-compatible client for Cloudflare R2.

    Lifecycle:
        - Call ``R2Client.create()`` classmethod -- returns None if unconfigured.
        - Use ``upload_file()``, ``delete_object()``, ``get_public_url()``.
    """

    def __init__(
        self,
        bucket_name: str,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        public_url: str | None = None,
    ) -> None:
        import boto3

        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )
        self._bucket = bucket_name
        # User-supplied public URL (e.g. custom CDN domain).
        # If not set, callers should use the R2 default public URL pattern.
        self._public_url = (public_url or "").rstrip("/")

    @classmethod
    def create(cls) -> "R2Client | None":
        """Factory: return configured client, or None if env vars missing.

        Checks for the presence of all required environment variables.
        Returns None so callers can trivially fall back to local mode.
        """
        bucket = os.environ.get("R2_BUCKET_NAME")
        account_id = os.environ.get("R2_ACCOUNT_ID")
        key_id = os.environ.get("R2_ACCESS_KEY_ID")
        secret = os.environ.get("R2_SECRET_ACCESS_KEY")
        public_url = os.environ.get("R2_PUBLIC_URL")

        if not all([bucket, account_id, key_id, secret]):
            logger.info(
                "R2 not fully configured (missing one of: "
                "R2_BUCKET_NAME, R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
                "R2_SECRET_ACCESS_KEY). Local-only mode.",
            )
            return None

        try:
            import boto3  # noqa: F401
        except ImportError:
            logger.warning("boto3 not installed; R2 storage unavailable.")
            return None

        return cls(
            bucket_name=bucket,
            account_id=account_id,
            access_key_id=key_id,
            secret_access_key=secret,
            public_url=public_url,
        )

    @property
    def is_configured(self) -> bool:
        return True  # instances are always configured (None otherwise)

    def get_public_url(self, object_key: str) -> str:
        """Return the publicly accessible URL for an R2 object."""
        if self._public_url:
            return f"{self._public_url}/{object_key}"
        # Fallback: standard R2 public bucket URL pattern
        return (
            f"https://pub-{self._account_id}.{self._bucket}.r2.dev"
            f"/{object_key}"
        )

    @property
    def _account_id(self) -> str:
        """Extract account ID from the S3 client config."""
        return self._s3._client_config._user_provided_options.get(
            "endpoint_url",
            "",
        ).split("//")[-1].split(".")[0]

    @property
    def _bucket_display(self) -> str:
        return self._bucket

    def upload_file(self, file_path: str | Path, object_key: str) -> str:
        """Upload a local file to R2. Returns the public URL.

        Args:
            file_path: Absolute path to the local file.
            object_key: S3 object key (e.g. ``videos/abc12345/final.mp4``).

        Raises:
            botocore.exceptions.BotoCoreError: on upload failure.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(
                f"File not found for upload: {file_path}"
            )

        self._s3.upload_file(
            str(path),
            Bucket=self._bucket,
            Key=object_key,
            ExtraArgs={
                "ContentType": "video/mp4",
                "CacheControl": "public, max-age=31536000",
            },
        )
        url = self.get_public_url(object_key)
        logger.info(
            "Uploaded %s -> %s (%d bytes)",
            object_key,
            url,
            path.stat().st_size,
        )
        return url

    def delete_object(self, object_key: str) -> None:
        """Delete an object from R2. Logs but does not raise on failure."""
        try:
            self._s3.delete_object(Bucket=self._bucket, Key=object_key)
            logger.info("Deleted R2 object: %s", object_key)
        except Exception as exc:
            logger.warning("Failed to delete R2 object %s: %s", object_key, exc)

    def object_exists(self, object_key: str) -> bool:
        """Check whether an object exists in R2."""
        try:
            self._s3.head_object(Bucket=self._bucket, Key=object_key)
            return True
        except Exception:
            return False


def is_r2_url(value: str | None) -> bool:
    """Return True if *value* looks like an http(s) URL (i.e. R2 public URL).

    Used by routes.py to decide between redirect vs FileResponse.
    """
    if not value:
        return False
    return value.startswith("http://") or value.startswith("https://")


def r2_object_key(task_id: str) -> str:
    """Return the canonical R2 object key for a task's video.

    Pattern: ``videos/{task_id}/final.mp4``
    This keeps objects organized and makes cleanup straightforward.
    """
    return f"videos/{task_id}/final.mp4"
