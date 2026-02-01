"""Trap handler for clean exit logging in Ralph scripts.

Installs signal handlers that log a clean shutdown message when a
Ralph script is interrupted or terminated. This ensures that even
abnormal exits produce structured log output useful for debugging
and post-mortem analysis.

Trapped signals:
    - SIGINT  (Ctrl-C / keyboard interrupt)
    - SIGTERM (graceful termination request)

Usage::

    from ralph.hygiene import install_trap_handler

    def main() -> None:
        cleanup = install_trap_handler(script_name="research-ralph")
        try:
            # ... main logic ...
        finally:
            cleanup()
"""

from __future__ import annotations

import atexit
import logging
import signal
import sys
import time
from dataclasses import dataclass, field
from types import FrameType
from typing import Callable

logger = logging.getLogger(__name__)

# Signals we trap for clean exit logging.
TRAPPED_SIGNALS: tuple[signal.Signals, ...] = (signal.SIGINT, signal.SIGTERM)


@dataclass
class TrapContext:
    """Mutable context tracking the state of an installed trap handler.

    Attributes:
        script_name: Name of the Ralph script that installed the trap.
        start_time: Monotonic timestamp when the trap was installed.
        exit_logged: Whether the exit log message has already been emitted.
        original_handlers: Original signal handlers saved before installation,
            keyed by signal number.
        caught_signal: The signal that triggered the handler, if any.
    """

    script_name: str
    start_time: float = field(default_factory=time.monotonic)
    exit_logged: bool = False
    original_handlers: dict[int, signal.Handlers | Callable[..., object] | int | None] = field(
        default_factory=dict,
    )
    caught_signal: signal.Signals | None = None

    @property
    def elapsed_secs(self) -> float:
        """Seconds elapsed since the trap was installed."""
        return time.monotonic() - self.start_time

    def log_exit(self, reason: str) -> None:
        """Emit the clean exit log message exactly once.

        Args:
            reason: Human-readable description of why the script is exiting.
        """
        if self.exit_logged:
            return
        self.exit_logged = True
        elapsed = self.elapsed_secs
        logger.info(
            "[%s] Clean exit: %s (after %.1fs)",
            self.script_name,
            reason,
            elapsed,
        )


def _make_signal_handler(
    ctx: TrapContext,
    *,
    exit_func: Callable[[int], object] | None = None,
) -> Callable[[int, FrameType | None], None]:
    """Create a signal handler closure bound to the given TrapContext.

    Args:
        ctx: The trap context to update when a signal is caught.
        exit_func: Callable to terminate the process. Defaults to sys.exit.

    Returns:
        A signal handler function with the standard (signum, frame) signature.
    """
    if exit_func is None:
        exit_func = sys.exit

    def handler(signum: int, frame: FrameType | None) -> None:
        sig = signal.Signals(signum)
        ctx.caught_signal = sig
        ctx.log_exit(f"received {sig.name} (signal {signum})")

        # Restore original handler to avoid recursive trapping, then re-raise.
        original = ctx.original_handlers.get(signum)
        if original is not None and callable(original):
            signal.signal(signum, original)

        exit_func(128 + signum)

    return handler


def _make_atexit_handler(ctx: TrapContext) -> Callable[[], None]:
    """Create an atexit handler that logs normal exit if no signal was caught.

    Args:
        ctx: The trap context to check and update.

    Returns:
        A no-argument callable suitable for atexit.register.
    """

    def handler() -> None:
        if ctx.caught_signal is None:
            ctx.log_exit("normal shutdown")

    return handler


def install_trap_handler(
    script_name: str,
    *,
    signals: tuple[signal.Signals, ...] = TRAPPED_SIGNALS,
    exit_func: Callable[[int], object] | None = None,
) -> Callable[[], None]:
    """Install signal and atexit handlers for clean exit logging.

    This is the main entry point for the trap subsystem. It:
      1. Creates a TrapContext bound to the script name.
      2. Installs signal handlers for SIGINT and SIGTERM that log
         the exit reason before terminating.
      3. Registers an atexit handler that logs normal shutdown if
         no signal was caught.
      4. Returns a cleanup callable that can be invoked to manually
         log exit and restore original signal handlers.

    Args:
        script_name: Name of the Ralph script (used in log messages).
        signals: Tuple of signals to trap. Defaults to (SIGINT, SIGTERM).
        exit_func: Callable to terminate the process in signal handlers.
            Defaults to sys.exit.

    Returns:
        A cleanup callable. When called, it logs normal exit (if not
        already logged) and restores original signal handlers.
    """
    ctx = TrapContext(script_name=script_name)
    sig_handler = _make_signal_handler(ctx, exit_func=exit_func)

    # Install signal handlers, saving originals for restoration.
    for sig in signals:
        try:
            original = signal.getsignal(sig)
            ctx.original_handlers[sig.value] = original
            signal.signal(sig, sig_handler)
            logger.debug("[%s] Installed trap for %s", script_name, sig.name)
        except (OSError, ValueError) as exc:
            # Some signals can't be caught (e.g., in non-main thread).
            logger.debug(
                "[%s] Cannot trap %s: %s", script_name, sig.name, exc,
            )

    # Install atexit handler for normal shutdown logging.
    atexit_handler = _make_atexit_handler(ctx)
    atexit.register(atexit_handler)
    logger.debug("[%s] Installed atexit handler for clean exit logging", script_name)

    def cleanup() -> None:
        """Restore original signal handlers and log exit if needed."""
        ctx.log_exit("cleanup called")
        for sig in signals:
            original = ctx.original_handlers.get(sig.value)
            if original is not None:
                try:
                    signal.signal(sig, original)
                except (OSError, ValueError):
                    pass

    return cleanup
