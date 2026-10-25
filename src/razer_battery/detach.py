"""Decide how the tray restarts itself without a console window; no Windows calls here.

A double-clicked console exe gets a console window that stays open as long as any process
is attached to it. The PyInstaller one-file exe runs as a launcher plus a child, so the
child cannot close the window by detaching alone; starting a fresh copy whose console has
no window and exiting both processes does.
"""

import os
from collections.abc import Mapping

MARKER = "RAZER_BATTERY_DETACHED"


def should_detach(has_console: bool, env: Mapping[str, str]) -> bool:
    # The marker stops a detached copy from restarting itself again.
    return has_console and env.get(MARKER) != "1"


def detached_command(executable: str, argv: list[str], frozen: bool) -> list[str]:
    # A frozen exe is its own interpreter; python.exe needs the script path again.
    if frozen:
        return [executable, *argv[1:]]
    return [executable, os.path.abspath(argv[0]), *argv[1:]]


def detached_env(env: Mapping[str, str]) -> dict[str, str]:
    result = dict(env)
    result[MARKER] = "1"
    # Makes a PyInstaller one-file exe unpack itself again instead of reusing this process's
    # temporary folder, which is deleted when this process exits.
    result["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return result
