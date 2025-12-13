# -*- coding: utf-8 -*-
"""
Utility helpers for configuring dedicated loggers per component in the
Function Exchange scenario.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional


# Comment: Determine the project root so all log files land under repo/logs.
def get_project_root(start_path: Optional[Path] = None) -> Path:
    """
    Walk up the directory tree (starting from the caller file) until we find
    a folder that contains pyproject.toml which is treated as the repo root.
    """
    current = start_path or Path(__file__).resolve()
    anchor = current if current.is_dir() else current.parent
    search_chain = [anchor] + list(anchor.parents)
    for candidate in search_chain:
        if (candidate / "pyproject.toml").exists():
            return candidate
    return anchor


# Comment: Configure a logger that writes to logs/<log_filename> and stdout.
def setup_component_logger(component_name: str, log_filename: str) -> logging.Logger:
    """
    Build or fetch a logger with both console and file handlers so every agent
    and the orchestrator can persist verbose traces to individual log files.
    """
    logger = logging.getLogger(component_name)
    logger.setLevel(logging.DEBUG)

    project_root = get_project_root()
    logs_dir = project_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = logs_dir / log_filename

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    )

    # Comment: Attach a file handler if it is not already wired.
    if not any(
        isinstance(handler, logging.FileHandler)
        and getattr(handler, "baseFilename", "") == str(log_file_path)
        for handler in logger.handlers
    ):
        file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Comment: Attach a stream handler once so logs also show up in stdout.
    if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger
