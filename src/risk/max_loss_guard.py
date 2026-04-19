class MaxLossGuard:
    """
    Bloquea el sistema si se alcanza la pérdida máxima total (drawdown FTMO).
    """

    def __init__(self, initial_balance: float, max_loss_pct: float = 0.10):
        self.initial_balance = initial_balance
        self.max_loss_limit = initial_balance * (1 - max_loss_pct)
        self.current_balance = initial_balance
        self._triggered = False

    def update(self, pnl: float) -> None:
        self.current_balance += pnl
        if self.current_balance <= self.max_loss_limit:
            self._triggered = True

    def is_triggered(self) -> bool:
        return self._triggered

    @property
    def drawdown_pct(self) -> float:
        return (self.initial_balance - self.current_balance) / self.initial_balance
