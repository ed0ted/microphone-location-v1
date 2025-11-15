from __future__ import annotations

import dataclasses
import pathlib
from typing import Dict, List

import yaml


@dataclasses.dataclass
class NodeGeometry:
    node_id: int
    position: List[float]


@dataclasses.dataclass
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 80


@dataclasses.dataclass
class FusionConfig:
    listen_host: str = "0.0.0.0"
    listen_port: int = 5005
    localization_rate_hz: float = 20.0
    grid_bounds: Dict[str, List[float]] = dataclasses.field(
        default_factory=lambda: {"x": [-5, 25], "y": [-5, 25], "z": [0, 25]}
    )
    grid_step: float = 1.0
    direction_weight: float = 0.3
    detection_floor: float = 0.05
    smoothing_alpha: float = 0.4
    smoothing_beta: float = 0.2
    nodes: List[NodeGeometry] = dataclasses.field(default_factory=list)
    web: WebConfig = dataclasses.field(default_factory=WebConfig)


def load_config(path: str | pathlib.Path) -> FusionConfig:
    config_path = pathlib.Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    nodes = [NodeGeometry(**node) for node in raw.get("nodes", [])]
    raw["nodes"] = nodes
    if "web" in raw:
        raw["web"] = WebConfig(**raw["web"])
    return FusionConfig(**raw)
