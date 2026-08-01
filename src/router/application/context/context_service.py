"""ContextService implementing IContextService contract."""

from router.application.context.context_builder import ContextBuilder
from router.core.logging.logger import get_logger
from router.domain.entities.context import MessageContext
from router.domain.entities.message import Message
from router.domain.ports.repository_ports import (
    IBusinessRepository,
    IGroupRepository,
    IMediaRepository,
    IUserRepository,
)
from router.domain.ports.service_ports import IContextService

logger = get_logger(__name__)


class ContextService(IContextService):
    """Orchestrates multi-repository fan-out reads and builds MessageContext."""

    def __init__(
        self,
        user_repo: IUserRepository,
        group_repo: IGroupRepository,
        business_repo: IBusinessRepository,
        media_repo: IMediaRepository,
        builder: ContextBuilder | None = None,
    ) -> None:
        """Initialize ContextService with repository dependencies."""
        self.user_repo = user_repo
        self.group_repo = group_repo
        self.business_repo = business_repo
        self.media_repo = media_repo
        self.builder = builder or ContextBuilder()

    def create_context(self, message: Message) -> MessageContext:
        """Perform fan-out reads and synthesize enriched MessageContext."""
        user = self.user_repo.get_by_id(message.user_id)
        group = self.group_repo.get_by_id(message.group_id) if message.group_id else None
        group_member = (
            self.group_repo.get_member(message.group_id, message.user_id)
            if message.group_id
            else None
        )
        business = (
            self.business_repo.get_by_id(message.business_id) if message.business_id else None
        )
        user_business_history = (
            self.business_repo.get_user_history(message.user_id, message.business_id)
            if message.business_id
            else None
        )

        ocr_text: str | None = None
        vlm_caption: str | None = None
        transcript: str | None = None

        if message.media_id and message.media_type == "image":
            image_manifest = self.media_repo.get_image(message.media_id)
            if image_manifest:
                ocr_text = image_manifest.ocr_text
                vlm_caption = image_manifest.vlm_caption
        elif message.media_id and message.media_type == "voice":
            voice_manifest = self.media_repo.get_voice(message.media_id)
            if voice_manifest:
                transcript = voice_manifest.transcript

        return self.builder.build(
            message=message,
            user=user,
            group=group,
            group_member=group_member,
            business=business,
            user_business_history=user_business_history,
            media_ocr_text=ocr_text,
            media_vlm_caption=vlm_caption,
            voice_transcript=transcript,
        )
