"""ContextBuilder implementation for synthesizing immutable MessageContext instances."""

from router.domain.entities.business import BusinessAccount, UserBusinessHistory
from router.domain.entities.context import MessageContext
from router.domain.entities.group import Group, GroupMember
from router.domain.entities.message import Message
from router.domain.entities.user import User


class ContextBuilder:
    """Stateless builder for constructing MessageContext objects."""

    def build(
        self,
        message: Message,
        user: User | None = None,
        group: Group | None = None,
        group_member: GroupMember | None = None,
        business: BusinessAccount | None = None,
        user_business_history: UserBusinessHistory | None = None,
        media_ocr_text: str | None = None,
        media_vlm_caption: str | None = None,
        voice_transcript: str | None = None,
    ) -> MessageContext:
        """Assemble and return an immutable MessageContext object."""
        return MessageContext(
            message_id=message.message_id,
            user_id=message.user_id,
            sender_id=message.sender_id,
            conversation_type=message.conversation_type,
            message_text=message.message_text,
            created_at=message.created_at,
            forwarded_count=message.forwarded_count,
            user=user,
            group=group,
            group_member=group_member,
            business=business,
            user_business_history=user_business_history,
            media_id=message.media_id,
            media_type=message.media_type,
            media_ocr_text=media_ocr_text,
            media_vlm_caption=media_vlm_caption,
            voice_transcript=voice_transcript,
        )
