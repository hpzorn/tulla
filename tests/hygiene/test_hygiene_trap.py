"""Tests for the trap handler for clean exit logging."""

import logging
import signal
from unittest.mock import MagicMock, patch

from tulla.hygiene.trap import (
    TRAPPED_SIGNALS,
    TrapContext,
    _make_atexit_handler,
    _make_signal_handler,
    install_trap_handler,
)


class TestTrapContext:
    """Tests for the TrapContext dataclass."""

    def test_initial_state(self) -> None:
        ctx = TrapContext(script_name="test-script")
        assert ctx.script_name == "test-script"
        assert ctx.exit_logged is False
        assert ctx.caught_signal is None
        assert ctx.original_handlers == {}

    def test_elapsed_secs(self) -> None:
        ctx = TrapContext(script_name="test-script")
        assert ctx.elapsed_secs >= 0.0

    def test_log_exit_emits_once(self, caplog: logging.LogRecord) -> None:  # type: ignore[type-arg]
        ctx = TrapContext(script_name="test-script")
        with caplog.at_level(logging.INFO):
            ctx.log_exit("test reason")
            ctx.log_exit("second call should be ignored")
        assert ctx.exit_logged is True
        info_messages = [r.message for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_messages) == 1
        assert "test-script" in info_messages[0]
        assert "test reason" in info_messages[0]

    def test_log_exit_includes_elapsed_time(self, caplog: logging.LogRecord) -> None:  # type: ignore[type-arg]
        ctx = TrapContext(script_name="my-tulla")
        with caplog.at_level(logging.INFO):
            ctx.log_exit("done")
        msg = caplog.records[0].message
        # Should contain the elapsed time in "after X.Xs" format.
        assert "after" in msg
        assert "my-tulla" in msg


class TestMakeSignalHandler:
    """Tests for the signal handler factory."""

    def test_handler_logs_exit_on_signal(self, caplog: logging.LogRecord) -> None:  # type: ignore[type-arg]
        ctx = TrapContext(script_name="sig-test")
        mock_exit = MagicMock()
        handler = _make_signal_handler(ctx, exit_func=mock_exit)

        with caplog.at_level(logging.INFO):
            handler(signal.SIGTERM.value, None)

        assert ctx.exit_logged is True
        assert ctx.caught_signal == signal.SIGTERM
        mock_exit.assert_called_once_with(128 + signal.SIGTERM.value)

    def test_handler_calls_exit_with_128_plus_signum(self) -> None:
        ctx = TrapContext(script_name="sig-test")
        mock_exit = MagicMock()
        handler = _make_signal_handler(ctx, exit_func=mock_exit)

        handler(signal.SIGINT.value, None)

        mock_exit.assert_called_once_with(128 + signal.SIGINT.value)

    def test_handler_restores_original_handler(self) -> None:
        ctx = TrapContext(script_name="sig-test")
        original = MagicMock()
        ctx.original_handlers[signal.SIGTERM.value] = original
        mock_exit = MagicMock()
        handler = _make_signal_handler(ctx, exit_func=mock_exit)

        with patch("tulla.hygiene.trap.signal.signal") as mock_signal:
            handler(signal.SIGTERM.value, None)
            mock_signal.assert_called_once_with(signal.SIGTERM.value, original)


class TestMakeAtexitHandler:
    """Tests for the atexit handler factory."""

    def test_logs_normal_shutdown_when_no_signal(self, caplog: logging.LogRecord) -> None:  # type: ignore[type-arg]
        ctx = TrapContext(script_name="atexit-test")
        handler = _make_atexit_handler(ctx)

        with caplog.at_level(logging.INFO):
            handler()

        assert ctx.exit_logged is True
        info_messages = [r.message for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_messages) == 1
        assert "normal shutdown" in info_messages[0]

    def test_does_not_log_if_signal_caught(self, caplog: logging.LogRecord) -> None:  # type: ignore[type-arg]
        ctx = TrapContext(script_name="atexit-test")
        ctx.caught_signal = signal.SIGTERM
        handler = _make_atexit_handler(ctx)

        with caplog.at_level(logging.INFO):
            handler()

        # Should not log because signal handler already logged.
        assert ctx.exit_logged is False


class TestInstallTrapHandler:
    """Tests for the main install_trap_handler function."""

    def test_returns_callable_cleanup(self) -> None:
        cleanup = install_trap_handler("test-script", exit_func=MagicMock())
        assert callable(cleanup)
        cleanup()  # Should not raise.

    def test_installs_signal_handlers(self) -> None:
        original_handlers = {}
        for sig in TRAPPED_SIGNALS:
            original_handlers[sig] = signal.getsignal(sig)

        try:
            install_trap_handler("test-script", exit_func=MagicMock())
            for sig in TRAPPED_SIGNALS:
                current = signal.getsignal(sig)
                # Handler should have been replaced (not the original).
                assert current != original_handlers[sig]
        finally:
            # Restore original handlers.
            for sig in TRAPPED_SIGNALS:
                signal.signal(sig, original_handlers[sig])

    def test_cleanup_restores_original_handlers(self) -> None:
        original_handlers = {}
        for sig in TRAPPED_SIGNALS:
            original_handlers[sig] = signal.getsignal(sig)

        cleanup = install_trap_handler("test-script", exit_func=MagicMock())
        cleanup()

        for sig in TRAPPED_SIGNALS:
            current = signal.getsignal(sig)
            assert current == original_handlers[sig]

    def test_cleanup_logs_exit(self, caplog: logging.LogRecord) -> None:  # type: ignore[type-arg]
        cleanup = install_trap_handler("cleanup-test", exit_func=MagicMock())
        with caplog.at_level(logging.INFO):
            cleanup()
        info_messages = [r.message for r in caplog.records if r.levelno == logging.INFO]
        assert any("cleanup called" in m for m in info_messages)

        # Restore handlers (cleanup already did this).

    def test_custom_signals(self) -> None:
        """Test that only specified signals are trapped."""
        original_sigterm = signal.getsignal(signal.SIGTERM)
        original_sigint = signal.getsignal(signal.SIGINT)

        try:
            # Only trap SIGTERM.
            cleanup = install_trap_handler(
                "test-script",
                signals=(signal.SIGTERM,),
                exit_func=MagicMock(),
            )
            # SIGTERM should be changed.
            assert signal.getsignal(signal.SIGTERM) != original_sigterm
            # SIGINT should NOT be changed.
            assert signal.getsignal(signal.SIGINT) == original_sigint
            cleanup()
        finally:
            signal.signal(signal.SIGTERM, original_sigterm)
            signal.signal(signal.SIGINT, original_sigint)
