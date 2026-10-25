"""Razer HID feature-report protocol: build requests and parse replies, with no I/O.

Report layout (90 bytes): status, transaction id, remaining packets (2, big endian),
protocol type, data size, command class, command id, 80 argument bytes,
checksum (XOR of bytes 2..87), reserved.
"""

REPORT_LENGTH = 90
ARGS_OFFSET = 8
ARGS_LENGTH = 80
CHECKSUM_OFFSET = 88

# Verified on a DeathAdder V3 Pro 2.4G receiver; 0xFF makes it answer with a timeout status.
TRANSACTION_ID = 0x1F

STATUS_NEW = 0x00
STATUS_BUSY = 0x01
STATUS_OK = 0x02
STATUS_FAILURE = 0x03
STATUS_TIMEOUT = 0x04
STATUS_UNSUPPORTED = 0x05

CMD_BATTERY = (0x07, 0x80)
CMD_CHARGING = (0x07, 0x84)

_STATUS_MESSAGES = {
    STATUS_FAILURE: "设备返回失败",
    STATUS_TIMEOUT: "鼠标未响应（可能已休眠或关机，动一下鼠标再试）",
    STATUS_UNSUPPORTED: "设备不支持该命令",
}


class ProtocolError(Exception):
    """The device answered, but not with a usable reply."""


class BusyError(ProtocolError):
    """The device has not finished the command yet; ask again."""


def checksum(report: bytes) -> int:
    value = 0
    for byte in report[2:CHECKSUM_OFFSET]:
        value ^= byte
    return value


def build_request(command_class: int, command_id: int, data_size: int = 2,
                  args: bytes = b"", transaction_id: int = TRANSACTION_ID) -> bytes:
    if len(args) > ARGS_LENGTH:
        raise ValueError("arguments longer than 80 bytes")
    report = bytearray(REPORT_LENGTH)
    report[0] = STATUS_NEW
    report[1] = transaction_id
    report[5] = data_size
    report[6] = command_class
    report[7] = command_id
    report[ARGS_OFFSET:ARGS_OFFSET + len(args)] = args
    report[CHECKSUM_OFFSET] = checksum(report)
    return bytes(report)


def parse_reply(reply: bytes, command_class: int, command_id: int,
                transaction_id: int = TRANSACTION_ID) -> bytes:
    """Return the 80 argument bytes of a successful reply to the given command."""
    if len(reply) != REPORT_LENGTH:
        raise ProtocolError(f"回复长度异常：{len(reply)} 字节")
    # Razer Synapse talks to the same device; its replies (and their statuses) are not ours to read.
    if (reply[1], reply[6], reply[7]) != (transaction_id, command_class, command_id):
        raise ProtocolError("回复与请求不匹配")
    status = reply[0]
    if status == STATUS_BUSY:
        raise BusyError("设备忙")
    if status != STATUS_OK:
        raise ProtocolError(_STATUS_MESSAGES.get(status, f"未知回复状态 0x{status:02X}"))
    return bytes(reply[ARGS_OFFSET:ARGS_OFFSET + ARGS_LENGTH])


def raw_to_percent(raw: int) -> int:
    if not 0 <= raw <= 255:
        raise ValueError("raw battery value must be 0..255")
    return round(raw * 100 / 255)
