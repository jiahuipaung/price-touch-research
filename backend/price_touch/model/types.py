from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ProbabilityMatrix:
    values: np.ndarray
    method: str
    path_count: int = 0
    simulation_batches: int = 0

    def is_valid(self) -> bool:
        return bool(np.isfinite(self.values).all() and ((self.values >= 0) & (self.values <= 1)).all())
