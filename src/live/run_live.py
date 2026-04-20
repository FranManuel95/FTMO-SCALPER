"""
Punto de entrada CLI para el trading automático en MT5.

Ejemplos:
  # Dry-run local (sin enviar órdenes, sin MT5 real)
  python -m src.live.run_live --dry-run --fake

  # Demo real en MT5 (necesita MT5_LOGIN, MT5_PASSWORD, MT5_SERVER en env)
  python -m src.live.run_live --dry-run

  # Producción (FTMO) — solo tras validación en demo
  python -m src.live.run_live --live --confirm "I UNDERSTAND"
"""
from __future__ import annotations

import argparse
import logging
import sys

from dotenv import load_dotenv

load_dotenv()  # carga .env antes de leer os.environ

from src.core.logging import setup_logging
from src.features.technical.indicators import add_adx, add_atr
from src.features.trend.htf_filter import add_htf_trend

from .mt5_client import MT5Client, MT5Credentials
from .notifier import NullNotifier, TelegramNotifier
from .portfolio_runner import PortfolioRunner, StrategyConfig


# ── Builders de signal generators con parámetros validados ─────────────────────

def build_xauusd_pullback_1h():
    from src.signals.pullback.trend_pullback import (
        TrendPullbackConfig, generate_pullback_signals,
    )
    cfg = TrendPullbackConfig(adx_min=25, rr_target=2.5, htf_trend_enabled=True)
    def gen(df):
        return generate_pullback_signals(df, cfg)
    return gen


def build_gbpusd_pullback_1h():
    from src.signals.pullback.trend_pullback import (
        TrendPullbackConfig, generate_pullback_signals,
    )
    cfg = TrendPullbackConfig(adx_min=25, rr_target=2.5, htf_trend_enabled=True)
    def gen(df):
        return generate_pullback_signals(df, cfg)
    return gen


def build_usdjpy_pullback_1h():
    from src.signals.pullback.trend_pullback import (
        TrendPullbackConfig, generate_pullback_signals,
    )
    cfg = TrendPullbackConfig(adx_min=20, rr_target=2.5, htf_trend_enabled=True)
    def gen(df):
        return generate_pullback_signals(df, cfg)
    return gen


def build_xauusd_ny_orb_15m():
    from src.signals.breakout.ny_open_breakout import (
        NYOpenBreakoutConfig, generate_ny_open_breakout_signals,
    )
    cfg = NYOpenBreakoutConfig(adx_min=18, rr_target=2.5, htf_trend_enabled=True)
    def gen(df):
        return generate_ny_open_breakout_signals(df, cfg)
    return gen


def build_xauusd_london_orb_15m():
    from src.signals.breakout.london_open_breakout import (
        LondonOpenBreakoutConfig, generate_london_open_breakout_signals,
    )
    cfg = LondonOpenBreakoutConfig(adx_min=18, rr_target=2.5, htf_trend_enabled=True)
    def gen(df):
        return generate_london_open_breakout_signals(df, cfg)
    return gen


def build_default_portfolio() -> list[StrategyConfig]:
    """Las 5 estrategias validadas con sus parámetros óptimos."""
    return [
        StrategyConfig(
            strategy_id="xauusd_pullback_1h",
            symbol="XAUUSD", timeframe="1h",
            risk_pct=0.004, trail_atr_mult=0.3,      # 0.3 es el óptimo del sweep
            generator=build_xauusd_pullback_1h(),
        ),
        StrategyConfig(
            strategy_id="gbpusd_pullback_1h",
            symbol="GBPUSD", timeframe="1h",
            risk_pct=0.004, trail_atr_mult=0.5,
            generator=build_gbpusd_pullback_1h(),
        ),
        StrategyConfig(
            strategy_id="usdjpy_pullback_1h",
            symbol="USDJPY", timeframe="1h",
            risk_pct=0.003, trail_atr_mult=0.2,      # 0.2 es viable por spread bajo
            generator=build_usdjpy_pullback_1h(),
        ),
        StrategyConfig(
            strategy_id="xauusd_ny_orb_15m",
            symbol="XAUUSD", timeframe="15m",
            risk_pct=0.0025, trail_atr_mult=0.5,
            generator=build_xauusd_ny_orb_15m(),
        ),
        StrategyConfig(
            strategy_id="xauusd_london_orb_15m",
            symbol="XAUUSD", timeframe="15m",
            risk_pct=0.0025, trail_atr_mult=0.5,
            generator=build_xauusd_london_orb_15m(),
        ),
    ]


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Trading automático live en MT5")
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--dry-run", action="store_true",
                      help="Simula órdenes sin enviarlas a MT5 (default)")
    mode.add_argument("--live", action="store_true",
                      help="Envía órdenes reales — requiere --confirm")
    parser.add_argument("--confirm", default="",
                        help="Tipo exactamente 'I UNDERSTAND' para habilitar --live")
    parser.add_argument("--fake", action="store_true",
                        help="Usa cliente MT5 fake (dev/CI, sin terminal)")
    parser.add_argument("--tick-seconds", type=int, default=30,
                        help="Intervalo entre iteraciones (default 30s)")
    parser.add_argument("--once", action="store_true",
                        help="Ejecuta una sola iteración y sale (tests)")
    parser.add_argument("--no-telegram", action="store_true",
                        help="Desactiva notificaciones Telegram aunque haya env vars")
    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger(__name__)

    live_mode = args.live
    if live_mode and args.confirm != "I UNDERSTAND":
        logger.error("--live requiere --confirm 'I UNDERSTAND' para confirmar órdenes reales")
        return 2
    dry_run = not live_mode

    if args.fake:
        client = MT5Client(fake=True)
    else:
        creds = MT5Credentials.from_env()
        client = MT5Client(credentials=creds)

    if not client.connect():
        logger.error("No se pudo conectar a MT5 — abortando")
        return 1

    notifier = NullNotifier() if args.no_telegram else (TelegramNotifier.from_env() or NullNotifier())

    runner = PortfolioRunner(
        client=client,
        strategies=build_default_portfolio(),
        dry_run=dry_run,
        tick_interval_seconds=args.tick_seconds,
        notifier=notifier,
    )

    if args.once:
        runner.tick()
    else:
        runner.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
