from functools import lru_cache

import boto3
from botocore.config import Config

from app.core.config import settings


@lru_cache
def get_s3_client():
    if not all(
        [
            settings.b2_key_id,
            settings.b2_application_key,
            settings.b2_bucket_name,
            settings.b2_endpoint_url,
        ]
    ):
        raise RuntimeError("Backblaze B2 configuration is incomplete")

    return boto3.client(
        "s3",
        endpoint_url=settings.b2_endpoint_url,
        aws_access_key_id=settings.b2_key_id,
        aws_secret_access_key=(
            settings.b2_application_key.get_secret_value()
        ),
        config=Config(
            signature_version="s3v4",
        ),
        region_name=settings.b2_region,
    )


def upload_file(
    file_object,
    object_key: str,
    content_type: str = "application/pdf",
) -> None:
    client = get_s3_client()

    client.upload_fileobj(
        file_object,
        settings.b2_bucket_name,
        object_key,
        ExtraArgs={
            "ContentType": content_type,
        },
    )


def download_file(object_key: str):
    client = get_s3_client()

    response = client.get_object(
        Bucket=settings.b2_bucket_name,
        Key=object_key,
    )

    return response["Body"]


def delete_file(object_key: str) -> None:
    client = get_s3_client()

    client.delete_object(
        Bucket=settings.b2_bucket_name,
        Key=object_key,
    )
