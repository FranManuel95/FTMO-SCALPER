"""Smoke tests: verificar que todos los módulos importan correctamente."""


def test_core_imports():
    from src.core.types import Trade, Signal, Side, MarketRegime
    from src.core.paths import ROOT, DATA_DIR
    from src.core.utils import load_yaml, timestamp_str


def test_risk_imports():
    from src.risk.position_sizing import size_by_fixed_risk
    from src.risk.daily_loss_guard import DailyLossGuard
    from src.risk.max_loss_guard import MaxLossGuard


def test_metrics_imports():
    from src.metrics.performance import profit_factor, win_rate, summary
    from src.metrics.drawdown import max_drawdown
    from src.metrics.ftmo_checks import run_all_checks
    from src.metrics.consistency import monthly_returns


def test_validation_imports():
    from src.validation.in_sample import split_in_sample
    from src.validation.walk_forward import walk_forward_windows
    from src.validation.monte_carlo import monte_carlo_drawdown
    from src.validation.stress_tests import run_stress_suite


def test_signals_imports():
    from src.signals.breakout.london_breakout import generate_london_breakout_signals
    from src.signals.pullback.trend_pullback import generate_pullback_signals
