"""Helpers de formateo para mostrar números en el dashboard."""
from __future__ import annotations


def fmt_eur(x: float | None, sign: bool = False) -> str:
    if x is None:
        return "—"
    fmt = "+,.2f" if sign else ",.2f"
    return f"€{x:{fmt}}"


def fmt_pct(x: float | None, decimals: int = 1) -> str:
    if x is None:
        return "—"
    return f"{x:.{decimals}f}%"


def fmt_pips(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x:+.1f} pips"


def fmt_duration(seconds: int | float | None) -> str:
    if seconds is None or seconds < 0:
        return "—"
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60}s"
    h = s // 3600
    m = (s % 3600) // 60
    return f"{h}h {m}m" if h < 24 else f"{h // 24}d {h % 24}h"


def fmt_signed(x: float | None, decimals: int = 2) -> str:
    if x is None:
        return "—"
    return f"{x:+.{decimals}f}"


def trend_arrow(delta: float, threshold: float = 0.0) -> str:
    if delta > threshold:
        return "▲"
    if delta < -threshold:
        return "▼"
    return "▬"


def severity_color(severity: str) -> str:
    return {"high": "🔴", "medium": "🟡", "low": "🔵"}.get(severity, "⚪")
