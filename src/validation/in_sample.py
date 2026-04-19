import pandas as pd


def split_in_sample(df: pd.DataFrame, train_ratio: float = 0.7) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Divide el dataset en in-sample y out-of-sample por fecha."""
    split_idx = int(len(df) * train_ratio)
    return df.iloc[:split_idx].copy(), df.iloc[split_idx:].copy()


def split_by_date(
    df: pd.DataFrame,
    train_end: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Divide en IS/OOS usando una fecha fija como corte."""
    cutoff = pd.Timestamp(train_end, tz="UTC")
    return df[df.index < cutoff].copy(), df[df.index >= cutoff].copy()
