import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_tenant_user, get_db
from app.core.config import settings
from app.models.document import Document, DocumentStatus
from app.schemas.document import DocumentResponse

router = APIRouter()

CHUNK_SIZE = 1024 * 1024  # read the upload 1 MB at a time

# allowed content type -> the file extension it must come with
ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
}


def validate_file_type(file: UploadFile) -> str:
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    extension = Path(file.filename or "").suffix.lower()

    if content_type not in ALLOWED_TYPES or extension != ALLOWED_TYPES[content_type]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and TXT files are allowed.",
        )
    return extension


async def save_upload_to_disk(file: UploadFile, destination: Path, extension: str) -> int:
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    destination.parent.mkdir(parents=True, exist_ok=True)

    size = 0
    saved = False
    try:
        async with aiofiles.open(destination, "wb") as out:
            while chunk := await file.read(CHUNK_SIZE):
                if size == 0 and extension == ".pdf" and b"%PDF-" not in chunk[:1024]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="File is not a valid PDF.",
                    )
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum is {settings.MAX_UPLOAD_SIZE_MB} MB.",
                    )
                await out.write(chunk)

        if size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty.",
            )
        saved = True
    finally:
        if not saved:
            destination.unlink(missing_ok=True)  # never leave half-written files

    return size


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    current_user: dict = Depends(get_current_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    extension = validate_file_type(file)

    filename = Path(file.filename).name
    if len(filename) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File name is too long (maximum 255 characters).",
        )

    tenant_id = uuid.UUID(current_user["tenant_id"])
    document_id = uuid.uuid4()
    destination = Path(settings.STORAGE_DIR) / str(tenant_id) / f"{document_id}{extension}"

    await save_upload_to_disk(file, destination, extension)

    document = Document(
        id=document_id,
        tenant_id=tenant_id,
        filename=filename,
        storage_path=str(destination),
        status=DocumentStatus.PENDING,
    )
    try:
        db.add(document)
        await db.flush()
        await db.refresh(document)  # must happen BEFORE commit (tenant context ends at commit)
        await db.commit()
    except Exception:
        await db.rollback()
        destination.unlink(missing_ok=True)  # no DB row -> no orphan file
        raise

    return document