"""The ``dvdrip`` APIs."""

import importlib.metadata

from dvdrip._dvd import DVD
from dvdrip._errors import UserError
from dvdrip._models import (
    AudioTrack,
    Chapter,
    Duration,
    Size,
    SubtitleTrack,
    Task,
    Title,
    TitleInfo,
)

__all__ = [
    "DVD",
    "AudioTrack",
    "Chapter",
    "Duration",
    "Size",
    "SubtitleTrack",
    "Task",
    "Title",
    "TitleInfo",
    "UserError",
]

__version__ = importlib.metadata.version("dvdrip")
