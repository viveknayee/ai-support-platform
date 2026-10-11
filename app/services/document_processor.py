import logging
import uuid
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.document import Document, DocumentStatus
from app.models.tenant import Tenant  # noqa: F401   
from app.services.text_extractor import ExtractionError, extract_text

logger = logging.getLogger(__name__)

MAX_ERROR_LENGTH = 1000  # Document.error_message is String(1000)


async def set_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    # The RLS setting lives only until the next commit, so this must be called
    # at the start of EVERY transaction.
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


async def process_document(document_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
    """Read the stored file, extract its text and update the document status.
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
            try:
                extract_text(storage_path)  # Day 12 will use the returned text
                new_status, error = DocumentStatus.COMPLETED, None
            except ExtractionError as exc:  # a problem with the FILE: safe to show the user
                new_status, error = DocumentStatus.FAILED, str(exc)
            except FileNotFoundError:
                new_status, error = DocumentStatus.FAILED, "The stored file is missing."
            except Exception:  # a bug on OUR side: log the details, show a generic message
                logger.exception("Unexpected error while processing document %s", document_id)
                new_status, error = DocumentStatus.FAILED, "Unexpected error while processing the file."

            # ---- Transaction 2: save the result (set the tenant again!) ----
            await set_tenant(session, tenant_id)
            document.status = new_status
            document.error_message = error[:MAX_ERROR_LENGTH] if error else None
            await session.commit()

            return new_status.value.lower()
    finally:
        await engine.dispose()