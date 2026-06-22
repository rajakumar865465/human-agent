from __future__ import annotations

import logging
import sys
from pathlib import Path

try:
    from loguru import logger as _loguru_logger
except ModuleNotFoundError:
    _loguru_logger = None

_CONFIGURED = False


class _StdLoggerAdapter:
    def __init__(self, logger: logging.Logger, module: str):
        self._logger = logger
        self._module = module

    def bind(self, **kwargs):
        module = kwargs.get("module", self._module)
        return _StdLoggerAdapter(self._logger, module)

    def info(self, message: str, *args, **kwargs):
        self._logger.info(f"[{self._module}] {message}", *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        self._logger.warning(f"[{self._module}] {message}", *args, **kwargs)

    def exception(self, message: str, *args, **kwargs):
        self._logger.exception(f"[{self._module}] {message}", *args, **kwargs)

    def debug(self, message: str, *args, **kwargs):
        self._logger.debug(f"[{self._module}] {message}", *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        self._logger.error(f"[{self._module}] {message}", *args, **kwargs)


def get_logger(name: str, log_dir: Path | None = None):
    global _CONFIGURED
    target_dir = log_dir or Path("reports/logs")
    target_dir.mkdir(parents=True, exist_ok=True)

    if _loguru_logger is None:
        root_logger = logging.getLogger("supervisor")
        if not root_logger.handlers:
            root_logger.setLevel(logging.INFO)
            stream_handler = logging.StreamHandler(sys.stderr)
            stream_handler.setLevel(logging.INFO)
            file_handler = logging.FileHandler(target_dir / "supervisor.log", encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
            stream_handler.setFormatter(formatter)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(stream_handler)
            root_logger.addHandler(file_handler)
        return _StdLoggerAdapter(root_logger, name)

    if not _CONFIGURED:
        _loguru_logger.remove()
        _loguru_logger.add(sys.stderr, level="INFO")
        _loguru_logger.add(target_dir / "supervisor.log", rotation="5 MB", retention="7 days", level="DEBUG")
        _CONFIGURED = True

    return _loguru_logger.bind(module=name)
