"""FastAPI Application Main Entry Point."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from router.application.decision.decision_engine import DecisionEngineV2
from router.core.config.settings import get_settings
from router.core.logging.logger import configure_logger, get_logger
from router.domain.entities.context import MessageContext

settings = get_settings()
configure_logger(log_level=settings.log_level, is_dev=(settings.app_env == "development"))
logger = get_logger(__name__)

# Singleton decision engine (initialised once on startup)
_engine: DecisionEngineV2 | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle event manager."""
    global _engine
    logger.info("Initializing system foundation...", app_env=settings.app_env)
    _engine = DecisionEngineV2()
    logger.info("DecisionEngineV2 ready")
    yield
    logger.info("Shutting down system foundation...")
    _engine = None


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class MessageEvaluateRequest(BaseModel):
    """Payload for a single real-time message routing decision."""
    message_id: str = "msg_live_001"
    sender_id: str = "user_123"
    content: str = "Hello"
    media_type: str = "text"


class MessageEvaluateResponse(BaseModel):
    """Structured routing decision response."""
    message_id: str
    action: str
    message_type: str
    reason: str
    confidence: float
    evidence_ids: list[str]


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """FastAPI Application Factory."""
    app = FastAPI(
        title="WhatsApp AI Notification Router",
        description=(
            "Enterprise-grade AI-powered WhatsApp Message Notification Router. "
            "Routes incoming messages in real-time using a 12-stage Decision Pipeline."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # -----------------------------------------------------------------------
    # GET /
    # -----------------------------------------------------------------------
    @app.get("/", tags=["info"])
    async def root() -> dict[str, Any]:
        """Root endpoint — system overview."""
        return {
            "name": "WhatsApp AI Notification Router",
            "version": "0.1.0",
            "status": "online",
            "docs": "/docs",
            "health": "/health",
            "evaluate": "POST /api/v1/evaluate",
        }

    # -----------------------------------------------------------------------
    # GET /health
    # -----------------------------------------------------------------------
    @app.get("/health", tags=["monitoring"])
    async def health() -> dict[str, str]:
        """Health-check endpoint."""
        return {
            "status": "OK",
            "engine": "DecisionEngineV2",
            "app": settings.app_name,
        }

    # -----------------------------------------------------------------------
    # POST /api/v1/evaluate
    # -----------------------------------------------------------------------
    @app.post("/api/v1/evaluate", response_model=MessageEvaluateResponse, tags=["routing"])
    async def evaluate_message(payload: MessageEvaluateRequest) -> MessageEvaluateResponse:
        """
        Real-time message routing decision.

        Accepts a WhatsApp message payload and returns the routing action
        (e.g. DELIVER, SUPPRESS_SPAM, MUTE, PRIORITY_DELIVER) produced by the
        12-stage Decision Intelligence Pipeline.
        """
        engine = _engine or DecisionEngineV2()

        # Build a minimal MessageContext using the backward-compat flat fields
        ctx = MessageContext(
            message_id=payload.message_id,
            sender_id=payload.sender_id,
            message_text=payload.content,
            media_type=payload.media_type,
        )

        action, msg_type, reason, confidence, evidence = engine.evaluate_routing(ctx)

        return MessageEvaluateResponse(
            message_id=payload.message_id,
            action=action.value if hasattr(action, "value") else str(action),
            message_type=msg_type.value if hasattr(msg_type, "value") else str(msg_type),
            reason=reason,
            confidence=round(confidence, 4),
            evidence_ids=evidence,
        )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("router.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
