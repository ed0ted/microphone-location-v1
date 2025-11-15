from __future__ import annotations

import logging
import math
import threading
import time
from typing import Dict, Iterable, List

import numpy as np

from .config import FusionConfig, NodeGeometry
from .state_store import Frame, FrameStore, FusionState

LOGGER = logging.getLogger("localization")


def _distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b) + 1e-6)


def _grid_points(bounds: Dict[str, List[float]], step: float) -> Iterable[np.ndarray]:
    xs = np.arange(bounds["x"][0], bounds["x"][1] + step, step)
    ys = np.arange(bounds["y"][0], bounds["y"][1] + step, step)
    zs = np.arange(bounds["z"][0], bounds["z"][1] + step, step)
    for x in xs:
        for y in ys:
            for z in zs:
                yield np.array([x, y, z], dtype=np.float32)


def normalize_energies(energies: Dict[int, float]) -> Dict[int, float]:
    total = sum(energies.values()) + 1e-6
    return {node_id: val / total for node_id, val in energies.items()}


class LocalizationEngine:
    def __init__(self, config: FusionConfig, store: FrameStore):
        self.config = config
        self.store = store
        self.node_positions = {geom.node_id: np.array(geom.position, dtype=np.float32) for geom in config.nodes}
        self.velocity = np.zeros(3, dtype=np.float32)
        self.last_position = np.zeros(3, dtype=np.float32)
        self._stop = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        period = 1.0 / self.config.localization_rate_hz
        next_time = time.time()
        while not self._stop.is_set():
            start = time.time()
            frames = self.store.get_frames()
            fusion_state = self._localize(frames)
            if fusion_state:
                self.store.update_fusion_state(fusion_state)
            next_time += period
            sleep = max(0.0, next_time - time.time())
            time.sleep(sleep)

    def _localize(self, frames: Dict[int, Frame]) -> FusionState | None:
        if len(frames) < 2:
            return None
        energies = {node_id: float(frame.total_energy) for node_id, frame in frames.items()}
        normalized = normalize_energies(energies)
        present_nodes = [node_id for node_id, frame in frames.items() if frame.present]
        if not present_nodes:
            state = self.store.get_fusion_state()
            state.present = False
            state.confidence = 0.0
            return state
        best_point, best_err = self._grid_search(frames, normalized)
        refined = self._refine(best_point, frames, normalized)
        now = time.time()
        dt = max(now - self.store.get_fusion_state().timestamp, 1e-3)
        velocity = (refined - self.last_position) / dt
        position = self.config.smoothing_alpha * refined + (1 - self.config.smoothing_alpha) * self.last_position
        velocity = self.config.smoothing_beta * velocity + (1 - self.config.smoothing_beta) * self.velocity
        self.last_position = position
        self.velocity = velocity
        node_details = [
            {
                "id": node_id,
                "energy": normalized[node_id],
                "dir": frames[node_id].dir_local,
                "online": True,
            }
            for node_id in frames
        ]
        fusion_state = FusionState(
            timestamp=now,
            present=True,
            position=position.tolist(),
            velocity=velocity.tolist(),
            confidence=max(0.0, 1.0 - best_err),
            error=float(best_err),
            node_details=node_details,
        )
        return fusion_state

    def _grid_search(self, frames: Dict[int, Frame], normalized: Dict[int, float]) -> tuple[np.ndarray, float]:
        best_point = None
        best_err = math.inf
        for point in _grid_points(self.config.grid_bounds, self.config.grid_step):
            err = self._point_error(point, frames, normalized)
            if err < best_err:
                best_err = err
                best_point = point
        if best_point is None:
            best_point = np.zeros(3, dtype=np.float32)
        return best_point, best_err

    def _point_error(self, point: np.ndarray, frames: Dict[int, Frame], normalized: Dict[int, float]) -> float:
        predictions = {}
        for node_id, frame in frames.items():
            node_pos = self.node_positions.get(node_id)
            if node_pos is None:
                continue
            dist = _distance(point, node_pos)
            predictions[node_id] = 1.0 / (dist * dist)
        predictions = normalize_energies(predictions)
        err = sum((predictions.get(node_id, 0) - normalized.get(node_id, 0)) ** 2 for node_id in frames)
        for node_id, frame in frames.items():
            node_pos = self.node_positions.get(node_id)
            if node_pos is None:
                continue
            direction = np.array(frame.dir_local, dtype=np.float32)
            if np.linalg.norm(direction) == 0:
                continue
            target = point - node_pos
            target_norm = np.linalg.norm(target) + 1e-6
            dot = np.dot(direction, target / target_norm)
            err += self.config.direction_weight * (1.0 - dot)
        return float(err)

    def _refine(self, start: np.ndarray, frames: Dict[int, Frame], normalized: Dict[int, float]) -> np.ndarray:
        point = start.copy()
        step = self.config.grid_step * 0.5
        for _ in range(10):
            improved = False
            for axis in range(3):
                for delta in (-step, step):
                    candidate = point.copy()
                    candidate[axis] += delta
                    err_candidate = self._point_error(candidate, frames, normalized)
                    err_current = self._point_error(point, frames, normalized)
                    if err_candidate < err_current:
                        point = candidate
                        improved = True
            if not improved:
                step *= 0.5
                if step < 0.25:
                    break
        return point
