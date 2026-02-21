import os

import boto3


def _get_r2_client():
    account_id = os.getenv("R2_ACCOUNT_ID")
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")

    if not account_id or not access_key or not secret_key:
        raise RuntimeError("R2 environment variables not configured")

    endpoint = f"https://{account_id}.r2.cloudflarestorage.com"

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )


def upload_file(*args, **kwargs):
    s3 = _get_r2_client()
    return s3.upload_file(*args, **kwargs)
