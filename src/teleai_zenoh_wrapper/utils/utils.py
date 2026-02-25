import os
import time

import ctypes
import os
import logging
import sys

import colorlog


class EndAwareLogger(logging.Logger):
    """A drop-in Logger that supports print-like `end=` for stdout terminator.

    Backward-compatible: existing `logger.info("...")` calls keep working.
    New: `logger.info("...", end="")` (or any string) controls the handler terminator.
    """

    # Match stdlib signature but tolerate extra kwargs (like `end`).
    def _log(
        self,
        level,
        msg,
        args,
        exc_info=None,
        extra=None,
        stack_info=False,
        stacklevel=1,
        **kwargs,
    ):
        _sentinel = object()
        end = kwargs.pop("end", _sentinel)
        flush = kwargs.pop("flush", _sentinel)

        if kwargs:
            # Preserve default behavior: unknown kwargs should still be an error
            # to avoid silently swallowing mistakes.
            unknown = ", ".join(sorted(kwargs.keys()))
            raise TypeError(f"unexpected keyword argument(s): {unknown}")

        if extra is None:
            extra = {}
        else:
            # avoid mutating caller dict
            extra = dict(extra)

        # Per-record terminator info consumed by our handler.
        # - If caller provided `end=`, it must win over any `extra` value.
        # - If not provided, let handler default to '\n' (or `extra['end']` if set).
        if end is not _sentinel:
            extra["end"] = end
        if flush is not _sentinel:
            extra["flush"] = flush

        super()._log(
            level,
            msg,
            args,
            exc_info=exc_info,
            extra=extra,
            stack_info=stack_info,
            stacklevel=stacklevel,
        )


class EndAwareStreamHandler(colorlog.StreamHandler):
    """StreamHandler that reads per-record `end` and uses it as terminator."""

    def emit(self, record):
        # StreamHandler uses `self.terminator`; make it record-specific.
        original_terminator = getattr(self, "terminator", "\n")
        try:
            record_end = getattr(record, "end", original_terminator)

            # If the previous log used a non-newline terminator (progress-style output),
            # ensure the next *normal* log starts on a fresh line.
            if getattr(self, "_needs_newline", False) and record_end == "\n":
                try:
                    self.stream.write("\n")
                    self.flush()
                except Exception:
                    pass
                self._needs_newline = False

            self.terminator = record_end
            super().emit(record)

            # Track whether we're currently mid-line.
            self._needs_newline = self.terminator != "\n"

            if getattr(record, "flush", False):
                self.flush()
        finally:
            self.terminator = original_terminator


def setup_logger():
    logger = logging.getLogger("Teleai_vla_deploy")
    if not isinstance(logger, EndAwareLogger):
        # Upgrade the existing logger instance in-place to keep references valid.
        logger.__class__ = EndAwareLogger

    # Avoid duplicate console prints:
    # - `propagate=False` prevents bubbling to root logger.
    # - removing existing StreamHandlers prevents multiple console handlers.
    for h in list(logger.handlers):
        if isinstance(h, logging.StreamHandler):
            logger.removeHandler(h)

    handler = EndAwareStreamHandler(stream=sys.stdout)
    handler.setFormatter(
        colorlog.ColoredFormatter(
            # Only colorize the level name; keep everything else base/white.
            "%(white)s[%(log_color)s%(levelname)s%(reset)s%(white)s] "
            "[%(name)s] %(message)s%(reset)s",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
            reset=True,
        )
    )
    logger.addHandler(handler)

    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


logger = setup_logger()


class Timespec(ctypes.Structure):
    _fields_ = [
        ("tv_sec", ctypes.c_long),
        ("tv_nsec", ctypes.c_long)
    ]

libc = ctypes.CDLL("libc.so.6")
nanosleep_func = libc.nanosleep



def nano_sleep(ns):
    req = Timespec(ns // 1_000_000_000, ns % 1_000_000_000)
    rem = Timespec(0, 0)
    nanosleep_func(ctypes.byref(req), ctypes.byref(rem))

def get_nano():
    return time.clock_gettime_ns(time.CLOCK_REALTIME)