import numpy as np
import pandas as pd


def max_drawdown(equity_curve: pd.Series) -> float:
    """Retorna el max drawdown como fracción (0.10 = 10%)."""
    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / rolling_max
    return float(drawdown.min())


def max_drawdown_duration(equity_curve: pd.Series) -> int:
    """Retorna la duración del max drawdown en número de barras."""
    rolling_max = equity_curve.cummax()
    underwater = equity_curve < rolling_max
    durations = []
    count = 0
    for u in underwater:
        if u:
            count += 1
        else:
            if count > 0:
                durations.append(count)
            count = 0
    return max(durations) if durations else 0


def drawdown_series(equity_curve: pd.Series) -> pd.Series:
    rolling_max = equity_curve.cummax()
    return (equity_curve - rolling_max) / rolling_max


def calmar_ratio(equity_curve: pd.Series, periods_per_year: int = 252) -> float:
    dd = abs(max_drawdown(equity_curve))
    if dd == 0:
        return 0.0
    annual_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (periods_per_year / len(equity_curve)) - 1
    return annual_return / dd
