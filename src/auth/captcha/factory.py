"""Enhanced factory for creating CAPTCHA solvers with fallback chain and Browserbase integration."""

from enum import Enum
from typing import List, Type, Dict, Optional
from .base import CaptchaSolver
from .solvers import (
    BrowserbaseCaptchaSolver,
    ManualCaptchaSolver,
    NoopCaptchaSolver,
)
from src.config import settings
import logging

logger = logging.getLogger(__name__)


class CaptchaSolverType(str, Enum):
    """CAPTCHA solver types."""

    BROWSERBASE = "browserbase"
    MANUAL = "manual"
    NOOP = "noop"


class CaptchaSolverFactory:
    """Enhanced factory for creating CAPTCHA solvers with fallback chain."""

    _solvers: Dict[CaptchaSolverType, Type[CaptchaSolver]] = {
        CaptchaSolverType.BROWSERBASE: BrowserbaseCaptchaSolver,
        CaptchaSolverType.MANUAL: ManualCaptchaSolver,
        CaptchaSolverType.NOOP: NoopCaptchaSolver,
    }

    @classmethod
    def create_solver_chain(
        cls, preferred_solvers: Optional[List[CaptchaSolverType]] = None
    ) -> List[CaptchaSolver]:
        """Create a chain of CAPTCHA solvers with fallback."""
        if preferred_solvers is None:
            # Use configuration-based preferences
            preferred_solvers = []
            for solver_name in settings.captcha_solver_preferences:
                try:
                    solver_type = CaptchaSolverType(solver_name)
                    preferred_solvers.append(solver_type)
                except ValueError:
                    logger.warning(f"Unknown CAPTCHA solver type: {solver_name}")

        solvers = []
        for solver_type in preferred_solvers:
            solver_class = cls._solvers.get(solver_type)
            if solver_class:
                try:
                    solver = solver_class()
                    solvers.append(solver)
                    logger.info(f"Created CAPTCHA solver: {solver_type.value}")
                except Exception as e:
                    logger.error(
                        f"Failed to create CAPTCHA solver {solver_type.value}: {e}"
                    )

        # Sort by priority (higher = preferred)
        return sorted(solvers, key=lambda s: s.get_priority(), reverse=True)

    @classmethod
    def create_solver(cls, solver_type: CaptchaSolverType) -> Optional[CaptchaSolver]:
        """Create a specific CAPTCHA solver."""
        solver_class = cls._solvers.get(solver_type)
        if not solver_class:
            logger.error(f"Unknown CAPTCHA solver type: {solver_type}")
            return None

        try:
            solver = solver_class()
            logger.info(f"Created CAPTCHA solver: {solver_type.value}")
            return solver
        except Exception as e:
            logger.error(f"Failed to create CAPTCHA solver {solver_type.value}: {e}")
            return None

    @classmethod
    def get_available_solvers(cls) -> List[CaptchaSolverType]:
        """Get list of available CAPTCHA solver types."""
        return list(cls._solvers.keys())

    @classmethod
    def get_solver_info(cls, solver_type: CaptchaSolverType) -> Dict[str, any]:
        """Get information about a CAPTCHA solver."""
        solver_class = cls._solvers.get(solver_type)
        if not solver_class:
            return {"error": f"Unknown solver type: {solver_type}"}

        try:
            solver = solver_class()
            return {
                "type": solver_type.value,
                "class": solver_class.__name__,
                "priority": solver.get_priority(),
                "available": True,
            }
        except Exception as e:
            return {
                "type": solver_type.value,
                "class": solver_class.__name__,
                "priority": 0,
                "available": False,
                "error": str(e),
            }
