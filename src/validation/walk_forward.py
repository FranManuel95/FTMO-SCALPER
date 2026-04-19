from dataclasses import dataclass
from typing import Callable, Sequence

import pandas as pd

from src.core.types import Trade


@dataclass
class WFWindow:
    train: pd.DataFrame
    test: pd.DataFrame
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def walk_forward_windows(
    df: pd.DataFrame,
    train_months: int = 6,
    test_months: int = 1,
) -> list[WFWindow]:
    windows = []
    start = df.index[0]
    end = df.index[-1]

    train_delta = pd.DateOffset(months=train_months)
    test_delta = pd.DateOffset(months=test_months)

    current = start
    while current + train_delta + test_delta <= end:
        train_end = current + train_delta
        test_end = train_end + test_delta

        train_df = df[(df.index >= current) & (df.index < train_end)]
        test_df = df[(df.index >= train_end) & (df.index < test_end)]

        if len(train_df) > 0 and len(test_df) > 0:
            windows.append(WFWindow(
                train=train_df,
                test=test_df,
                train_start=current,
                train_end=train_end,
                test_start=train_end,
                test_end=test_end,
            ))

        current += test_delta

    return windows


def walk_forward_efficiency(is_pf: float, oos_pf: float) -> float | None:
    """
    WFE: qué fracción del edge IS se mantiene en OOS. Objetivo ≥ 0.5.
    Retorna None cuando IS PF < 1.2 — denominador demasiado pequeño para
    que el ratio sea estable o interpretable.
    """
    if is_pf < 1.2:
        return None
    return (oos_pf - 1.0) / (is_pf - 1.0)
