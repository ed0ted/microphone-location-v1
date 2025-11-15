from __future__ import annotations

import binascii
import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, List

import numpy as np


@dataclass
class Packet:
    node_id: int
    seq: int
    ts_us: int
    present: bool
    mic_rms: List[float]
    noise_rms: List[float]
    crest: List[float]
    bandpower: List[float]
    dir_local: List[float]
    dir_conf: float
    supply_v: float
    temp_c: float
    extra: Dict[str, Any] | None = None

    def to_payload(self) -> bytes:
        payload = asdict(self)
        if self.extra:
            payload.update(self.extra)
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        crc = f"{binascii.crc32(payload_bytes) & 0xFFFFFFFF:08x}"
        return payload_bytes + b"|" + crc.encode("ascii")

    @classmethod
    def from_frame(cls, node_id: int, seq: int, frame, supply_v: float, temp_c: float) -> "Packet":
        ts_us = int(frame.timestamp * 1_000_000)
        return cls(
            node_id=node_id,
            seq=seq,
            ts_us=ts_us,
            present=bool(frame.present),
            mic_rms=[float(x) for x in frame.mic_rms],
            noise_rms=[float(x) for x in frame.noise_rms],
            crest=[float(x) for x in frame.crest],
            bandpower=[float(x) for x in frame.bandpower],
            dir_local=[float(x) for x in frame.dir_local],
            dir_conf=float(frame.dir_conf),
            supply_v=float(supply_v),
            temp_c=float(temp_c),
            extra={"total_energy": float(frame.total_energy)},
        )
