from __future__ import annotations

import logging
import math
import threading
import time
from abc import ABC, abstractmethod
from typing import Iterable

import numpy as np

from .config import NodeConfig

LOGGER = logging.getLogger(__name__)


class BaseSampler(ABC):
    def __init__(self, sample_rate: int, channels: int = 3):
        self.sample_rate = sample_rate
        self.channels = channels

    @abstractmethod
    def read_block(self, samples: int) -> np.ndarray:
        """Return block of shape (channels, samples) in volts."""


class SimulatedSampler(BaseSampler):
    """Generates plausible microphone levels for bench testing."""

    def __init__(self, sample_rate: int, channels: int = 3, noise_level: float = 0.02):
        super().__init__(sample_rate, channels)
        self._noise = noise_level
        self._phase = np.zeros(self.channels)
        self._rng = np.random.default_rng()

    def read_block(self, samples: int) -> np.ndarray:
        t = np.arange(samples) / float(self.sample_rate)
        block = []
        base_freqs = np.array([110, 155, 210, 180], dtype=float)
        for idx in range(self.channels):
            freq = base_freqs[idx % len(base_freqs)] * (1.0 + 0.05 * math.sin(time.time() * 0.1 + idx))
            self._phase[idx] = (self._phase[idx] + freq * samples / self.sample_rate) % (2 * math.pi)
            signal = 0.1 * np.sin(2 * math.pi * freq * t + self._phase[idx])
            noise = self._rng.normal(0, self._noise, size=samples)
            block.append(signal + noise)
        return np.asarray(block, dtype=np.float32)


class HardwareSampler(BaseSampler):
    """ADS1115-based sampler. Falls back to per-channel polling."""

    def __init__(self, config: NodeConfig):
        super().__init__(config.sampling.sample_rate, config.num_channels)
        try:
            import board  # type: ignore
            import busio  # type: ignore
            from adafruit_ads1x15.analog_in import AnalogIn  # type: ignore
            from adafruit_ads1x15.ads1115 import ADS1115, Mode, Rate, PGA  # type: ignore
        except Exception as exc:  # pragma: no cover - hardware only
            raise RuntimeError("Hardware ADS1115 libraries not available") from exc

        self._board = board
        self._busio = busio
        self._AnalogIn = AnalogIn
        self._ADS1115 = ADS1115
        self._Mode = Mode
        self._Rate = Rate
        self._PGA = PGA
        self._config = config
        self._init_device()

    def _init_device(self):
        i2c = self._busio.I2C(self._board.SCL, self._board.SDA)
        self._ads = self._ADS1115(i2c, address=self._config.ads_address_int)
        self._ads.mode = self._Mode.CONTINUOUS
        self._ads.data_rate = self._Rate.RATE_860
        try:
            self._ads.gain = self._PGA[self._config.pga_voltage]  # type: ignore[index]
        except Exception:
            self._ads.gain = self._PGA["1.024"]  # type: ignore[index]
        # Initialize only the number of channels needed (3 for triangle, 4 for tetrahedron)
        self._channels = [self._AnalogIn(self._ads, getattr(self._ADS1115, f"P{i}")) for i in range(self.channels)]

    def read_block(self, samples: int) -> np.ndarray:  # pragma: no cover - hardware only
        block = np.zeros((self.channels, samples), dtype=np.float32)
        for idx, channel in enumerate(self._channels):
            volts = [channel.voltage for _ in range(samples)]
            block[idx] = np.asarray(volts, dtype=np.float32)
        return block


class AdcSampler:
    """High-level sampler that hides hardware/simulated implementations."""

    def __init__(self, config: NodeConfig):
        self.config = config
        self.sample_rate = config.sampling.sample_rate
        self._impl: BaseSampler
        if not config.use_simulator:
            try:
                self._impl = HardwareSampler(config)
                LOGGER.info(
                    "Initialized ADS1115 sampler on address %s with %d channels",
                    hex(config.ads_address_int),
                    config.num_channels,
                )
                return
            except Exception as exc:
                LOGGER.warning("Hardware sampler unavailable, falling back to simulator: %s", exc)
        self._impl = SimulatedSampler(config.sampling.sample_rate, config.num_channels)
        LOGGER.info("Using simulated sampler with %d channels", config.num_channels)

    def read_block(self, samples: int) -> np.ndarray:
        return self._impl.read_block(samples)


class ContinuousSampler:
    """Threaded sampler that paces reads to match requested cadence."""

    def __init__(self, sampler: AdcSampler, block_samples: int):
        self._sampler = sampler
        self._block_samples = block_samples
        self._queue: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        target_period = self._block_samples / float(self._sampler.sample_rate)
        while not self._stop.is_set():
            start = time.perf_counter()
            block = self._sampler.read_block(self._block_samples)
            with self._lock:
                self._queue.append(block)
            elapsed = time.perf_counter() - start
            sleep_time = max(0.0, target_period - elapsed)
            if sleep_time:
                time.sleep(sleep_time)

    def pop_blocks(self) -> Iterable[np.ndarray]:
        with self._lock:
            blocks = list(self._queue)
            self._queue.clear()
        return blocks
