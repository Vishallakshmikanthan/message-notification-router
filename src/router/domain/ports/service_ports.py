"""Abstract Core Service Port Interfaces."""

from abc import ABC, abstractmethod
from typing import Any, Mapping

from router.domain.entities.context import MessageContext
from router.domain.entities.message import Message


class IDataLoader(ABC):
    """Abstract 7-stage deterministic boot data loader interface."""

    @abstractmethod
    def execute_pipeline(self, dataset_dir: str) -> Mapping[str, Any]:
        """Execute 7-stage boot ingestion pipeline."""
        ...


class IDataManager(ABC):
    """Abstract Data Layer Facade & Lifecycle Manager interface."""

    @abstractmethod
    def initialize(self, dataset_dir: str) -> None:
        """Initialize data layer components and boot pipeline."""
        ...

    @abstractmethod
    def reload(self) -> None:
        """Reload dataset repositories in-memory."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Gracefully release data layer resources."""
        ...

    @abstractmethod
    def get_status(self) -> Mapping[str, Any]:
        """Return operational health status dictionary."""
        ...


class IContextService(ABC):
    """Abstract Context Service interface for synthesizing MessageContext objects."""

    @abstractmethod
    def create_context(self, message: Message) -> MessageContext:
        """Synthesize enriched MessageContext for an incoming message."""
        ...


class ILookupService(ABC):
    """Base lookup service interface."""

    ...
