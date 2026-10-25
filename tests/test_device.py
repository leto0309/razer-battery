import pytest

from razer_battery import device, protocol


class FakeMouse:
    """Answers like the real receiver: echoes the request with a status and values."""

    def __init__(self, battery=0xAB, charging=0, busy_polls=0, status=protocol.STATUS_OK, interference=()):
        self.values = {protocol.CMD_BATTERY: battery, protocol.CMD_CHARGING: charging}
        self.busy_polls = busy_polls
        self.status = status
        # Replies another program caused, returned once each before the real answers.
        self.interference = list(interference)
        self.sent = []
        self.polls = 0

    def send(self, report):
        self.sent.append(report)
        self.remaining_busy = self.busy_polls

    def receive(self):
        self.polls += 1
        if self.interference:
            return self.interference.pop(0)
        reply = bytearray(self.sent[-1])
        if self.remaining_busy:
            self.remaining_busy -= 1
            reply[0] = protocol.STATUS_BUSY
            return bytes(reply)
        reply[0] = self.status
        reply[protocol.ARGS_OFFSET + 1] = self.values[(reply[6], reply[7])]
        return bytes(reply)


def no_sleep(_):
    pass


def test_reads_percent_and_charging():
    mouse = FakeMouse(battery=0xAB, charging=1)
    reading = device.read_battery(mouse, "DeathAdder V3 Pro (wireless)", sleep=no_sleep)
    assert reading == device.Reading("DeathAdder V3 Pro (wireless)", 67, True)
    assert [(r[6], r[7]) for r in mouse.sent] == [protocol.CMD_BATTERY, protocol.CMD_CHARGING]


def test_not_charging_when_flag_is_zero():
    reading = device.read_battery(FakeMouse(battery=255, charging=0), "m", sleep=no_sleep)
    assert (reading.percent, reading.charging) == (100, False)


def test_busy_replies_are_retried():
    mouse = FakeMouse(busy_polls=3)
    assert device.query(mouse, protocol.CMD_BATTERY, sleep=no_sleep)[1] == 0xAB
    assert mouse.polls == 4
    assert len(mouse.sent) == 1


def test_gives_up_when_device_stays_busy():
    mouse = FakeMouse(busy_polls=100)
    with pytest.raises(protocol.ProtocolError, match="持续忙"):
        device.query(mouse, protocol.CMD_BATTERY, attempts=5, rounds=3, sleep=no_sleep)
    assert (len(mouse.sent), mouse.polls) == (3, 15)


def test_sleeping_mouse_reports_timeout_after_resending():
    mouse = FakeMouse(status=protocol.STATUS_TIMEOUT)
    with pytest.raises(protocol.ProtocolError, match="休眠"):
        device.read_battery(mouse, "m", sleep=no_sleep)
    assert (len(mouse.sent), mouse.polls) == (3, 3)


def synapse_reply(status):
    # Captured from the real receiver while Razer Synapse was running.
    reply = bytearray(protocol.build_request(0x0F, 0x03, data_size=0x08, transaction_id=0x10))
    reply[0] = status
    return bytes(reply)


def test_reply_meant_for_synapse_makes_us_send_again():
    mouse = FakeMouse(interference=[synapse_reply(protocol.STATUS_FAILURE)])
    assert device.query(mouse, protocol.CMD_BATTERY, sleep=no_sleep)[1] == 0xAB
    assert len(mouse.sent) == 2


def test_our_command_failing_once_is_sent_again():
    failed = bytearray(protocol.build_request(*protocol.CMD_BATTERY))
    failed[0] = protocol.STATUS_FAILURE
    mouse = FakeMouse(interference=[bytes(failed)])
    assert device.query(mouse, protocol.CMD_BATTERY, sleep=no_sleep)[1] == 0xAB
    assert len(mouse.sent) == 2


def test_last_error_is_reported_when_every_round_fails():
    mouse = FakeMouse(interference=[synapse_reply(protocol.STATUS_OK)] * 3)
    with pytest.raises(protocol.ProtocolError, match="不匹配"):
        device.query(mouse, protocol.CMD_BATTERY, rounds=3, sleep=no_sleep)
    assert len(mouse.sent) == 3


def test_waits_before_each_poll():
    delays = []
    device.query(FakeMouse(busy_polls=1), protocol.CMD_BATTERY, delay=0.25, sleep=delays.append)
    assert delays == [0.25, 0.25]


def test_supported_models_use_razer_vendor_and_91_byte_feature_reports():
    assert device.VENDOR_ID == 0x1532
    assert device.FEATURE_LENGTH == 91
    assert device.MODELS[0x00B7] == "DeathAdder V3 Pro (wireless)"
