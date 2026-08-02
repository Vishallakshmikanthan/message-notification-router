"""Prompt Loader — YAML template loader for the versioned prompt registry.

Loads prompt templates from the filesystem according to the directory
convention: templates/{version}/{prompt_id}.yaml.

Spec: prompt_architecture.md §6 — Prompt Registry stores prompts under
Semantic Versioning (v1.2.0.yaml).

Design:
- Templates are loaded lazily and cached in-memory after first access.
- File-not-found errors raise explicit PromptNotFoundError.
- YAML parse errors raise PromptLoadError with full context.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

from router.application.prompts.prompt_version import PromptVersion

logger = logging.getLogger(__name__)

# Default template directory (relative to this file)
_DEFAULT_TEMPLATE_DIR = Path(__file__).parent / "templates"


class PromptNotFoundError(Exception):
    """Raised when a requested prompt template YAML file does not exist."""


class PromptLoadError(Exception):
    """Raised when YAML parsing or template validation fails."""


class PromptTemplate:
    """Loaded and validated prompt template.

    Attributes:
        version: Parsed PromptVersion descriptor.
        raw_content: Raw template string with {placeholder} slots.
        token_budget: Estimated token budget for this layer.
        cacheable: Whether this prompt is eligible for provider prefix caching.
        description: Human-readable prompt description.
    """

    __slots__ = ("version", "raw_content", "token_budget", "cacheable", "description")

    def __init__(
        self,
        version: PromptVersion,
        raw_content: str,
        token_budget: int,
        cacheable: bool,
        description: str,
    ) -> None:
        self.version = version
        self.raw_content = raw_content
        self.token_budget = token_budget
        self.cacheable = cacheable
        self.description = description

    def render(self, variables: dict[str, Any]) -> str:
        """Render the template by substituting {placeholder} variables.

        Args:
            variables: Key-value mapping of template variables.

        Returns:
            Rendered prompt string.

        Raises:
            KeyError: If a required template variable is missing.
        """
        try:
            return self.raw_content.format(**variables)
        except KeyError as exc:
            raise PromptLoadError(
                f"Missing template variable {exc} for prompt '{self.version.prompt_id}'"
            ) from exc

    def __repr__(self) -> str:
        return (
            f"PromptTemplate(id={self.version.prompt_id!r}, "
            f"version={self.version.version_string!r}, "
            f"token_budget={self.token_budget})"
        )


class PromptLoader:
    """YAML prompt template loader with in-memory caching.

    Templates are stored as YAML files at:
        {template_dir}/v{major}/{prompt_id}.yaml

    Example file path:
        templates/v1/system_prompt.yaml

    Args:
        template_dir: Root directory containing versioned template subdirectories.
                      Defaults to the package-relative 'templates/' directory.
    """

    def __init__(self, template_dir: Path | None = None) -> None:
        """Initialize the PromptLoader.

        Args:
            template_dir: Root directory for YAML templates.
        """
        self._template_dir = template_dir or _DEFAULT_TEMPLATE_DIR
        self._cache: dict[str, PromptTemplate] = {}
        logger.info(
            "PromptLoader initialized",
            extra={"template_dir": str(self._template_dir), "yaml_available": _YAML_AVAILABLE},
        )

    def load(self, prompt_id: str, major_version: int = 1) -> PromptTemplate:
        """Load and cache a prompt template by ID and major version.

        Args:
            prompt_id: Prompt identifier (e.g., 'system_prompt').
            major_version: Major version directory (e.g., 1 → 'v1/').

        Returns:
            Loaded PromptTemplate instance.

        Raises:
            PromptNotFoundError: If the YAML file does not exist.
            PromptLoadError: If parsing or validation fails.
        """
        cache_key = f"{prompt_id}@v{major_version}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        template_path = self._template_dir / f"v{major_version}" / f"{prompt_id}.yaml"

        if not template_path.exists():
            raise PromptNotFoundError(
                f"Prompt template not found: '{template_path}'. "
                f"Ensure '{prompt_id}.yaml' exists under templates/v{major_version}/."
            )

        raw = self._parse_yaml(template_path)
        template = self._build_template(raw, prompt_id, major_version)
        self._cache[cache_key] = template

        logger.debug(
            "Prompt template loaded",
            extra={
                "prompt_id": prompt_id,
                "version": template.version.version_string,
                "token_budget": template.token_budget,
                "cacheable": template.cacheable,
            },
        )
        return template

    def invalidate_cache(self, prompt_id: str | None = None) -> None:
        """Invalidate the in-memory template cache.

        Args:
            prompt_id: If provided, invalidate only this prompt's cache entry.
                       If None, flush entire cache.
        """
        if prompt_id is None:
            self._cache.clear()
            logger.info("PromptLoader: full cache invalidated")
        else:
            keys_to_remove = [k for k in self._cache if k.startswith(prompt_id)]
            for key in keys_to_remove:
                del self._cache[key]
            logger.info("PromptLoader: cache invalidated", extra={"prompt_id": prompt_id})

    def _parse_yaml(self, path: Path) -> dict[str, Any]:
        """Parse YAML file into a Python dict.

        Args:
            path: Absolute path to the YAML file.

        Returns:
            Parsed YAML content as dict.

        Raises:
            PromptLoadError: On YAML syntax errors or IO failures.
        """
        try:
            if _YAML_AVAILABLE:
                with path.open("r", encoding="utf-8") as fh:
                    data = yaml.safe_load(fh)
            else:
                # Minimal fallback: parse key: value | content: | lines
                data = self._minimal_yaml_parser(path)

            if not isinstance(data, dict):
                raise PromptLoadError(f"Invalid YAML structure in '{path}': expected dict root.")
            return data
        except OSError as exc:
            raise PromptLoadError(f"Failed to read prompt file '{path}': {exc}") from exc
        except Exception as exc:
            if "yaml" in type(exc).__module__:
                raise PromptLoadError(f"YAML parse error in '{path}': {exc}") from exc
            raise

    @staticmethod
    def _minimal_yaml_parser(path: Path) -> dict[str, Any]:
        """Fallback YAML parser when PyYAML is unavailable.

        Handles simple key: value pairs and multi-line 'content:' blocks.

        Args:
            path: Path to YAML file.

        Returns:
            Parsed dict with at least prompt_id, version, content keys.
        """
        data: dict[str, Any] = {}
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()

        in_content = False
        content_lines: list[str] = []

        for line in lines:
            if in_content:
                if line and not line.startswith(" ") and ":" in line and not line.startswith("  "):
                    in_content = False
                else:
                    content_lines.append(line.removeprefix("  "))
                    continue

            stripped = line.strip()
            if stripped.startswith("content:"):
                in_content = True
                rest = stripped[len("content:"):].strip().lstrip("|").strip()
                if rest:
                    content_lines.append(rest)
            elif ":" in stripped and not stripped.startswith("#"):
                key, _, val = stripped.partition(":")
                data[key.strip()] = val.strip().strip('"').strip("'")

        if content_lines:
            data["content"] = "\n".join(content_lines)

        return data

    @staticmethod
    def _build_template(
        raw: dict[str, Any], prompt_id: str, major_version: int
    ) -> PromptTemplate:
        """Construct a PromptTemplate from parsed YAML data.

        Args:
            raw: Parsed YAML content dict.
            prompt_id: Expected prompt identifier.
            major_version: Major version number.

        Returns:
            Validated PromptTemplate instance.

        Raises:
            PromptLoadError: If required fields are missing.
        """
        required = ["version", "layer", "content"]
        missing = [f for f in required if f not in raw]
        if missing:
            raise PromptLoadError(
                f"Prompt '{prompt_id}' YAML is missing required fields: {missing}"
            )

        try:
            version = PromptVersion.from_string(
                prompt_id=raw.get("prompt_id", prompt_id),
                layer=raw["layer"],
                version_str=raw["version"],
            )
        except ValueError as exc:
            raise PromptLoadError(f"Invalid version in '{prompt_id}.yaml': {exc}") from exc

        return PromptTemplate(
            version=version,
            raw_content=raw["content"],
            token_budget=int(raw.get("token_budget", 400)),
            cacheable=bool(raw.get("cacheable", False)),
            description=str(raw.get("description", "")),
        )
