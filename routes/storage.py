import uuid
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from dependencies.auth import get_current_user
from exceptions.domain import StorageFileNotFoundError, StorageOperationError
from services.storage_service import StorageService, storage_service

router = APIRouter(
    prefix="/storage",
    tags=["Storage"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file/asset to S3 storage",
)
async def upload_asset(
    file: UploadFile = File(...),
    folder: str = Query(default="assets", description="Folder/prefix under which to store file"),
    service: StorageService = Depends(lambda: storage_service),
):
    """
    Accepts a binary file upload and stores it in S3.
    Returns a stable identifier (key) and metadata that can be used to retrieve or delete it later.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Cannot upload an empty file.")

    # Generate a stable, collision-free key
    file_ext = ""
    if file.filename and "." in file.filename:
        file_ext = "." + file.filename.rsplit(".", 1)[-1]
    
    unique_key = f"{folder}/{uuid.uuid4().hex}{file_ext}"

    content_type = file.content_type or "application/octet-stream"
    result = await service.upload_file(
        file_obj=file_bytes,
        key=unique_key,
        content_type=content_type,
    )

    return {
        "identifier": unique_key,
        "filename": file.filename,
        "content_type": content_type,
        "size_bytes": len(file_bytes),
        "bucket": result["bucket"],
        "url": result["url"],
    }


@router.get(
    "/files",
    summary="List files stored in S3",
)
async def list_assets(
    prefix: str = Query(default="", description="Key prefix to filter files"),
    max_keys: int = Query(default=50, ge=1, le=200, description="Max files to return"),
    service: StorageService = Depends(lambda: storage_service),
):
    """
    List files stored under a given key prefix.
    """
    files = await service.list_files(prefix=prefix, max_keys=max_keys)
    return {
        "prefix": prefix,
        "count": len(files),
        "files": files,
    }


@router.get(
    "/files/{file_id:path}",
    summary="Retrieve and stream a stored file from S3 by identifier",
)
async def get_asset(
    file_id: str,
    service: StorageService = Depends(lambda: storage_service),
):
    """
    Retrieves a stored file by its identifier and streams the content back to the client.
    Returns 404 if the key does not exist.
    """
    file_data = await service.get_file(file_id)
    return Response(
        content=file_data["content"],
        media_type=file_data["content_type"],
        headers={
            "Content-Disposition": f'inline; filename="{file_id.split("/")[-1]}"',
            "Content-Length": str(file_data["content_length"]),
        },
    )


@router.delete(
    "/files/{file_id:path}",
    summary="Delete a stored file from S3 by identifier",
)
async def delete_asset(
    file_id: str,
    service: StorageService = Depends(lambda: storage_service),
):
    """
    Deletes a file by its identifier.
    """
    await service.delete_file(file_id)
    return {
        "status": "deleted",
        "identifier": file_id,
    }
