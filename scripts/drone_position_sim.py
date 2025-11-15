#!/usr/bin/env python3
"""
Drone Position Simulator

Simulates a moving drone by updating its 3D position in a shared state file.
The node simulators read this position to generate realistic audio signals.

Usage:
    python scripts/drone_position_sim.py --pattern circle --speed 2.0 --height 5.0

This should be run alongside actual node agents using simulated audio.
"""

from __future__ import annotations

import argparse
import logging
import math
import signal
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from node.drone_audio_sim import write_drone_state

LOGGER = logging.getLogger("drone-position-sim")


class DronePositionSimulator:
    """Simulates drone movement and updates shared position state."""
    
    def __init__(
        self,
        pattern: str = "circle",
        speed: float = 2.0,
        height: float = 5.0,
        radius: float = 8.0,
        rate: float = 20.0,
        state_file: str = "/tmp/drone_sim_state.json",
    ):
        self.pattern = pattern
        self.speed = speed
        self.height = height
        self.radius = radius
        self.rate = rate
        self.period = 1.0 / rate
        self.state_file = state_file
        
        # Animation state
        self.time = 0.0
        self._stop = False
        
        LOGGER.info(
            "Initialized drone position simulator: pattern=%s, speed=%.1f m/s, height=%.1f m",
            pattern, speed, height
        )
        LOGGER.info("State file: %s", state_file)
    
    def get_drone_position(self, t: float) -> list[float]:
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
        elif self.pattern == "diagonal":
            # Diagonal path
            period = 2 * self.radius * 1.414 / self.speed  # sqrt(2) for diagonal
            phase = (t % period) / period
            if phase < 0.5:
                x = center_x - self.radius + 2 * self.radius * phase * 2
                y = center_y - self.radius + 2 * self.radius * phase * 2
            else:
                x = center_x + self.radius - 2 * self.radius * (phase - 0.5) * 2
                y = center_y + self.radius - 2 * self.radius * (phase - 0.5) * 2
            z = self.height
        else:
            raise ValueError(f"Unknown pattern: {self.pattern}")
        
        return [x, y, z]
    
    def run(self):
        """Main simulation loop."""
        LOGGER.info("Starting drone position simulation...")
        LOGGER.info("Drone pattern: %s", self.pattern)
        LOGGER.info("Updating position at %.1f Hz", self.rate)
        
        def signal_handler(signum, frame):
            LOGGER.info("Received signal %d, stopping...", signum)
            self._stop = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        next_time = time.time()
        
        try:
            while not self._stop:
                # Calculate current drone position
                position = self.get_drone_position(self.time)
                
                # Write to shared state file
                write_drone_state(position, self.state_file)
                
                if LOGGER.isEnabledFor(logging.DEBUG):
                    LOGGER.debug(
                        "Drone position: [%.2f, %.2f, %.2f]",
                        position[0], position[1], position[2]
                    )
                elif self.time % 5.0 < self.period:  # Log every 5 seconds
                    LOGGER.info(
                        "Drone at [%.2f, %.2f, %.2f]",
                        position[0], position[1], position[2]
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
            LOGGER.info("Drone position simulator stopped")


def main():
    parser = argparse.ArgumentParser(
        description="Simulate drone position for realistic audio generation in nodes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--pattern",
        choices=["circle", "line", "hover", "figure8", "diagonal"],
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
        "--rate",
        type=float,
        default=20.0,
        help="Update rate in Hz (default: 20.0)"
    )
    parser.add_argument(
        "--state-file",
        default="/tmp/drone_sim_state.json",
        help="Path to shared state file (default: /tmp/drone_sim_state.json)"
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
    simulator = DronePositionSimulator(
        pattern=args.pattern,
        speed=args.speed,
        height=args.height,
        radius=args.radius,
        rate=args.rate,
        state_file=args.state_file,
    )
    
    simulator.run()


if __name__ == "__main__":
    main()

