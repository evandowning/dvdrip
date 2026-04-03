"""Pydantic data models for DVD ripping."""

from pydantic import BaseModel, ConfigDict, Field


class Duration(BaseModel):
    """A time duration with hours, minutes, and seconds."""

    model_config = ConfigDict(frozen=True)

    hours: int
    minutes: int
    seconds: int

    def __str__(self) -> str:
        """Format as HH:MM:SS."""
        return f"{self.hours:02d}:{self.minutes:02d}:{self.seconds:02d}"

    def in_seconds(self) -> int:
        """Convert to total seconds."""
        return 60 * (60 * self.hours + self.minutes) + self.seconds


class Size(BaseModel):
    """Video frame dimensions and pixel aspect ratio."""

    model_config = ConfigDict(frozen=True)

    width: int
    height: int
    pix_aspect_width: int
    pix_aspect_height: int
    fps: float


class Chapter(BaseModel):
    """A DVD chapter with its number and duration."""

    model_config = ConfigDict(frozen=True)

    number: int
    duration: Duration


class AudioTrack(BaseModel):
    """An audio track on a DVD title."""

    model_config = ConfigDict(frozen=True)

    number: int
    lang: str
    codec: str
    channels: str
    iso639_2: str
    extras: str


class SubtitleTrack(BaseModel):
    """A subtitle track on a DVD title."""

    model_config = ConfigDict(frozen=True)

    number: int
    info: str


class TitleInfo(BaseModel):
    """Parsed information about a DVD title from HandBrakeCLI scan output."""

    model_config = ConfigDict(
        frozen=True,
        populate_by_name=True,
        extra="ignore",
    )

    duration: Duration
    size: str
    chapters: dict[str, str]
    audio_tracks: dict[str, str] = Field(validation_alias="audio tracks")
    subtitle_tracks: dict[str, str] = Field(validation_alias="subtitle tracks")


class Title(BaseModel):
    """A DVD title with its number and parsed info."""

    model_config = ConfigDict(frozen=True)

    number: int
    info: TitleInfo


class Task(BaseModel):
    """A ripping task: one title, optionally one chapter."""

    model_config = ConfigDict(frozen=True)

    title: Title
    chapter: int | None = None
