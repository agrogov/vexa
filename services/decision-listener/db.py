"""
Lightweight async DB access for decision-listener.
Only initialised when DB_HOST is set; otherwise all operations are no-ops.
"""
import os
import logging
from contextlib import asynccontextmanager
from typing import Optional, List

logger = logging.getLogger(__name__)

_DB_HOST = os.environ.get("DB_HOST")
_DB_PORT = os.environ.get("DB_PORT", "5432")
_DB_NAME = os.environ.get("DB_NAME")
_DB_USER = os.environ.get("DB_USER")
_DB_PASSWORD = os.environ.get("DB_PASSWORD")
_DB_SSL_MODE = os.environ.get("DB_SSL_MODE", "disable")

_session_factory = None


def is_configured() -> bool:
    return bool(_DB_HOST and _DB_NAME and _DB_USER and _DB_PASSWORD)


def init_db():
    """Call once at startup. No-op if DB env vars are not set."""
    global _session_factory
    if not is_configured():
        logger.warning("DB_HOST not set — decisions will not be persisted to Postgres")
        return
    try:
        import ssl
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker

        url = f"postgresql+asyncpg://{_DB_USER}:{_DB_PASSWORD}@{_DB_HOST}:{_DB_PORT}/{_DB_NAME}"
        connect_args: dict = {"statement_cache_size": 0}
        if _DB_SSL_MODE in ("require", "prefer"):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            connect_args["ssl"] = ctx
        elif _DB_SSL_MODE in ("verify-ca", "verify-full"):
            connect_args["ssl"] = True
        elif _DB_SSL_MODE == "disable":
            connect_args["ssl"] = False

        engine = create_async_engine(url, connect_args=connect_args, pool_size=5, max_overflow=10)
        _session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        logger.info(f"DB connection pool initialised: {_DB_HOST}:{_DB_PORT}/{_DB_NAME}")
    except Exception as e:
        logger.error(f"Failed to initialise DB connection: {e}", exc_info=True)


@asynccontextmanager
async def get_session():
    """Async context manager that yields a session, or None if DB is not configured."""
    if _session_factory is None:
        yield None
        return
    async with _session_factory() as session:
        yield session


async def persist_decision(meeting_id: str, item: dict) -> bool:
    """
    Persist a decision item to the meeting_decisions table.
    Returns True on success, False on failure (caller should not abort on failure).
    """
    if not is_configured():
        return False
    try:
        from shared_models.models import MeetingDecision
        async with get_session() as session:
            if session is None:
                return False
            decision = MeetingDecision(
                meeting_id=int(meeting_id),
                type=item.get("type", "unknown"),
                summary=item.get("summary", ""),
                speaker=item.get("speaker"),
                confidence=item.get("confidence"),
                entities=item.get("entities", []),
            )
            session.add(decision)
            await session.commit()
            return True
    except Exception as e:
        logger.error(f"[{meeting_id}] Failed to persist decision to DB: {e}", exc_info=True)
        return False


async def load_decisions(meeting_id: str) -> Optional[List[dict]]:
    """
    Load all decisions for a meeting from Postgres.
    Returns None if DB is not configured, empty list if no decisions found.
    """
    if not is_configured():
        return None
    try:
        from shared_models.models import MeetingDecision
        from sqlalchemy import select
        async with get_session() as session:
            if session is None:
                return None
            result = await session.execute(
                select(MeetingDecision)
                .where(MeetingDecision.meeting_id == int(meeting_id))
                .order_by(MeetingDecision.created_at)
            )
            rows = result.scalars().all()
            return [
                {
                    "type": r.type,
                    "summary": r.summary,
                    "speaker": r.speaker,
                    "confidence": r.confidence,
                    "entities": r.entities or [],
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"[{meeting_id}] Failed to load decisions from DB: {e}", exc_info=True)
        return None
