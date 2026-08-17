from minio import Minio
from minio.deleteobjects import DeleteObject

from app.config import settings

minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE,
)

BUCKET_NAME = settings.MINIO_BUCKET


def ensure_bucket() -> None:
    if not minio_client.bucket_exists(BUCKET_NAME):
        minio_client.make_bucket(BUCKET_NAME)


def delete_object(object_key: str) -> None:
    minio_client.remove_object(BUCKET_NAME, object_key)


def delete_objects_by_prefix(prefix: str) -> None:
    to_delete = (
        DeleteObject(obj.object_name)
        for obj in minio_client.list_objects(BUCKET_NAME, prefix=prefix, recursive=True)
    )
    # remove_objects returns an iterator of per-object errors -- must be
    # consumed or nothing actually happens (lazy generator underneath).
    for error in minio_client.remove_objects(BUCKET_NAME, to_delete):
        raise RuntimeError(f"Failed to delete {error.name}: {error}")
