import os
from pathlib import Path
from uuid import uuid4

import boto3
from fastapi import UploadFile

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "").strip()
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "").strip()
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "").strip()
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "").rstrip("/")

_r2_client = boto3.client(
    "s3",
    endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name="auto",
)


def upload_file(file: UploadFile, tenant_id: str, folder: str = "storefront") -> str:
    extension = Path(file.filename or "").suffix
    object_key = f"{folder}/{tenant_id}/{uuid4().hex}{extension}"

    file.file.seek(0)
    _r2_client.upload_fileobj(file.file, R2_BUCKET_NAME, object_key)

    return f"{R2_PUBLIC_URL}/{object_key}"
