import os

from razer_battery import detach


def test_detaches_only_with_a_console_and_only_once():
    assert detach.should_detach(True, {})
    assert not detach.should_detach(False, {})
    assert not detach.should_detach(True, {detach.MARKER: "1"})


def test_frozen_exe_is_restarted_with_its_own_arguments():
    command = detach.detached_command(r"C:\x\razer-battery.exe", [r"C:\x\razer-battery.exe", "--tray"], frozen=True)
    assert command == [r"C:\x\razer-battery.exe", "--tray"]


def test_script_is_restarted_through_the_interpreter_with_an_absolute_path():
    command = detach.detached_command("python.exe", ["app.py", "--tray", "--interval", "30"], frozen=False)
    assert command == ["python.exe", os.path.abspath("app.py"), "--tray", "--interval", "30"]


def test_env_marks_the_copy_and_resets_pyinstaller_without_touching_the_original():
    original = {"PATH": "p"}
    env = detach.detached_env(original)
    assert env == {"PATH": "p", detach.MARKER: "1", "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    assert original == {"PATH": "p"}
    assert not detach.should_detach(True, env)
