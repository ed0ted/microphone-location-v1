from __future__ import annotations

import asyncio
import binascii
import json
import logging
from dataclasses import asdict
from typing import Any, Dict, Tuple

from .state_store import Frame, FrameStore

LOGGER = logging.getLogger("fusion-receiver")


def parse_packet(data: bytes) -> Tuple[Dict[str, Any], str]:
    try:
        payload, crc_hex = data.rsplit(b"|", 1)
        computed = f"{binascii.crc32(payload) & 0xFFFFFFFF:08x}"
        if computed.encode("ascii") != crc_hex:
            raise ValueError("CRC mismatch")
        decoded = json.loads(payload.decode("utf-8"))
        return decoded, crc_hex.decode("ascii")
    except ValueError as exc:
        raise ValueError(f"Invalid packet: {exc}") from exc


class FusionReceiverProtocol(asyncio.DatagramProtocol):
    def __init__(self, store: FrameStore):
        self.store = store

    def datagram_received(self, data: bytes, addr):
        try:
            payload, crc = parse_packet(data)
            frame = Frame(
                node_id=payload["node_id"],
                seq=payload["seq"],
                timestamp=payload["ts_us"] / 1_000_000.0,
                present=payload.get("present", False),
                mic_rms=payload.get("mic_rms", []),
                noise_rms=payload.get("noise_rms", []),
                crest=payload.get("crest", []),
                bandpower=payload.get("bandpower", []),
                dir_local=payload.get("dir_local", []),
                dir_conf=payload.get("dir_conf", 0.0),
                total_energy=float(payload.get("total_energy", sum(payload.get("mic_rms", [])))),
                extra=payload,
            )
            self.store.update_frame(frame)
        except Exception as exc:
            LOGGER.warning("Failed to parse packet from %s: %s", addr, exc)


async def run_receiver(host: str, port: int, store: FrameStore) -> None:
    LOGGER.info("Starting fusion receiver on %s:%s", host, port)
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: FusionReceiverProtocol(store), local_addr=(host, port)
    )
    try:
        while True:
            await asyncio.sleep(1.0)
            store.mark_offline()
    finally:
        transport.close()
