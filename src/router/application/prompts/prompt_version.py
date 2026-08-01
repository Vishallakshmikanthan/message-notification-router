"""Prompt versioning module for the WhatsApp Notification Router.

Implements semantic versioning for prompt templates as specified in
prompt_architecture.md §6 (Prompt Engineering Governance & Version Control).

Every prompt execution records prompt_id, prompt_version, and a computed
git_commit_hash equivalent for full observability and auditability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class PromptVersion:
    """Immutable semantic version descriptor for a prompt template.

    Attributes:
        major: Breaking change version number.
        minor: Backward-compatible feature addition.
        patch: Backward-compatible bug fix.
        prompt_id: Unique prompt identifier (e.g., "system_prompt").
        layer: Prompt hierarchy layer (e.g., "system", "reasoning").
        commit_hash: Optional git commit hash for full lineage tracing.
    """

    major: int
    minor: int
    patch: int
    prompt_id: str
    layer: str
    commit_hash: Optional[str] = field(default=None)

    @property
    def version_string(self) -> str:
        """Return the full semantic version string (e.g., '1.0.0')."""
        return f"{self.major}.{self.minor}.{self.patch}"

    @property
    def full_id(self) -> str:
        """Return unique prompt lineage identifier (e.g., 'system_prompt@1.0.0')."""
        return f"{self.prompt_id}@{self.version_string}"

    @classmethod
    def from_string(cls, prompt_id: str, layer: str, version_str: str) -> "PromptVersion":
        """Parse a semantic version string into a PromptVersion.

        Args:
            prompt_id: Prompt identifier.
            layer: Prompt hierarchy layer.
            version_str: Semantic version string (e.g., "1.0.0").

        Returns:
            PromptVersion instance.

        Raises:
            ValueError: If version_str is not a valid semantic version.
        """
        parts = version_str.strip().split(".")
        if len(parts) != 3:
            raise ValueError(
                f"Invalid semantic version: '{version_str}'. Expected format: MAJOR.MINOR.PATCH"
            )
        try:
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError as exc:
            raise ValueError(
                f"Version components must be integers, got: '{version_str}'"
            ) from exc
        return cls(
            major=major,
            minor=minor,
            patch=patch,
            prompt_id=prompt_id,
            layer=layer,
        )

    def is_compatible_with(self, other: "PromptVersion") -> bool:
        """Check backward compatibility (same major version).

        Args:
            other: Another PromptVersion to compare against.

        Returns:
            True if both versions share the same major number.
        """
        return self.major == other.major

    def __str__(self) -> str:
        return self.full_id

    def __repr__(self) -> str:
        return (
            f"PromptVersion(id={self.prompt_id!r}, version={self.version_string!r}, "
            f"layer={self.layer!r})"
        )
