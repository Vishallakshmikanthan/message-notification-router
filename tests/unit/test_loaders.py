"""Unit tests verifying every loader stage independently."""

import os
import pytest

from router.infrastructure.repositories.business_repository import BusinessRepository
from router.infrastructure.repositories.event_repository import EventRepository
from router.infrastructure.repositories.group_repository import GroupRepository
from router.infrastructure.repositories.history_repository import HistoryRepository
from router.infrastructure.repositories.media_repository import MediaRepository
from router.infrastructure.repositories.message_repository import MessageRepository
from router.infrastructure.repositories.notification_summary_repository import (
    NotificationSummaryRepository,
)
from router.infrastructure.repositories.user_repository import UserRepository
from router.infrastructure.storage.data_loader import DataLoader
from router.infrastructure.storage.file_manager import FileManager


def test_stage1_media_audit(dataset_dir: str) -> None:
    """Verify Stage 1 physical media directory auditing."""
    media_dir = os.path.join(dataset_dir, "media")
    fm = FileManager(media_dir=media_dir)
    valid_paths = fm.audit_media_directories()
    assert isinstance(valid_paths, set)
    assert len(valid_paths) > 0


def test_stage2_base_entities_loader(dataset_dir: str) -> None:
    """Verify Stage 2 static base entity loading (users, groups, business_accounts)."""
    user_repo = UserRepository()
    group_repo = GroupRepository()
    biz_repo = BusinessRepository()

    loader = DataLoader(
        user_repo=user_repo,
        group_repo=group_repo,
        business_repo=biz_repo,
    )
    result = loader.execute_pipeline(dataset_dir)
    assert result["status"] == "success"

    assert user_repo.count() > 0
    assert group_repo.count() > 0
    assert biz_repo.count() > 0

    # Spot check user u_001
    user = user_repo.get_by_id("u_001")
    assert user is not None
    assert user.user_id == "u_001"


def test_stage3_relationship_loader(dataset_dir: str) -> None:
    """Verify Stage 3 junction and relationship loading (group_members, user_business_history)."""
    user_repo = UserRepository()
    group_repo = GroupRepository()
    biz_repo = BusinessRepository()

    loader = DataLoader(
        user_repo=user_repo,
        group_repo=group_repo,
        business_repo=biz_repo,
    )
    loader.execute_pipeline(dataset_dir)

    # Verify group member junction lookup
    member = group_repo.get_member("group_001", "u_001")
    # Might be None or member depending on dataset, check index exists
    assert len(group_repo._members_index) > 0

    # Verify business history lookup
    assert len(biz_repo._history_index) > 0


def test_stage4_media_manifest_loader(dataset_dir: str) -> None:
    """Verify Stage 4 media manifest resolution (images.csv, voice_notes.csv)."""
    media_repo = MediaRepository()
    loader = DataLoader(media_repo=media_repo)
    loader.execute_pipeline(dataset_dir)

    assert len(media_repo._image_index) > 0
    assert len(media_repo._voice_index) > 0


def test_stage5_history_and_events_loader(dataset_dir: str) -> None:
    """Verify Stage 5 historical corpus and event logs loading."""
    history_repo = HistoryRepository()
    event_repo = EventRepository()

    loader = DataLoader(history_repo=history_repo, event_repo=event_repo)
    loader.execute_pipeline(dataset_dir)

    assert history_repo.count() > 0
    assert event_repo.count() > 0


def test_stage6_time_series_summary_loader(dataset_dir: str) -> None:
    """Verify Stage 6 daily notification summary loading."""
    summary_repo = NotificationSummaryRepository()
    loader = DataLoader(summary_repo=summary_repo)
    loader.execute_pipeline(dataset_dir)

    assert summary_repo.count() > 0


def test_stage7_incoming_message_loader(dataset_dir: str) -> None:
    """Verify Stage 7 primary incoming evaluation message loading."""
    msg_repo = MessageRepository()
    loader = DataLoader(message_repo=msg_repo)
    loader.execute_pipeline(dataset_dir)

    assert msg_repo.count() > 0
