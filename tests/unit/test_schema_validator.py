"""Unit tests for 4-level SchemaValidator and QuarantineEngine."""

from router.infrastructure.storage.quarantine_engine import QuarantineEngine
from router.infrastructure.storage.schema_validator import SchemaValidator


def test_schema_validator_levels() -> None:
    """Verify Level 1, Level 2, Level 3, and Level 4 validation rules."""
    qe = QuarantineEngine()
    validator = SchemaValidator(quarantine_engine=qe)

    # Level 1: Structure check
    bad_row1 = {"user_id": "u_001"}
    assert validator.validate_level1_structure(bad_row1, ["user_id", "name"], "users.csv") is False
    assert len(qe.get_quarantined()) == 1

    # Level 2: Regex PK check
    bad_row2 = {"user_id": "invalid_id_format"}
    assert validator.validate_level2_types_and_formats(bad_row2, "user_id", "user_id", "users.csv") is False
    assert len(qe.get_quarantined()) == 2

    # Level 3: FK check
    valid_uids = {"u_001", "u_002"}
    bad_row3 = {"user_id": "u_999"}
    assert validator.validate_foreign_key("u_999", valid_uids, "user_id", "messages.csv", bad_row3) is False
    assert len(qe.get_quarantined()) == 3

    # Level 4: Business invariant check (member_count < admin_count)
    bad_row4 = {"group_id": "group_001", "member_count": "2", "admin_count": "5"}
    assert validator.validate_level4_domain_rules(bad_row4, "groups.csv") is False
    assert len(qe.get_quarantined()) == 4
