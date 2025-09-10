"""Factory for creating CAPTCHA solvers with fallback chain."""

from enum import Enum
from typing import List, Type, Dict, Optional
from .base import CaptchaSolver
from .solvers import (
    BrowserbaseCaptchaSolver,
    ManualCaptchaSolver,
    NoopCaptchaSolver,
)


class CaptchaSolverType(str, Enum):
    """CAPTCHA solver types."""

    BROWSERBASE = "browserbase"
    MANUAL = "manual"
    NOOP = "noop"


class CaptchaSolverFactory:
    """Factory for creating CAPTCHA solvers with fallback chain."""

    _solvers: Dict[CaptchaSolverType, Type[CaptchaSolver]] = {
        CaptchaSolverType.BROWSERBASE: BrowserbaseCaptchaSolver,
        CaptchaSolverType.MANUAL: ManualCaptchaSolver,
        CaptchaSolverType.NOOP: NoopCaptchaSolver,
    }

    @classmethod
    def create_solver_chain(
        cls, preferred_solvers: List[CaptchaSolverType]
    ) -> List[CaptchaSolver]:
        """Create a chain of CAPTCHA solvers with fallback."""
        solvers = []
        for solver_type in preferred_solvers:
            solver_class = cls._solvers.get(solver_type)
            if solver_class:
                solvers.append(solver_class())
        return sorted(solvers, key=lambda s: s.get_priority(), reverse=True)
