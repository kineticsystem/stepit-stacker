"""The settings of the pipeline, from config/pipeline.toml, and the files of config/."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "config"


@dataclass(frozen=True)
class Quilt:
    columns: int
    rows: int
    view_width: int
    view_height: int
    reverse: bool

    @property
    def views(self):
        return self.columns * self.rows

    @property
    def aspect(self):
        return self.view_width / self.view_height


@dataclass(frozen=True)
class Config:
    rig_host: str
    rig_user: str
    rig_port: int
    rig_pictures: str
    mirror: Path
    rotate: int
    quilt: Quilt
    develop_xmp: Path = CONFIG / "develop.xmp"
    grade_xmp: Path = CONFIG / "grade.xmp"


def load(path=CONFIG / "pipeline.toml"):
    with open(path, "rb") as file:
        settings = tomllib.load(file)
    mirror = Path(settings["pictures"]["mirror"]).expanduser()
    return Config(
        rig_host=settings["rig"]["host"],
        rig_user=settings["rig"]["user"],
        rig_port=settings["rig"]["port"],
        rig_pictures=settings["rig"]["pictures"],
        mirror=mirror if mirror.is_absolute() else REPO / mirror,
        rotate=settings["images"]["rotate"],
        quilt=Quilt(**settings["quilt"]),
    )
