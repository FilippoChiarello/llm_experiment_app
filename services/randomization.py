from __future__ import annotations

import random
from typing import Dict, List


def choose_balanced_condition(
    active_conditions: List[Dict[str, object]],
    condition_counts: Dict[str, int],
) -> Dict[str, object]:
    if not active_conditions:
        raise ValueError("At least one active condition is required")
    minimum_count = min(condition_counts.get(str(condition["id"]), 0) for condition in active_conditions)
    candidates = [
        condition
        for condition in active_conditions
        if condition_counts.get(str(condition["id"]), 0) == minimum_count
    ]
    return random.choice(candidates)

