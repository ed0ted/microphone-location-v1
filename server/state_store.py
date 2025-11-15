from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Frame:
    node_id: int
    seq: int
    timestamp: float
    present: bool
    mic_rms: List[float]
    noise_rms: List[float]
    crest: List[float]
    bandpower: List[float]
    dir_local: List[float]
    dir_conf: float
    total_energy: float
    extra: dict


@dataclass
class NodeState:
    last_frame: Optional[Frame] = None
    last_seen: float = field(default_factory=time.time)
    online: bool = False


@dataclass
class FusionState:
    timestamp: float = field(default_factory=time.time)
    present: bool = False
    position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    velocity: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    confidence: float = 0.0
    error: float = 0.0
    node_details: List[dict] = field(default_factory=list)


class FrameStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._nodes: Dict[int, NodeState] = {}
        self._fusion_state = FusionState()

    def update_frame(self, frame: Frame) -> None:
        with self._lock:
            node_state = self._nodes.setdefault(frame.node_id, NodeState())
            node_state.last_frame = frame
            node_state.last_seen = time.time()
            node_state.online = True

    def get_frames(self) -> Dict[int, Frame]:
        with self._lock:
            return {node_id: state.last_frame for node_id, state in self._nodes.items() if state.last_frame}

    def mark_offline(self, timeout: float = 2.0) -> None:
        now = time.time()
        with self._lock:
            for state in self._nodes.values():
                if now - state.last_seen > timeout:
                    state.online = False

    def get_node_health(self) -> Dict[int, dict]:
        with self._lock:
            return {
                node_id: {
                    "online": state.online,
                    "last_seen": state.last_seen,
                    "present": bool(state.last_frame and state.last_frame.present),
                }
                for node_id, state in self._nodes.items()
            }

    def update_fusion_state(self, fusion: FusionState) -> None:
        with self._lock:
            self._fusion_state = fusion

    def get_fusion_state(self) -> FusionState:
        with self._lock:
            return self._fusion_state
