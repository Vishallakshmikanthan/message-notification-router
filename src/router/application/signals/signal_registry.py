"""SignalRegistry implementation maintaining dynamic directory of registered signal calculators."""


from router.application.signals.base_calculator import BaseSignalCalculator
from router.core.logging.logger import get_logger

logger = get_logger(__name__)


class SignalRegistry:
    """Registry maintaining active signal calculators and DAG execution lookup."""

    def __init__(self) -> None:
        """Initialize empty registry structures."""
        self._calculators_by_name: dict[str, BaseSignalCalculator] = {}
        self._calculators_by_category: dict[str, list[BaseSignalCalculator]] = {}

    def register(self, calculator: BaseSignalCalculator) -> None:
        """Register a BaseSignalCalculator instance into the registry."""
        name = calculator.get_name()
        category = calculator.get_category()

        self._calculators_by_name[name] = calculator
        if category not in self._calculators_by_category:
            self._calculators_by_category[category] = []
        self._calculators_by_category[category].append(calculator)
        logger.debug("Registered signal calculator", name=name, category=category)

    def get_calculator(self, name: str) -> BaseSignalCalculator | None:
        """Retrieve registered calculator by name."""
        return self._calculators_by_name.get(name)

    def get_calculators_by_category(self, category: str) -> list[BaseSignalCalculator]:
        """Retrieve list of registered calculators under a category."""
        return self._calculators_by_category.get(category, [])

    def get_all_calculators(self) -> list[BaseSignalCalculator]:
        """Return list of all registered calculators."""
        return list(self._calculators_by_name.values())
