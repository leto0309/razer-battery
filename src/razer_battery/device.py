"""Query a Razer mouse over any transport that can send and receive 90-byte feature reports."""

import time
from dataclasses import dataclass
from typing import Callable, Protocol

from . import protocol

VENDOR_ID = 0x1532
# Report ID 0 plus the 90-byte Razer report.
FEATURE_LENGTH = protocol.REPORT_LENGTH + 1
MODELS = {
    0x00B7: "DeathAdder V3 Pro (wireless)",
    0x00B6: "DeathAdder V3 Pro (wired)",
}

ATTEMPTS = 10
ROUNDS = 3
DELAY_S = 0.05


class Transport(Protocol):
    def send(self, report: bytes) -> None: ...
    def receive(self) -> bytes: ...


@dataclass(frozen=True)
class Reading:
    model: str
    percent: int
    charging: bool


class DeviceNotFound(Exception):
    pass


def _poll(transport: Transport, command: tuple[int, int], attempts: int, delay: float,
          sleep: Callable[[float], None]) -> bytes:
    for _ in range(attempts):
        sleep(delay)
        try:
            return protocol.parse_reply(transport.receive(), *command)
        except protocol.BusyError:
            continue
    raise protocol.ProtocolError("设备持续忙，读取超时")


def query(transport: Transport, command: tuple[int, int], attempts: int = ATTEMPTS,
          rounds: int = ROUNDS, delay: float = DELAY_S,
          sleep: Callable[[float], None] = time.sleep) -> bytes:
    request = protocol.build_request(*command)
    error = protocol.ProtocolError("未发送请求")
    for _ in range(rounds):
        # When Razer Synapse sends its own command between our send and receive (measured at
        # about 1 in 100 reads), we get its reply or a failure; sending ours again fixes that.
        transport.send(request)
        try:
            return _poll(transport, command, attempts, delay, sleep)
        except protocol.ProtocolError as caught:
            error = caught
    raise error


def read_battery(transport: Transport, model: str, **query_options) -> Reading:
    battery = query(transport, protocol.CMD_BATTERY, **query_options)
    charging = query(transport, protocol.CMD_CHARGING, **query_options)
    return Reading(model, protocol.raw_to_percent(battery[1]), charging[1] != 0)


def read_connected_mouse() -> Reading:
    """Read the first supported mouse that answers; Windows only."""
    from . import hid_win

    last_error: Exception | None = None
    for interface in hid_win.list_interfaces(VENDOR_ID):
        model = MODELS.get(interface.product_id)
        if model is None or interface.feature_length != FEATURE_LENGTH:
            continue
        try:
            with hid_win.FeatureTransport(interface.path, FEATURE_LENGTH) as transport:
                return read_battery(transport, model)
        except (protocol.ProtocolError, OSError) as error:
            # With both the receiver and the cable plugged in, the other interface may still answer.
            last_error = error
    if last_error is not None:
        raise last_error
    raise DeviceNotFound("未找到 Razer DeathAdder V3 Pro（检查接收器是否插好）")
