from __future__ import annotations

import argparse
import logging
import signal
import socket
import sys
import time
from pathlib import Path
from typing import Iterable

import numpy as np

from .ads_sampler import AdcSampler
from .config import NodeConfig, dump_config, load_config
from .dsp import FeatureExtractor
from .packets import Packet

LOGGER = logging.getLogger("drone-node")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


class NodeAgent:
    def __init__(self, config: NodeConfig):
        self.config = config
        self.sampler = AdcSampler(config)
        sampling = config.sampling
        frame_hop = int(sampling.sample_rate * (sampling.frame_hop_ms / 1000.0))
        self.extractor = FeatureExtractor(
            sample_rate=sampling.sample_rate,
            frame_hop=frame_hop,
            window_seconds=sampling.window_seconds,
            mic_vectors=config.mic_vectors,
            num_channels=config.num_channels,
            noise_init=config.calibration_noise_rms,
        )
        self.seq = 0
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.endpoint = config.fusion_endpoint
        self._stop = False
        self._last_frame_ts = time.time()
        LOGGER.info(
            "Node %d initialized in %s mode (%d channels)",
            config.node_id,
            config.array_mode,
            config.num_channels,
        )

    def run(self) -> None:
        LOGGER.info("Starting node agent for node_id=%s endpoint=%s", self.config.node_id, self.endpoint)
        block_samples = self.config.sampling.block_samples
        hdr_rate = self.config.network.heartbeat_hz
        heartbeat_interval = 1.0 / hdr_rate if hdr_rate else 0
        last_heartbeat = 0.0

        while not self._stop:
            block = self.sampler.read_block(block_samples)
            frames = self.extractor.push(block)
            now = time.time()
            if frames:
                last_heartbeat = now
                for frame in frames:
                    self.seq += 1
                    pkt = Packet.from_frame(
                        node_id=self.config.node_id,
                        seq=self.seq,
                        frame=frame,
                        supply_v=4.9,
                        temp_c=37.0,
                    )
                    self._send(pkt)
                    self._last_frame_ts = frame.timestamp
            elif heartbeat_interval and (now - last_heartbeat) >= heartbeat_interval:
                last_heartbeat = now
                self.seq += 1
                num_ch = self.config.num_channels
                pkt = Packet(
                    node_id=self.config.node_id,
                    seq=self.seq,
                    ts_us=int(now * 1_000_000),
                    present=False,
                    mic_rms=[0.0] * num_ch,
                    noise_rms=[float(x) for x in self.extractor.noise_tracker.level],
                    crest=[0.0] * num_ch,
                    bandpower=[0.0, 0.0],
                    dir_local=[0.0, 0.0, 0.0],
                    dir_conf=0.0,
                    supply_v=4.9,
                    temp_c=37.0,
                    extra={"heartbeat": True},
                )
                self._send(pkt)

    def stop(self) -> None:
        self._stop = True

    def _send(self, packet: Packet) -> None:
        payload = packet.to_payload()
        try:
            self.socket.sendto(payload, self.endpoint)
            if LOGGER.isEnabledFor(logging.DEBUG):
                pkt_type = "heartbeat" if packet.extra and packet.extra.get("heartbeat") else "detection" if packet.present else "data"
                LOGGER.debug(
                    "Sent packet seq=%d type=%s present=%s energy=%.4f",
                    packet.seq, pkt_type, packet.present, sum(packet.mic_rms)
                )
        except OSError as exc:
            LOGGER.error("Failed to send packet: %s", exc)


def _load_config_or_exit(path: str) -> NodeConfig:
    try:
        return load_config(path)
    except FileNotFoundError:
        LOGGER.error("Config file %s not found", path)
    except Exception as exc:
        LOGGER.error("Failed to load config: %s", exc)
    sys.exit(1)


def run_agent(args: argparse.Namespace) -> None:
    config = _load_config_or_exit(args.config)
    agent = NodeAgent(config)

    def _handle_signal(signum, _frame):
        LOGGER.info("Received signal %s, stopping node agent", signum)
        agent.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    agent.run()


def _collect_samples(config: NodeConfig, duration: float) -> np.ndarray:
    sampler = AdcSampler(config)
    samples_needed = int(config.sampling.sample_rate * duration)
    blocks = []
    while sum(block.shape[1] for block in blocks) < samples_needed:
        blocks.append(sampler.read_block(config.sampling.block_samples))
    return np.concatenate(blocks, axis=1)[:, :samples_needed]


def run_calibrate(args: argparse.Namespace) -> None:
    config = _load_config_or_exit(args.config)
    LOGGER.info("Starting calibration for %.1f seconds", args.duration)
    all_samples = _collect_samples(config, args.duration)
    rms = np.sqrt(np.mean(all_samples**2, axis=1))
    config.calibration_noise_rms = [float(x) for x in rms]
    dump_config(config, args.config)
    LOGGER.info("Updated calibration noise RMS to %s", config.calibration_noise_rms)


def run_capture(args: argparse.Namespace) -> None:
    config = _load_config_or_exit(args.config)
    LOGGER.info("Capturing raw samples for %.1f seconds", args.duration)
    all_samples = _collect_samples(config, args.duration)
    out = Path(args.output or f"capture-node{config.node_id}.npy")
    np.save(out, all_samples)
    LOGGER.info("Saved capture to %s", out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Raspberry Pi node agent")
    parser.add_argument("--config", default="configs/node-1.yaml", help="Path to node config YAML")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    sub = parser.add_subparsers(dest="command")
    run_cmd = sub.add_parser("run", help="Run the node agent (default)")
    run_cmd.set_defaults(func=run_agent)
    cal_cmd = sub.add_parser("calibrate", help="Calibrate ambient noise levels")
    cal_cmd.add_argument("--duration", type=float, default=60.0, help="Seconds to record for calibration")
    cal_cmd.set_defaults(func=run_calibrate)
    cap_cmd = sub.add_parser("capture", help="Capture raw samples to .npy file")
    cap_cmd.add_argument("--duration", type=float, default=10.0, help="Seconds to capture")
    cap_cmd.add_argument("--output", help="Output filename (.npy)")
    cap_cmd.set_defaults(func=run_capture)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    _setup_logging(args.verbose)
    if not args.command:
        args.command = "run"
        args.func = run_agent
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
