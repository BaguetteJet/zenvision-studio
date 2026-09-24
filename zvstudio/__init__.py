"""zenvision-studio — drive small lid OLED panels (ASUS ZenVision and friends)
with live applets and custom animations."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("zenvision-studio")
except PackageNotFoundError:  # source checkout, not installed
    __version__ = "0.0.0"
