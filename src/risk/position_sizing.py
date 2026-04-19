def size_by_fixed_risk(
    account_balance: float,
    risk_pct: float,
    entry_price: float,
    stop_loss_price: float,
    pip_value: float = 1.0,
) -> float:
    """
    Calcula el tamaño de posición basado en riesgo fijo sobre el balance.

    Returns: número de unidades (lotes o contratos)
    """
    risk_amount = account_balance * risk_pct
    stop_distance = abs(entry_price - stop_loss_price)
    if stop_distance == 0:
        return 0.0
    return risk_amount / (stop_distance * pip_value)


def size_by_kelly(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    fraction: float = 0.25,
) -> float:
    """
    Fracción de Kelly para sizing. fraction=0.25 = cuarto Kelly (conservador).
    """
    if avg_loss == 0:
        return 0.0
    b = avg_win / avg_loss
    kelly = (b * win_rate - (1 - win_rate)) / b
    return max(0.0, kelly * fraction)
