from __future__ import annotations

import dataclasses
import pathlib
from typing import List, Sequence

import yaml


@dataclasses.dataclass
class SamplingConfig:
    frame_hop_ms: int = 100
    window_seconds: float = 1.6
    block_samples: int = 128
    sample_rate: int = 860


@dataclasses.dataclass
class NetworkConfig:
    host: str = "10.0.0.1"
    port: int = 5005
    heartbeat_hz: float = 2.0


@dataclasses.dataclass
class NodeConfig:
    node_id: int
    fusion_host: str
    fusion_port: int
    array_mode: str = "triangle"  # "triangle" or "tetrahedron"
    
    # Global position of this node in surveillance area [x, y, z] in meters
    global_position: List[float] | None = None
    
    # Triangle array (3 mics)
    triangle_positions: Sequence[Sequence[float]] = dataclasses.field(default_factory=list)
    triangle_vectors: Sequence[Sequence[float]] = dataclasses.field(default_factory=list)
    
    # Tetrahedron array (4 mics)
    tetrahedron_positions: Sequence[Sequence[float]] = dataclasses.field(default_factory=list)
    tetrahedron_vectors: Sequence[Sequence[float]] = dataclasses.field(default_factory=list)
    
    pga_voltage: float = 1.024
    ads_address: str | int = "0x48"
    use_simulator: bool = False
    sampling: SamplingConfig = dataclasses.field(default_factory=SamplingConfig)
    network: NetworkConfig = dataclasses.field(default_factory=NetworkConfig)
    calibration_noise_rms: List[float] | None = None
    mic_bias_mv: List[float] | None = None

    @property
    def ads_address_int(self) -> int:
        return int(str(self.ads_address), 16) if isinstance(self.ads_address, str) else int(self.ads_address)

    @property
    def fusion_endpoint(self) -> tuple[str, int]:
        return (self.fusion_host, int(self.fusion_port))
    
    @property
    def num_channels(self) -> int:
        """Number of microphone channels based on array mode."""
        return 3 if self.array_mode == "triangle" else 4
    
    @property
    def mic_positions(self) -> Sequence[Sequence[float]]:
        """Current microphone positions based on array mode."""
        return self.triangle_positions if self.array_mode == "triangle" else self.tetrahedron_positions
    
    @property
    def mic_vectors(self) -> Sequence[Sequence[float]]:
        """Current directional vectors based on array mode."""
        return self.triangle_vectors if self.array_mode == "triangle" else self.tetrahedron_vectors


def _dataclass_from_dict(cls, data):
    fieldtypes = {f.name: f.type for f in dataclasses.fields(cls)}
    kwargs = {}
    for key, value in data.items():
        if dataclasses.is_dataclass(fieldtypes.get(key)):
            kwargs[key] = _dataclass_from_dict(fieldtypes[key], value)
        else:
            kwargs[key] = value
    return cls(**kwargs)


def load_config(path: str | pathlib.Path) -> NodeConfig:
    config_path = pathlib.Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if "sampling" in raw:
        raw["sampling"] = _dataclass_from_dict(SamplingConfig, raw["sampling"])
    if "network" in raw:
        raw["network"] = _dataclass_from_dict(NetworkConfig, raw["network"])
    return NodeConfig(**raw)


def dump_config(config: NodeConfig, path: str | pathlib.Path) -> None:
    def serialize(obj):
        if dataclasses.is_dataclass(obj):
            return {k: serialize(v) for k, v in dataclasses.asdict(obj).items()}
        return obj

    config_path = pathlib.Path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(serialize(config), handle, sort_keys=False)
