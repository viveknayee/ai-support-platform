import logging
import uuid
from pathlib import Path

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.document import Document, DocumentStatus
from app.models.document_chunk import DocumentChunk
from app.models.tenant import Tenant  # noqa: F401
from app.services.text_extractor import ExtractionError, extract_text
from app.services.text_processor import TextChunk, split_text_into_chunks

logger = logging.getLogger(__name__)

MAX_ERROR_LENGTH = 1000  # Document.error_message is String(1000)


async def set_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    # The RLS setting lives only until the next commit, so this must be called
    # at the start of EVERY transaction.
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


async def save_result(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
    status: DocumentStatus,
    error: str | None,
    chunks: list[TextChunk],
) -> None:
    """One transaction: replace the document's chunks and set its final status together."""
    await set_tenant(session, tenant_id)
    # Delete first so a re-run (Celery can deliver a task twice) never creates duplicates.
    await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
    session.add_all(
        DocumentChunk(
            tenant_id=tenant_id,
            document_id=document_id,
            chunk_index=chunk.chunk_index,
            token_count=chunk.token_count,
            content=chunk.text,
        )
        for chunk in chunks
    )
    await session.execute(
        update(Document)
        .where(Document.id == document_id)
        .values(status=status, error_message=error[:MAX_ERROR_LENGTH] if error else None)
    )
    await session.commit()


async def process_document(document_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
    """Read the stored file, extract its text, split it into chunks, save them and update the status.
    Returns a short result word: completed / failed / not_found / skipped."""

    # A fresh engine for every task: asyncio.run() creates a new event loop each time,
    # and a connection pool made in an old loop would crash with "event loop is closed".
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            # ---- Transaction 1: find the document and mark it PROCESSING ----
            await set_tenant(session, tenant_id)
            document = (
                await session.execute(select(Document).where(Document.id == document_id))
            ).scalar_one_or_none()

            if document is None:  # wrong id, or it belongs to another tenant (RLS hides it)
                logger.warning("Document %s not found for tenant %s", document_id, tenant_id)
                return "not_found"

            if document.status in (DocumentStatus.COMPLETED, DocumentStatus.FAILED):
                return "skipped"  # Celery can deliver a task twice; never redo finished work

            document.status = DocumentStatus.PROCESSING
            document.error_message = None
            await session.commit()  # the tenant setting ends here

            # ---- The slow part: no DB transaction is open while we read the file ----
            storage_path = Path(document.storage_path)
            chunks: list[TextChunk] = []
            try:
                chunks = split_text_into_chunks(extract_text(storage_path))
                new_status, error = DocumentStatus.COMPLETED, None
            except ExtractionError as exc:  # a problem with the FILE: safe to show the user
                new_status, error = DocumentStatus.FAILED, str(exc)
            except FileNotFoundError:
                new_status, error = DocumentStatus.FAILED, "The stored file is missing."
            except Exception:  # a bug on OUR side: log the details, show a generic message
                logger.exception("Unexpected error while processing document %s", document_id)
                new_status, error = DocumentStatus.FAILED, "Unexpected error while processing the file."

            # ---- Transaction 2: save chunks + final status together (set the tenant again!) ----
            try:
                await save_result(session, tenant_id, document_id, new_status, error, chunks)
            except Exception:
                logger.exception("Could not save chunks for document %s", document_id)
                await session.rollback()
                new_status, error = DocumentStatus.FAILED, "Could not save the extracted text chunks."
                await save_result(session, tenant_id, document_id, new_status, error, [])

            return new_status.value.lower()
    finally:
        await engine.dispose()