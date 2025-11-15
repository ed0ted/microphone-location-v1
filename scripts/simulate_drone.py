#!/usr/bin/env python3
"""
Drone Sound Simulator

Simulates a drone sound source moving through the surveillance area and
sends realistic acoustic data packets to the fusion server. This allows
testing the localization system without actual hardware.

Usage:
    python scripts/simulate_drone.py --config configs/server.yaml

Options:
    --config PATH          Path to server config file (default: configs/server.yaml)
    --pattern PATTERN      Movement pattern: circle, line, hover, figure8 (default: circle)
    --speed SPEED          Movement speed in m/s (default: 2.0)
    --height HEIGHT        Fixed height in meters (default: 5.0)
    --radius RADIUS        Circle radius in meters (default: 8.0)
    --source-power POWER   Source sound power level (default: 10.0)
    --rate RATE            Update rate in Hz (default: 10.0)
    --verbose              Enable debug logging
"""

from __future__ import annotations

import argparse
import logging
import math
import socket
import time
from pathlib import Path

import numpy as np

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from node.packets import Packet
from server.config import load_config

LOGGER = logging.getLogger("drone-simulator")


class DroneSimulator:
    """Simulates a drone sound source and generates acoustic data packets."""
    
    def __init__(
        self,
        config_path: str,
        pattern: str = "circle",
        speed: float = 2.0,
        height: float = 5.0,
        radius: float = 8.0,
        source_power: float = 10.0,
        rate: float = 10.0,
    ):
        self.config = load_config(config_path)
        self.node_positions = {
            geom.node_id: np.array(geom.position, dtype=np.float32)
            for geom in self.config.nodes
        }
        self.pattern = pattern
        self.speed = speed
        self.height = height
        self.radius = radius
        self.source_power = source_power
        self.rate = rate
        self.period = 1.0 / rate
        
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.endpoint = (self.config.listen_host, self.config.listen_port)
        
        # Animation state
        self.time = 0.0
        self.seq = {node_id: 0 for node_id in self.node_positions.keys()}
        
        LOGGER.info(
            "Initialized drone simulator: pattern=%s, speed=%.1f m/s, height=%.1f m",
            pattern, speed, height
        )
        LOGGER.info("Server endpoint: %s:%d", self.endpoint[0], self.endpoint[1])
    
    def get_drone_position(self, t: float) -> np.ndarray:
        """Calculate drone position at time t based on movement pattern."""
        center_x = 10.0  # Center of surveillance area
        center_y = 10.0
        
        if self.pattern == "circle":
            angle = (t * self.speed / self.radius) % (2 * math.pi)
            x = center_x + self.radius * math.cos(angle)
            y = center_y + self.radius * math.sin(angle)
            z = self.height
        elif self.pattern == "line":
            # Fly back and forth along X-axis
            period = 2 * self.radius / self.speed
            phase = (t % period) / period
            if phase < 0.5:
                x = center_x - self.radius + 2 * self.radius * phase * 2
            else:
                x = center_x + self.radius - 2 * self.radius * (phase - 0.5) * 2
            y = center_y
            z = self.height
        elif self.pattern == "hover":
            # Stationary hover
            x = center_x
            y = center_y
            z = self.height
        elif self.pattern == "figure8":
            # Figure-8 pattern
            angle = (t * self.speed / self.radius) % (2 * math.pi)
            x = center_x + self.radius * math.sin(angle)
            y = center_y + self.radius * math.sin(angle) * math.cos(angle)
            z = self.height
        else:
            raise ValueError(f"Unknown pattern: {self.pattern}")
        
        return np.array([x, y, z], dtype=np.float32)
    
    def calculate_node_data(self, drone_pos: np.ndarray, node_id: int) -> dict:
        """Calculate acoustic energy and direction for a node given drone position."""
        node_pos = self.node_positions[node_id]
        
        # Vector from node to drone
        vec = drone_pos - node_pos
        distance = float(np.linalg.norm(vec))
        
        # Inverse square law: energy = power / (distance^2)
        # Add minimum distance to avoid division by zero
        min_dist = 0.5  # Minimum distance in meters
        effective_dist = max(distance, min_dist)
        energy = self.source_power / (effective_dist * effective_dist)
        
        # Normalize direction vector
        if distance > 0.01:
            direction = (vec / distance).tolist()
        else:
            direction = [0.0, 0.0, 1.0]  # Default to upward
        
        # Add some realistic noise/variation
        noise_factor = 1.0 + np.random.normal(0, 0.1)
        energy *= max(0.5, noise_factor)
        
        # Simulate 3 microphone channels (triangle mode)
        # Energy is distributed based on direction
        mic_energies = []
        for i in range(3):
            # Simulate directional response
            mic_dir = [
                math.cos(i * 2 * math.pi / 3),  # X component
                math.sin(i * 2 * math.pi / 3),  # Y component
                0.0  # Z component (horizontal array)
            ]
            # Dot product gives sensitivity in that direction
            sensitivity = max(0.0, np.dot(direction, mic_dir) * 0.5 + 0.5)
            mic_energies.append(energy * sensitivity * (0.8 + 0.4 * np.random.random()))
        
        # Calculate direction confidence (lower at long distances)
        max_dist = 25.0  # Maximum expected distance
        conf = max(0.3, 1.0 - (distance / max_dist))
        
        return {
            "energy": energy,
            "mic_rms": mic_energies,
            "direction": direction,
            "confidence": conf,
            "distance": distance,
        }
    
    def generate_packet(self, node_id: int, drone_pos: np.ndarray, present: bool = True) -> Packet:
        """Generate a UDP packet with simulated acoustic data."""
        self.seq[node_id] += 1
        
        if present:
            data = self.calculate_node_data(drone_pos, node_id)
            mic_rms = data["mic_rms"]
            dir_local = data["direction"]
            dir_conf = data["confidence"]
            # Simulate noise floor
            noise_rms = [0.05] * 3  # Base noise level
            crest = [e / n if n > 0 else 0.0 for e, n in zip(mic_rms, noise_rms)]
            # Two band power estimates (simulate frequency bands)
            bandpower = [mic_rms[0] * 0.8 if len(mic_rms) > 0 else 0.0,
                        mic_rms[0] * 0.6 if len(mic_rms) > 0 else 0.0]
        else:
            # No detection (quiet)
            mic_rms = [0.0] * 3
            noise_rms = [0.05] * 3
            crest = [0.0] * 3
            bandpower = [0.0, 0.0]
            dir_local = [0.0, 0.0, 0.0]
            dir_conf = 0.0
        
        # Calculate total energy
        total_energy = sum(mic_rms) if present else 0.0
        
        packet = Packet(
            node_id=node_id,
            seq=self.seq[node_id],
            ts_us=int(time.time() * 1_000_000),
            present=present,
            mic_rms=mic_rms,
            noise_rms=noise_rms,
            crest=crest,
            bandpower=bandpower,
            dir_local=dir_local,
            dir_conf=dir_conf if present else 0.0,
            supply_v=4.9,
            temp_c=25.0,
            extra={"total_energy": total_energy},
        )
        
        return packet
    
    def run(self):
        """Main simulation loop."""
        LOGGER.info("Starting drone simulation...")
        LOGGER.info("Drone pattern: %s", self.pattern)
        LOGGER.info("Sending packets at %.1f Hz", self.rate)
        
        next_time = time.time()
        
        try:
            while True:
                start = time.time()
                
                # Calculate current drone position
                drone_pos = self.get_drone_position(self.time)
                
                # Generate and send packets for each node
                for node_id in self.node_positions.keys():
                    packet = self.generate_packet(node_id, drone_pos, present=True)
                    payload = packet.to_payload()
                    try:
                        self.socket.sendto(payload, self.endpoint)
                    except OSError as exc:
                        LOGGER.error("Failed to send packet: %s", exc)
                
                if LOGGER.isEnabledFor(logging.DEBUG):
                    LOGGER.debug(
                        "Drone at [%.2f, %.2f, %.2f] | seq=%s",
                        drone_pos[0], drone_pos[1], drone_pos[2],
                        {k: v for k, v in self.seq.items()}
                    )
                
                # Update simulation time
                self.time += self.period
                
                # Sleep to maintain rate
                next_time += self.period
                sleep_time = max(0.0, next_time - time.time())
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
        except KeyboardInterrupt:
            LOGGER.info("Simulation stopped by user")
        finally:
            self.socket.close()


def main():
    parser = argparse.ArgumentParser(
        description="Simulate drone sound source for testing localization system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--config",
        default="configs/server.yaml",
        help="Path to server config file"
    )
    parser.add_argument(
        "--pattern",
        choices=["circle", "line", "hover", "figure8"],
        default="circle",
        help="Movement pattern (default: circle)"
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=2.0,
        help="Movement speed in m/s (default: 2.0)"
    )
    parser.add_argument(
        "--height",
        type=float,
        default=5.0,
        help="Fixed height in meters (default: 5.0)"
    )
    parser.add_argument(
        "--radius",
        type=float,
        default=8.0,
        help="Circle/pattern radius in meters (default: 8.0)"
    )
    parser.add_argument(
        "--source-power",
        type=float,
        default=10.0,
        help="Source sound power level (default: 10.0)"
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=10.0,
        help="Update rate in Hz (default: 10.0)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    
    # Create and run simulator
    simulator = DroneSimulator(
        config_path=args.config,
        pattern=args.pattern,
        speed=args.speed,
        height=args.height,
        radius=args.radius,
        source_power=args.source_power,
        rate=args.rate,
    )
    
    simulator.run()


if __name__ == "__main__":
    main()

