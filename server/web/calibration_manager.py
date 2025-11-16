from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from node.config import dump_config, load_config

from ..state_store import FrameStore


@dataclass
class CalibrationJob:
    node_id: int
    duration: float
    status: str = "pending"
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    progress: float = 0.0
    result: Optional[List[float]] = None
    message: str = ""
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    sample_count: int = 0
    last_seq: Optional[int] = None
    _samples: List[List[float]] = field(default_factory=list, repr=False)


class CalibrationManager:
    """Collects noise RMS samples from the live stream and updates node configs."""

    def __init__(self, store: FrameStore, config_dir: str | Path, poll_interval: float = 0.5):
        self.store = store
        self.config_dir = Path(config_dir)
        self.poll_interval = poll_interval
        self.jobs: Dict[int, CalibrationJob] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def start_job(self, node_id: int, duration: float) -> CalibrationJob:
        if duration <= 0:
            raise ValueError("Duration must be positive")
        with self._lock:
            job = self.jobs.get(node_id)
            if job and job.status in {"running", "processing"}:
                raise ValueError("Calibration already in progress for this node")
            job = CalibrationJob(node_id=node_id, duration=duration, status="running")
            job.started_at = time.time()
            job.progress = 0.0
            job.completed_at = None
            job.result = None
            job.message = "Collecting noise samples"
            job.sample_count = 0
            job.last_seq = None
            job._samples.clear()
            self.jobs[node_id] = job
            return job

    def get_job(self, node_id: int) -> Optional[CalibrationJob]:
        with self._lock:
            return self.jobs.get(node_id)

    def get_status(self) -> List[dict]:
        with self._lock:
            return [
                {
                    "node_id": job.node_id,
                    "job_id": job.job_id,
                    "status": job.status,
                    "duration": job.duration,
                    "started_at": job.started_at,
                    "completed_at": job.completed_at,
                    "progress": min(job.progress, 1.0),
                    "message": job.message,
                    "sample_count": job.sample_count,
                    "result": job.result,
                }
                for job in self.jobs.values()
            ]

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._tick()
            time.sleep(self.poll_interval)

    def _tick(self) -> None:
        frames = self.store.get_frames()
        now = time.time()
        finalize_nodes: List[int] = []

        with self._lock:
            for node_id, job in self.jobs.items():
                if job.status != "running":
                    continue
                frame = frames.get(node_id)
                if frame and frame.seq != job.last_seq:
                    noise = frame.noise_rms or frame.mic_rms or []
                    if noise:
                        job._samples.append([float(x) for x in noise])
                        job.sample_count += 1
                        job.last_seq = frame.seq
                elapsed = now - job.started_at
                job.progress = min(elapsed / job.duration, 0.99)
                if elapsed >= job.duration:
                    job.status = "processing"
                    job.message = "Computing averages..."
                    finalize_nodes.append(node_id)

        for node_id in finalize_nodes:
            self._finalize_job(node_id)

    def _finalize_job(self, node_id: int) -> None:
        with self._lock:
            job = self.jobs.get(node_id)
            if not job:
                return
            samples = list(job._samples)

        if not samples:
            self._set_error(node_id, "No samples collected from node")
            return

        channel_count = max(len(sample) for sample in samples)
        totals = [0.0] * channel_count
        counts = [0] * channel_count
        for sample in samples:
            for idx, value in enumerate(sample):
                totals[idx] += value
                counts[idx] += 1
        averages = []
        for idx in range(channel_count):
            if counts[idx] == 0:
                averages.append(0.0)
            else:
                averages.append(round(totals[idx] / counts[idx], 6))

        config_path = self.config_dir / f"node-{node_id}.yaml"
        try:
            config = load_config(config_path)
            config.calibration_noise_rms = averages
            dump_config(config, config_path)
        except FileNotFoundError:
            self._set_error(node_id, f"Config not found: {config_path}")
            return
        except Exception as exc:
            self._set_error(node_id, f"Failed to update config: {exc}")
            return

        with self._lock:
            job = self.jobs.get(node_id)
            if not job:
                return
            job.status = "completed"
            job.result = averages
            job.message = f"Updated {config_path.name}"
            job.progress = 1.0
            job.completed_at = time.time()

    def _set_error(self, node_id: int, message: str) -> None:
        with self._lock:
            job = self.jobs.get(node_id)
            if not job:
                return
            job.status = "failed"
            job.message = message
            job.progress = 1.0
            job.completed_at = time.time()
