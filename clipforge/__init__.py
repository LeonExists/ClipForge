"""ClipForge — YouTube clip definitions -> captioned vertical short-form videos.

The `clipforge` package is a FastAPI-independent, importable pipeline core with a
thin CLI wrapper. The same engine runs headless (CLI) and behind the web server.
"""

from clipforge.config import Config
from clipforge.models import Clip, ClipResult, ProgressEvent, Stage

__all__ = ["Config", "Clip", "ClipResult", "ProgressEvent", "Stage"]
__version__ = "0.1.0"
