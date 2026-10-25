import pytest

from razer_battery import protocol


def reply_for(request: bytes, status: int = protocol.STATUS_OK, value: int = 0) -> bytes:
    reply = bytearray(request)
    reply[0] = status
    reply[protocol.ARGS_OFFSET + 1] = value
    return bytes(reply)


def test_battery_request_matches_bytes_sent_to_real_mouse():
    request = protocol.build_request(*protocol.CMD_BATTERY)
    assert len(request) == 90
    assert request[:8] == bytes([0x00, 0x1F, 0x00, 0x00, 0x00, 0x02, 0x07, 0x80])
    assert request[88] == 0x02 ^ 0x07 ^ 0x80
    assert request[89] == 0


def test_checksum_covers_arguments_but_not_status_or_transaction_id():
    request = protocol.build_request(0x07, 0x80, args=b"\x01\x10")
    assert request[88] == 0x02 ^ 0x07 ^ 0x80 ^ 0x01 ^ 0x10
    changed = bytearray(request)
    changed[0], changed[1] = 0xAA, 0xBB
    assert protocol.checksum(changed) == request[88]


def test_rejects_too_long_arguments():
    with pytest.raises(ValueError):
        protocol.build_request(0x07, 0x80, args=bytes(81))


def test_parse_reply_returns_arguments():
    request = protocol.build_request(*protocol.CMD_BATTERY)
    args = protocol.parse_reply(reply_for(request, value=0xAB), *protocol.CMD_BATTERY)
    assert len(args) == 80
    assert args[1] == 0xAB


def test_busy_reply_raises_busy_error():
    request = protocol.build_request(*protocol.CMD_BATTERY)
    with pytest.raises(protocol.BusyError):
        protocol.parse_reply(reply_for(request, status=protocol.STATUS_BUSY), *protocol.CMD_BATTERY)


@pytest.mark.parametrize("status, text", [
    (protocol.STATUS_TIMEOUT, "休眠"),
    (protocol.STATUS_FAILURE, "失败"),
    (protocol.STATUS_UNSUPPORTED, "不支持"),
    (0x09, "0x09"),
])
def test_error_statuses_are_reported(status, text):
    request = protocol.build_request(*protocol.CMD_BATTERY)
    with pytest.raises(protocol.ProtocolError, match=text) as caught:
        protocol.parse_reply(reply_for(request, status=status), *protocol.CMD_BATTERY)
    assert not isinstance(caught.value, protocol.BusyError)


@pytest.mark.parametrize("offset, value", [(1, 0x3F), (6, 0x0F), (7, 0x84)])
def test_reply_to_another_request_is_rejected(offset, value):
    reply = bytearray(reply_for(protocol.build_request(*protocol.CMD_BATTERY), value=0xAB))
    reply[offset] = value
    with pytest.raises(protocol.ProtocolError, match="不匹配"):
        protocol.parse_reply(bytes(reply), *protocol.CMD_BATTERY)


def test_another_programs_failure_is_a_mismatch_not_our_failure():
    reply = bytearray(protocol.build_request(0x0F, 0x03, data_size=8, transaction_id=0x10))
    reply[0] = protocol.STATUS_FAILURE
    with pytest.raises(protocol.ProtocolError, match="不匹配"):
        protocol.parse_reply(bytes(reply), *protocol.CMD_BATTERY)


def test_short_reply_is_rejected():
    with pytest.raises(protocol.ProtocolError, match="长度"):
        protocol.parse_reply(bytes(10), *protocol.CMD_BATTERY)


@pytest.mark.parametrize("raw, percent", [(0, 0), (255, 100), (0xAB, 67), (51, 20), (1, 0), (254, 100)])
def test_raw_to_percent(raw, percent):
    assert protocol.raw_to_percent(raw) == percent


@pytest.mark.parametrize("raw", [-1, 256])
def test_raw_to_percent_rejects_out_of_range(raw):
    with pytest.raises(ValueError):
        protocol.raw_to_percent(raw)
