from __future__ import annotations

import dataclasses
import logging
import time
from collections import deque
from typing import Deque, Dict, Iterable, List

import numpy as np

LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class FrameResult:
    timestamp: float
    mic_rms: np.ndarray
    crest: np.ndarray
    bandpower: np.ndarray
    total_energy: float
    present: bool
    dir_local: np.ndarray
    dir_conf: float
    noise_rms: np.ndarray


class RingBuffer:
    def __init__(self, channels: int, size: int):
        self.channels = channels
        self.buffer = np.zeros((channels, size), dtype=np.float32)
        self.size = size
        self.pos = 0
        self.filled = False

    def append(self, samples: np.ndarray) -> None:
        n = samples.shape[1]
        if n >= self.size:
            self.buffer[:] = samples[:, -self.size :]
            self.pos = 0
            self.filled = True
            return
        end = self.pos + n
        if end < self.size:
            self.buffer[:, self.pos : end] = samples
        else:
            first = self.size - self.pos
            self.buffer[:, self.pos :] = samples[:, :first]
            self.buffer[:, : n - first] = samples[:, first:]
        self.pos = (self.pos + n) % self.size
        if n:
            self.filled = True

    def view(self) -> np.ndarray:
        if not self.filled:
            return self.buffer[:, : self.pos]
        idx = np.arange(self.size)
        idx = (idx + self.pos) % self.size
        return self.buffer[:, idx]


class NoiseTracker:
    def __init__(self, channels: int, init: Iterable[float] | None = None, alpha: float = 0.01):
        init_array = np.asarray(list(init), dtype=np.float32) if init is not None else np.ones(channels, dtype=np.float32) * 0.05
        self.level = init_array
        self.alpha = alpha

    def update(self, rms: np.ndarray, present: bool) -> None:
        if not present:
            self.level = (1 - self.alpha) * self.level + self.alpha * rms


class DirectionEstimator:
    def __init__(self, vectors: Iterable[Iterable[float]]):
        arr = np.asarray(list(vectors), dtype=np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.vecs = arr / norms

    def estimate(self, weights: np.ndarray) -> tuple[np.ndarray, float]:
        weights = np.maximum(weights, 0.0)
        if np.all(weights == 0):
            return np.zeros(3, dtype=np.float32), 0.0
        direction = (weights[:, None] * self.vecs).sum(axis=0)
        norm = np.linalg.norm(direction)
        if norm == 0:
            return np.zeros(3, dtype=np.float32), 0.0
        return direction / norm, min(float(np.sum(weights)), 1.0)


def goertzel(samples: np.ndarray, target_freq: float, sample_rate: float) -> float:
    k = int(0.5 + (samples.shape[0] * target_freq) / sample_rate)
    omega = (2.0 * np.pi * k) / samples.shape[0]
    sine = np.sin(omega)
    cosine = np.cos(omega)
    coeff = 2 * cosine
    q0 = q1 = q2 = 0.0
    for sample in samples:
        q0 = coeff * q1 - q2 + sample
        q2 = q1
        q1 = q0
    real = q1 - q2 * cosine
    imag = q2 * sine
    magnitude = np.sqrt(real * real + imag * imag)
    return float(magnitude / samples.shape[0])


class FeatureExtractor:
    def __init__(
        self,
        sample_rate: int,
        frame_hop: int,
        window_seconds: float,
        mic_vectors: Iterable[Iterable[float]],
        num_channels: int = 3,
        noise_init: Iterable[float] | None = None,
    ):
        self.sample_rate = sample_rate
        self.frame_hop = frame_hop
        self.num_channels = num_channels
        self.window_samples = max(int(window_seconds * sample_rate), frame_hop)
        self.buffer = RingBuffer(num_channels, self.window_samples)
        self.pending = 0
        self.dir_estimator = DirectionEstimator(mic_vectors)
        self.noise_tracker = NoiseTracker(num_channels, noise_init)
        self.last_present = False
        self._last_emit = time.monotonic()

    def push(self, samples: np.ndarray) -> List[FrameResult]:
        self.buffer.append(samples)
        self.pending += samples.shape[1]
        frames: List[FrameResult] = []
        while self.pending >= self.frame_hop:
            frames.append(self._emit_frame())
            self.pending -= self.frame_hop
        return frames

    def _emit_frame(self) -> FrameResult:
        window = self.buffer.view()
        if window.size == 0:
            raise RuntimeError("Insufficient samples for frame computation")
        rms = np.sqrt(np.mean(window**2, axis=1))
        peak = np.max(np.abs(window), axis=1)
        crest = np.divide(peak, rms + 1e-6)
        band_120 = goertzel(window[0], 120.0, self.sample_rate)
        band_240 = goertzel(window[0], 240.0, self.sample_rate)
        total_energy = float(np.sum(rms))
        noise = self.noise_tracker.level
        signal = np.maximum(rms - noise, 0.0)
        noise_sum = float(np.sum(noise) + 1e-6)
        hi = noise_sum * 3.5
        lo = noise_sum * 3.0
        present = bool(total_energy > hi or (self.last_present and total_energy > lo))
        self.noise_tracker.update(rms, present)
        dir_vec, dir_conf = self.dir_estimator.estimate(signal)
        frame = FrameResult(
            timestamp=time.time(),
            mic_rms=rms,
            crest=crest,
            bandpower=np.array([band_120, band_240], dtype=np.float32),
            total_energy=total_energy,
            present=present,
            dir_local=dir_vec,
            dir_conf=dir_conf,
            noise_rms=self.noise_tracker.level.copy(),
        )
        self.last_present = present
        self._last_emit = time.monotonic()
        return frame
