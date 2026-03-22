"""
Sleep prevention utility for the Polymarket Trading Bot.

Prevents the OS from sleeping while the bot is running.
- Windows: SetThreadExecutionState via ctypes
- Linux/Mac: subprocess call to caffeinate / systemd-inhibit

Usage:
    from utils.sleep_prevention import prevent_sleep, allow_sleep
    prevent_sleep()   # call at bot start
    allow_sleep()     # call at graceful shutdown
"""

import platform
import subprocess
from utils.logger import get_logger

logger = get_logger(__name__)

# Track subprocess handle for macOS/Linux
_caffeinate_proc = None


def prevent_sleep() -> None:
    """Prevent the operating system from sleeping."""
    global _caffeinate_proc
    system = platform.system()

    try:
        if system == "Windows":
            import ctypes
            # ES_CONTINUOUS | ES_SYSTEM_REQUIRED = 0x80000002
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000002)
            logger.info("Sleep prevention enabled (Windows SetThreadExecutionState)")

        elif system == "Darwin":  # macOS
            _caffeinate_proc = subprocess.Popen(
                ["caffeinate", "-i"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Sleep prevention enabled (macOS caffeinate)")

        elif system == "Linux":
            _caffeinate_proc = subprocess.Popen(
                ["systemd-inhibit", "--what=idle", "--who=polymarket-bot",
                 "--why=Trading bot running", "sleep", "infinity"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("Sleep prevention enabled (Linux systemd-inhibit)")

        else:
            logger.warning(f"Sleep prevention not supported on {system}")

    except Exception as e:
        logger.warning(f"Failed to enable sleep prevention: {e}")


def allow_sleep() -> None:
    """Re-allow the operating system to sleep."""
    global _caffeinate_proc
    system = platform.system()

    try:
        if system == "Windows":
            import ctypes
            # ES_CONTINUOUS only = clear SYSTEM_REQUIRED flag
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            logger.info("Sleep prevention disabled (Windows)")

        elif system in ("Darwin", "Linux"):
            if _caffeinate_proc is not None:
                _caffeinate_proc.terminate()
                _caffeinate_proc.wait(timeout=5)
                _caffeinate_proc = None
                logger.info(f"Sleep prevention disabled ({system})")

        else:
            logger.warning(f"Sleep prevention cleanup not supported on {system}")

    except Exception as e:
        logger.warning(f"Failed to disable sleep prevention: {e}")
