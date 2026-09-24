import pytest
from PIL import Image

from zvstudio.core.applets.base import Ctx
from zvstudio.core.registry import all_applets

SIZE = (256, 64)


@pytest.mark.parametrize("key", list(all_applets().keys()))
def test_applet_renders_panel_sized_grayscale(key):
    klass = all_applets()[key]
    applet = klass(size=SIZE)
    img = applet.render(Ctx(t=0.0, frame=0, size=SIZE))
    assert isinstance(img, Image.Image)
    assert img.size == SIZE
    assert img.mode == "L"


def test_player_no_media_placeholder():
    from zvstudio.core.applets.player import PlayerApplet

    p = PlayerApplet(size=SIZE, config={"path": "/does/not/exist.gif"})
    img = p.render(Ctx(t=0.0, frame=0, size=SIZE))
    assert img.size == SIZE


def test_frames_applet_advances_by_its_own_fps():
    from zvstudio.core.applets.frames import FramesApplet

    a = Image.new("L", SIZE, 0)
    b = Image.new("L", SIZE, 255)
    fa = FramesApplet(size=SIZE, frames=[a, b], config={"fps": 10})
    # index = int(t * fps) % n  ->  0.00s -> frame 0, 0.10s -> frame 1, 0.20s -> wraps to 0
    assert fa.render(Ctx(t=0.00, frame=0, size=SIZE)).getpixel((0, 0)) == 0
    assert fa.render(Ctx(t=0.10, frame=0, size=SIZE)).getpixel((0, 0)) == 255
    assert fa.render(Ctx(t=0.20, frame=0, size=SIZE)).getpixel((0, 0)) == 0


def test_frames_applet_empty_is_blank():
    from zvstudio.core.applets.frames import FramesApplet

    fa = FramesApplet(size=SIZE, frames=[])
    img = fa.render(Ctx(t=1.23, frame=5, size=SIZE))
    assert img.size == SIZE and img.mode == "L"


def test_nowplaying_layout_with_art():
    from zvstudio.core.applets.nowplaying import NowPlayingApplet

    ap = NowPlayingApplet(size=SIZE)
    ap._title = None
    ap._strip = None
    with ap._art_lock:
        ap._art = Image.new("L", (48, 48), 200)
        ap._art_url = "x"
    ap._watcher.state = {"playing": True, "title": "Test Song", "artist": "An Artist",
                         "pos": 0.0, "length": 100.0, "changed_at": 0.0, "art_url": "x"}
    img = ap.render(Ctx(t=0.0, frame=0, size=SIZE))
    assert img.getpixel((25, 32)) == 200        # art square present
    assert img.getpixel((64, 12)) > 0           # title sits high, next to the art
    assert img.getpixel((64, 44)) > 0           # artist below the title, no overlap band


def test_player_advances_by_its_own_fps():
    from zvstudio.core.applets.player import PlayerApplet

    a = Image.new("L", SIZE, 0)
    b = Image.new("L", SIZE, 255)
    p = PlayerApplet(size=SIZE, config={"path": "x", "fps": 10})
    p._loaded = "x"
    p._frames = [a, b]
    # index = int(t * fps) % n, decoupled from the tick rate (ctx.frame)
    assert p.render(Ctx(t=0.00, frame=99, size=SIZE)).getpixel((0, 0)) == 0
    assert p.render(Ctx(t=0.10, frame=99, size=SIZE)).getpixel((0, 0)) == 255
    assert p.render(Ctx(t=0.20, frame=99, size=SIZE)).getpixel((0, 0)) == 0
