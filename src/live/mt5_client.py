"""
MT5Client — wrapper sobre la librería MetaTrader5.

Maneja inicialización, reconexión automática y abstrae el acceso al terminal.
Si la librería MetaTrader5 no está instalada (entorno Linux/CI), el cliente
opera en modo FAKE para permitir tests sin MT5 real.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as mt5  # type: ignore
    _HAS_MT5 = True
except ImportError:
    mt5 = None  # type: ignore
    _HAS_MT5 = False
    logger.warning("MetaTrader5 no instalado — MT5Client operará en modo FAKE")


@dataclass
class MT5Credentials:
    login: int
    password: str
    server: str
    path: str | None = None          # ruta al terminal.exe (opcional)
    timeout_ms: int = 60_000

    @classmethod
    def from_env(cls) -> "MT5Credentials":
        return cls(
            login=int(os.environ["MT5_LOGIN"]),
            password=os.environ["MT5_PASSWORD"],
            server=os.environ["MT5_SERVER"],
            path=os.environ.get("MT5_PATH"),
            timeout_ms=int(os.environ.get("MT5_TIMEOUT_MS", 60_000)),
        )


class MT5Client:
    """Cliente resiliente para MT5 con reconexión automática."""

    def __init__(self, credentials: MT5Credentials | None = None, fake: bool = False):
        self.credentials = credentials
        self.fake = fake or not _HAS_MT5
        self._connected = False
        if self.fake:
            logger.info("MT5Client inicializado en modo FAKE (sin conexión real)")

    def connect(self) -> bool:
        if self.fake:
            self._connected = True
            return True
        if self.credentials is None:
            raise ValueError("Credentials requeridas para conexión real")

        init_kwargs = {
            "login": self.credentials.login,
            "password": self.credentials.password,
            "server": self.credentials.server,
            "timeout": self.credentials.timeout_ms,
        }
        if self.credentials.path:
            init_kwargs["path"] = self.credentials.path

        if not mt5.initialize(**init_kwargs):
            err = mt5.last_error()
            logger.error(f"MT5 initialize failed: {err}")
            return False

        self._connected = True
        info = mt5.account_info()
        logger.info(
            f"Conectado a MT5 | Cuenta {info.login} | "
            f"Balance {info.balance:.2f} {info.currency} | Servidor {info.server}"
        )
        return True

    def ensure_connected(self, max_retries: int = 3) -> bool:
        if self.fake:
            return True
        for attempt in range(1, max_retries + 1):
            if mt5.terminal_info() is not None and mt5.account_info() is not None:
                return True
            logger.warning(f"MT5 desconectado — intento reconexión {attempt}/{max_retries}")
            mt5.shutdown()
            time.sleep(2 ** attempt)
            if self.connect():
                return True
        logger.error("No se pudo reconectar a MT5")
        return False

    def disconnect(self) -> None:
        if not self.fake and self._connected:
            mt5.shutdown()
        self._connected = False

    def account_balance(self) -> float:
        if self.fake:
            return 10_000.0
        info = mt5.account_info()
        return float(info.balance) if info else 0.0

    def account_equity(self) -> float:
        if self.fake:
            return 10_000.0
        info = mt5.account_info()
        return float(info.equity) if info else 0.0

    @property
    def raw(self):
        """Acceso al módulo mt5 raw para operaciones específicas."""
        if self.fake:
            raise RuntimeError("Modo FAKE no expone módulo MT5 raw")
        return mt5
