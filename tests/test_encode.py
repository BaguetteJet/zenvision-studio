import pytest
from PIL import Image

from zvstudio.core.device.zenvision import FRAME_BYTES, build_command, encode


def _is(data: bytes, *head: int) -> bool:
    """True if ``data`` starts with exactly the given command bytes."""
    return len(data) >= len(head) and list(data[: len(head)]) == list(head)


def test_encode_size():
    img = Image.new("L", (256, 64), 200)
    fb = encode(img)
    assert len(fb) == FRAME_BYTES == 8704


def test_packet_headers():
    fb = encode(Image.new("L", (256, 64), 255))
    headers = [fb[i * 512] for i in range(17)]
    assert headers == list(range(17))


def test_resizes_any_input():
    fb = encode(Image.new("L", (100, 40), 128))
    assert len(fb) == 8704


def test_builtin_commands():
    assert _is(build_command("clock", 1), 0x30, 0x05, 0x01, 0x01)
    assert _is(build_command("clock", 2), 0x30, 0x05, 0x01, 0x02)
    assert _is(build_command("theme", 4), 0x30, 0x05, 0x02, 0x00, 0x04)
    assert _is(build_command("battery", False), 0x30, 0x05, 0x04, 0, 0, 0, 0x01)
    assert _is(build_command("battery", True), 0x30, 0x05, 0x04, 0, 0, 0, 0x03)
    assert _is(build_command("sweep", False), 0x31, 0x02, 0x00, 0x04)
    assert _is(build_command("sweep", True), 0x31, 0x02, 0x02, 0x03)
    assert _is(build_command("bootanim", False), 0x32, 0x02, 0x00, 0x00)
    assert _is(build_command("bootanim", True), 0x32, 0x02, 0x02, 0x02)
    assert _is(build_command("speed", 3), 0x33, 0x01, 0x03)
    assert _is(build_command("brightness", 0x4F), 0x35, 0x01, 0x4F)
    assert _is(build_command("status"), 0xF1, 0x03)


def test_clocktime_command():
    cmd = build_command("clocktime", {
        "year": 2026, "month": 9, "day": 15, "hour": 14, "minute": 30,
        "second": 0, "format": 1, "weekday": 2,
    })
    assert _is(cmd, 0x40, 0x09, 0xEA, 0x07, 9, 15, 14, 30, 0, 1, 2)


def test_command_range_checks():
    for name, value in (("clock", 0), ("clock", 3), ("theme", 0), ("theme", 5),
                        ("speed", 0), ("speed", 4), ("brightness", 256), ("nope", 1)):
        with pytest.raises(ValueError):
            build_command(name, value)
