"""DataLoader implementation executing 7-stage deterministic boot sequence specified in data_layer.md."""

import csv
import os
from collections.abc import Mapping
from typing import Any

from router.core.logging.logger import get_logger
from router.domain.ports.service_ports import IDataLoader
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
from router.infrastructure.storage.data_model_factory import DataModelFactory
from router.infrastructure.storage.file_manager import FileManager
from router.infrastructure.storage.quarantine_engine import QuarantineEngine
from router.infrastructure.storage.schema_validator import SchemaValidator

logger = get_logger(__name__)


class DataLoader(IDataLoader):
    """Coordinates 7-stage deterministic system boot data ingestion pipeline."""

    def __init__(
        self,
        user_repo: UserRepository | None = None,
        group_repo: GroupRepository | None = None,
        business_repo: BusinessRepository | None = None,
        media_repo: MediaRepository | None = None,
        history_repo: HistoryRepository | None = None,
        event_repo: EventRepository | None = None,
        summary_repo: NotificationSummaryRepository | None = None,
        message_repo: MessageRepository | None = None,
        file_manager: FileManager | None = None,
        schema_validator: SchemaValidator | None = None,
        quarantine_engine: QuarantineEngine | None = None,
        factory: DataModelFactory | None = None,
    ) -> None:
        """Initialize DataLoader repositories, managers, and factories."""
        self.user_repo = user_repo or UserRepository()
        self.group_repo = group_repo or GroupRepository()
        self.business_repo = business_repo or BusinessRepository()
        self.media_repo = media_repo or MediaRepository()
        self.history_repo = history_repo or HistoryRepository()
        self.event_repo = event_repo or EventRepository()
        self.summary_repo = summary_repo or NotificationSummaryRepository()
        self.message_repo = message_repo or MessageRepository()

        self.quarantine_engine = quarantine_engine or QuarantineEngine()
        self.schema_validator = schema_validator or SchemaValidator(self.quarantine_engine)
        self.file_manager = file_manager
        self.factory = factory or DataModelFactory()
        self._is_loaded: bool = False

    def _read_csv(self, file_path: str) -> list[dict[str, str]]:
        """Read CSV file into list of row dictionaries."""
        if not os.path.exists(file_path):
            logger.warning(f"CSV file not found: {file_path}")
            return []
        rows = []
        with open(file_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append({k.strip(): v.strip() for k, v in r.items() if k})
        return rows

    def execute_pipeline(self, dataset_dir: str) -> Mapping[str, Any]:
        """Execute 7-stage deterministic boot data ingestion pipeline."""
        logger.info("Starting 7-stage deterministic boot pipeline", dataset_dir=dataset_dir)
        reports: dict[str, Any] = {}

        media_dir = os.path.join(dataset_dir, "media")
        fm = self.file_manager or FileManager(media_dir=media_dir)

        # Stage 1: Physical Media File System Audit
        valid_media_paths = fm.audit_media_directories()
        reports["stage1_media_files"] = len(valid_media_paths)

        # Stage 2: Static Base Entity Loading (users.csv, groups.csv, business_accounts.csv)
        users_rows = self._read_csv(os.path.join(dataset_dir, "users.csv"))
        user_pks: set[str] = set()
        for row in users_rows:
            if self.schema_validator.validate_level1_structure(row, ["user_id"], "users.csv"):
                if self.schema_validator.validate_level2_types_and_formats(row, "user_id", "user_id", "users.csv"):
                    user = self.factory.create_user(row)
                    self.user_repo.add(user.user_id, user)
                    user_pks.add(user.user_id)

        groups_rows = self._read_csv(os.path.join(dataset_dir, "groups.csv"))
        group_pks: set[str] = set()
        for row in groups_rows:
            if self.schema_validator.validate_level1_structure(row, ["group_id"], "groups.csv"):
                if self.schema_validator.validate_level2_types_and_formats(row, "group_id", "group_id", "groups.csv"):
                    if self.schema_validator.validate_level4_domain_rules(row, "groups.csv"):
                        group = self.factory.create_group(row)
                        self.group_repo.add(group.group_id, group)
                        group_pks.add(group.group_id)

        biz_rows = self._read_csv(os.path.join(dataset_dir, "business_accounts.csv"))
        business_pks: set[str] = set()
        for row in biz_rows:
            if self.schema_validator.validate_level1_structure(row, ["business_id"], "business_accounts.csv"):
                if self.schema_validator.validate_level2_types_and_formats(row, "business_id", "business_id", "business_accounts.csv"):
                    biz = self.factory.create_business_account(row)
                    self.business_repo.add(biz.business_id, biz)
                    business_pks.add(biz.business_id)

        reports["stage2_users"] = self.user_repo.count()
        reports["stage2_groups"] = self.group_repo.count()
        reports["stage2_businesses"] = self.business_repo.count()

        # Stage 3: Junction & Relationship Loading (group_members.csv, user_business_history.csv)
        gm_rows = self._read_csv(os.path.join(dataset_dir, "group_members.csv"))
        for row in gm_rows:
            if self.schema_validator.validate_level1_structure(row, ["group_id", "user_id"], "group_members.csv"):
                if self.schema_validator.validate_foreign_key(row.get("group_id"), group_pks, "group_id", "group_members.csv", row) and \
                   self.schema_validator.validate_foreign_key(row.get("user_id"), user_pks, "user_id", "group_members.csv", row):
                    gm = self.factory.create_group_member(row)
                    self.group_repo.add_member(gm)

        ubh_rows = self._read_csv(os.path.join(dataset_dir, "user_business_history.csv"))
        for row in ubh_rows:
            if self.schema_validator.validate_level1_structure(row, ["user_id", "business_id"], "user_business_history.csv"):
                if self.schema_validator.validate_foreign_key(row.get("user_id"), user_pks, "user_id", "user_business_history.csv", row) and \
                   self.schema_validator.validate_foreign_key(row.get("business_id"), business_pks, "business_id", "user_business_history.csv", row):
                    ubh = self.factory.create_user_business_history(row)
                    self.business_repo.add_user_history(ubh)

        # Stage 4: Media Manifest Resolution (images.csv, voice_notes.csv)
        img_rows = self._read_csv(os.path.join(dataset_dir, "images.csv"))
        for row in img_rows:
            if self.schema_validator.validate_level1_structure(row, ["image_id"], "images.csv"):
                img = self.factory.create_image_manifest(row)
                self.media_repo.add_image(img)

        voice_rows = self._read_csv(os.path.join(dataset_dir, "voice_notes.csv"))
        for row in voice_rows:
            if self.schema_validator.validate_level1_structure(row, ["voice_note_id"], "voice_notes.csv"):
                voice = self.factory.create_voice_note_manifest(row)
                self.media_repo.add_voice(voice)

        reports["stage4_images"] = len(self.media_repo._image_index)
        reports["stage4_voice_notes"] = len(self.media_repo._voice_index)

        # Stage 5: Historical Corpus & Events (message_history.csv, message_events.csv)
        history_pks: set[str] = set()
        hist_rows = self._read_csv(os.path.join(dataset_dir, "message_history.csv"))
        for row in hist_rows:
            if self.schema_validator.validate_level1_structure(row, ["message_id", "user_id"], "message_history.csv"):
                if self.schema_validator.validate_foreign_key(row.get("user_id"), user_pks, "user_id", "message_history.csv", row):
                    hist = self.factory.create_historical_message(row)
                    self.history_repo.add(hist.message_id, hist)
                    history_pks.add(hist.message_id)

        event_rows = self._read_csv(os.path.join(dataset_dir, "message_events.csv"))
        for row in event_rows:
            if self.schema_validator.validate_level1_structure(row, ["user_id", "message_id"], "message_events.csv"):
                event = self.factory.create_message_event(row)
                self.event_repo.add(event.event_id, event)

        reports["stage5_history_messages"] = self.history_repo.count()
        reports["stage5_events"] = self.event_repo.count()

        # Stage 6: Aggregated Time-Series Summaries (daily_notification_summary.csv)
        summary_rows = self._read_csv(os.path.join(dataset_dir, "daily_notification_summary.csv"))
        for row in summary_rows:
            if self.schema_validator.validate_level1_structure(row, ["user_id", "date"], "daily_notification_summary.csv"):
                if self.schema_validator.validate_foreign_key(row.get("user_id"), user_pks, "user_id", "daily_notification_summary.csv", row):
                    summary = self.factory.create_daily_notification_summary(row)
                    self.summary_repo.add_summary(summary)

        reports["stage6_summaries"] = self.summary_repo.count()

        # Stage 7: Primary Incoming Stream Resolution (messages.csv)
        msg_rows = self._read_csv(os.path.join(dataset_dir, "messages.csv"))
        for row in msg_rows:
            if self.schema_validator.validate_level1_structure(row, ["message_id", "user_id"], "messages.csv"):
                if self.schema_validator.validate_level2_types_and_formats(row, "message_id", "message_id", "messages.csv"):
                    if self.schema_validator.validate_foreign_key(row.get("user_id"), user_pks, "user_id", "messages.csv", row):
                        if self.schema_validator.validate_level4_domain_rules(row, "messages.csv"):
                            msg = self.factory.create_message(row)
                            self.message_repo.add(msg.message_id, msg)

        reports["stage7_messages"] = self.message_repo.count()

        self._is_loaded = True
        logger.info("Boot ingestion pipeline executed successfully", reports=reports)
        return {
            "status": "success",
            "stages_completed": 7,
            "reports": reports,
            "quarantined_count": len(self.quarantine_engine.get_quarantined()),
        }
