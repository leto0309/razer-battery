import json

import pytest

from razer_battery import cli, protocol
from razer_battery.device import DeviceNotFound, Reading

READING = Reading("DeathAdder V3 Pro (wireless)", 67, False)


def raises(error):
    def read():
        raise error
    return read


def test_prints_reading(capsys):
    assert cli.main([], read=lambda: READING) == cli.EXIT_OK
    assert capsys.readouterr().out.strip() == "Razer DeathAdder V3 Pro (wireless): 67%（未充电）"


def test_json_output(capsys):
    assert cli.main(["--json"], read=lambda: READING) == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out) == {
        "model": "DeathAdder V3 Pro (wireless)", "percent": 67, "charging": False,
    }


def test_missing_device_exits_2(capsys):
    assert cli.main([], read=raises(DeviceNotFound("未找到"))) == cli.EXIT_NOT_FOUND
    assert "未找到" in capsys.readouterr().err


@pytest.mark.parametrize("error", [protocol.ProtocolError("鼠标未响应"), OSError("拒绝访问")])
def test_read_failures_exit_3(capsys, error):
    assert cli.main([], read=raises(error)) == cli.EXIT_READ_FAILED
    assert "读取失败" in capsys.readouterr().err


def test_non_windows_is_refused(capsys):
    assert cli.main([], platform="linux") == cli.EXIT_UNSUPPORTED
    assert "Windows" in capsys.readouterr().err


def test_self_test_needs_no_hardware(capsys):
    assert cli.main(["--self-test"], platform="linux") == cli.EXIT_OK
    assert "ok" in capsys.readouterr().out


def test_interval_has_a_minimum():
    with pytest.raises(SystemExit):
        cli.main(["--tray", "--interval", "1"], read=lambda: READING)


def test_modes_are_exclusive():
    with pytest.raises(SystemExit):
        cli.main(["--json", "--tray"], read=lambda: READING)
