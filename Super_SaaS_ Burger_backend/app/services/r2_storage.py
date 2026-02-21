import os
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile


def _get_required_env(var_name: str) -> str:
    value = os.getenv(var_name, "").strip()
    if not value:
        raise RuntimeError(f"Variável de ambiente obrigatória ausente: {var_name}")
    return value


def _get_r2_client():
    r2_account_id = _get_required_env("R2_ACCOUNT_ID")
    r2_access_key_id = _get_required_env("R2_ACCESS_KEY_ID")
    r2_secret_access_key = _get_required_env("R2_SECRET_ACCESS_KEY")

    import boto3

    return boto3.client(
        "s3",
        endpoint_url=f"https://{r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=r2_access_key_id,
        aws_secret_access_key=r2_secret_access_key,
        region_name="auto",
    )


def _sanitize_key_part(part: str) -> str:
    return part.strip().strip("/")


def upload_file(
    file: UploadFile,
    tenant_id: str,
    category: str | None = None,
    subfolder: str | None = None,
    folder: str = "storefront",
) -> str:
    r2_bucket_name = _get_required_env("R2_BUCKET_NAME")
    r2_public_url = _get_required_env("R2_PUBLIC_URL").rstrip("/")

    tenant_key = _sanitize_key_part(tenant_id)
    category_key = _sanitize_key_part(category or folder)
    subfolder_key = _sanitize_key_part(subfolder) if subfolder else ""

    extension = Path(file.filename or "").suffix
    uuid_filename = f"{uuid4().hex}{extension}"
    key_parts = ["tenants", tenant_key, category_key]
    if subfolder_key:
        key_parts.append(subfolder_key)
    key_parts.append(uuid_filename)
    object_key = "/".join(key_parts)

    file.file.seek(0)
    _get_r2_client().upload_fileobj(file.file, r2_bucket_name, object_key)

    return f"{r2_public_url}/{object_key}"
