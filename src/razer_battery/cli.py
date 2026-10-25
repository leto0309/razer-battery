"""Command line entry point."""

import argparse
import json
import sys
from typing import Callable

from . import protocol
from .device import DeviceNotFound, Reading
from .display import describe

EXIT_OK = 0
EXIT_UNSUPPORTED = 1
EXIT_NOT_FOUND = 2
EXIT_READ_FAILED = 3


def self_test() -> bool:
    """Check the protocol code against a known reply; touches no hardware."""
    request = protocol.build_request(*protocol.CMD_BATTERY)
    reply = bytearray(request)
    reply[0] = protocol.STATUS_OK
    reply[protocol.ARGS_OFFSET + 1] = 0xAB  # 67%, as read from a real DeathAdder V3 Pro
    args = protocol.parse_reply(bytes(reply), *protocol.CMD_BATTERY)
    return request[protocol.CHECKSUM_OFFSET] == 0x85 and protocol.raw_to_percent(args[1]) == 67


def main(argv: list[str] | None = None, read: Callable[[], Reading] | None = None,
         platform: str = sys.platform) -> int:
    parser = argparse.ArgumentParser(prog="razer-battery", description="读取 Razer DeathAdder V3 Pro 电量")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--json", action="store_true", help="以 JSON 输出")
    mode.add_argument("--tray", action="store_true", help="在系统托盘显示电量")
    mode.add_argument("--self-test", action="store_true", help="不访问硬件的自检")
    parser.add_argument("--interval", type=int, default=60, metavar="秒", help="托盘刷新间隔，默认 60")
    args = parser.parse_args(argv)

    if args.self_test:
        ok = self_test()
        print("self-test ok" if ok else "self-test FAILED")
        return EXIT_OK if ok else EXIT_READ_FAILED
    if args.interval < 5:
        parser.error("--interval 至少 5 秒")
    if platform != "win32" and read is None:
        print("仅支持 Windows", file=sys.stderr)
        return EXIT_UNSUPPORTED
    if args.tray:
        from .tray import run
        return run(args.interval)

    if read is None:
        from .device import read_connected_mouse as read
    try:
        reading = read()
    except DeviceNotFound as error:
        print(error, file=sys.stderr)
        return EXIT_NOT_FOUND
    except (protocol.ProtocolError, OSError) as error:
        print(f"读取失败：{error}", file=sys.stderr)
        return EXIT_READ_FAILED
    if args.json:
        print(json.dumps({"model": reading.model, "percent": reading.percent, "charging": reading.charging}))
    else:
        print(describe(reading))
    return EXIT_OK
