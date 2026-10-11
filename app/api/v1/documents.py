import uuid
from contextlib import asynccontextmanager
from pathlib import Path
import asyncio                                                 
import logging                                                 
from app.workers.celery_app import celery_app                 
import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.api.deps import get_current_tenant_user
from app.core.config import settings
from app.core.database import get_tenant_db_session
from app.models.document import Document, DocumentStatus
from app.schemas.document import DocumentResponse

router = APIRouter()
logger = logging.getLogger(__name__) 

# get_tenant_db_session is a generator; this wrapper lets us use it with "async with"
tenant_db_session = asynccontextmanager(get_tenant_db_session)

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
        # the DB connection is taken only here, AFTER the slow file copy is finished
        async with tenant_db_session(tenant_id) as db:
            db.add(document)
            await db.flush()
            await db.refresh(document)  # must happen BEFORE commit (tenant context ends at commit)
            await db.commit()
    except Exception:
        destination.unlink(missing_ok=True)  # no DB row -> no orphan file
        raise
    try:                                                                                
        await asyncio.to_thread(                                                        
            celery_app.send_task,                                                       
            "process_document_task",                                                    
            args=[str(document.id), str(tenant_id)],                                    
            ignore_result=True,                                                         
        )                                                                               
    except Exception:                                                                   
        # The upload itself succeeded; do not fail it. The document stays PENDING.      
        logger.exception("Could not queue processing for document %s", document.id)    

    return document