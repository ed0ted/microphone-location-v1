"""
Realistic Drone Audio Simulator

Generates realistic microphone audio signals simulating a drone sound source.
Uses acoustic propagation models (inverse square law) and microphone array geometry.
"""

from __future__ import annotations

import json
import logging
import math
import time
from pathlib import Path
from typing import Optional

import numpy as np

LOGGER = logging.getLogger(__name__)


class DroneAudioSimulator:
    """
    Generates realistic audio signals for a microphone array based on
    a simulated drone position in 3D space.
    """
    
    def __init__(
        self,
        sample_rate: int,
        channels: int,
        node_position: np.ndarray,
        mic_positions: list[list[float]],
        state_file: str = "/tmp/drone_sim_state.json",
        noise_level: float = 0.02,
    ):
        """
        Args:
            sample_rate: Audio sample rate (Hz)
            channels: Number of microphone channels
            node_position: Position of the node [x, y, z] in meters
            mic_positions: Positions of each microphone relative to node center
            state_file: Path to shared state file with drone position
            noise_level: Background noise amplitude (volts RMS)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.node_position = np.array(node_position, dtype=np.float32)
        self.mic_positions = [np.array(pos, dtype=np.float32) for pos in mic_positions]
        self.state_file = Path(state_file)
        self.noise_level = noise_level
        
        # Drone sound characteristics
        self.base_freqs = [150, 300, 450, 600, 750]  # Harmonics of ~150 Hz
        self.freq_amplitudes = [1.0, 0.6, 0.4, 0.25, 0.15]  # Decreasing harmonic amplitudes
        
        # Phase tracking for continuous signal generation
        self.phases = np.zeros((self.channels, len(self.base_freqs)))
        
        # Random number generator
        self.rng = np.random.default_rng()
        
        # Cache for drone position to avoid excessive file reads
        self._last_read_time = 0.0
        self._cached_drone_pos = None
        self._read_interval = 0.05  # Read state file every 50ms
        
        LOGGER.info(
            "Initialized drone audio simulator for node at %s with %d mics",
            self.node_position, self.channels
        )
    
    def _read_drone_position(self) -> Optional[np.ndarray]:
        """Read current drone position from shared state file."""
        now = time.time()
        
        # Use cached position if we read recently
        if now - self._last_read_time < self._read_interval and self._cached_drone_pos is not None:
            return self._cached_drone_pos
        
        try:
            if self.state_file.exists() and self.state_file.stat().st_size > 0:
                with open(self.state_file, 'r') as f:
                    content = f.read().strip()
                    if not content:
                        # File exists but is empty - drone simulator not started yet
                        return None
                    state = json.loads(content)
                    drone_pos = np.array(state.get('position', [10, 10, 5]), dtype=np.float32)
                    self._cached_drone_pos = drone_pos
                    self._last_read_time = now
                    return drone_pos
        except json.JSONDecodeError:
            # File exists but has invalid JSON - might be in the middle of being written
            # This is normal, just return None and try again next time
            pass
        except Exception as exc:
            # Only log non-JSON errors at debug level
            if "JSON" not in str(exc):
                LOGGER.debug("Failed to read drone state: %s", exc)
        
        # No valid position available yet
        return None
    
    def _generate_drone_signal(
        self, 
        samples: int, 
        mic_idx: int, 
        distance: float,
        direction: np.ndarray
    ) -> np.ndarray:
        """
        Generate drone audio signal for a single microphone.
        
        Args:
            samples: Number of samples to generate
            mic_idx: Microphone channel index
            distance: Distance from microphone to drone (meters)
            direction: Normalized direction vector from mic to drone
        
        Returns:
            Audio signal (samples,) in volts
        """
        t = np.arange(samples) / float(self.sample_rate)
        signal = np.zeros(samples, dtype=np.float32)
        
        # Apply inverse square law for amplitude
        # At 1 meter, amplitude is ~200V RMS (loud drone sound source)
        # This is calibrated so that at typical distances (10-20m) the signal
        # exceeds the detection threshold of ~0.5V RMS
        # Add minimum distance to avoid singularity
        min_dist = 0.5
        effective_dist = max(distance, min_dist)
        base_amplitude = 200.0 / (effective_dist * effective_dist)
        
        # Generate harmonic content (drone motor sounds)
        for i, (freq, amp) in enumerate(zip(self.base_freqs, self.freq_amplitudes)):
            # Add frequency modulation to simulate varying motor speed
            freq_mod = freq * (1.0 + 0.03 * math.sin(time.time() * 2.0 + i))
            
            # Update phase for continuity
            phase_increment = freq_mod * samples / self.sample_rate
            phase = self.phases[mic_idx, i]
            
            # Generate tone
            tone = amp * np.sin(2 * math.pi * freq_mod * t + phase)
            signal += tone * base_amplitude
            
            # Update phase for next block
            self.phases[mic_idx, i] = (phase + 2 * math.pi * phase_increment) % (2 * math.pi)
        
        # Add broadband noise (aerodynamic noise)
        broadband = self.rng.normal(0, 0.1, size=samples)
        # Low-pass filter the broadband (simple moving average)
        window = 5
        broadband = np.convolve(broadband, np.ones(window)/window, mode='same')
        signal += broadband * base_amplitude * 0.3
        
        # Microphone directional response (cardioid pattern approximation)
        # Microphones are more sensitive in their pointing direction
        mic_direction = self.mic_positions[mic_idx]
        if np.linalg.norm(mic_direction) > 0.01:
            mic_dir_norm = mic_direction / np.linalg.norm(mic_direction)
            # Cardioid: response = 0.5 + 0.5 * cos(angle)
            dot = np.dot(mic_dir_norm, direction)
            directional_gain = 0.5 + 0.5 * max(-1, min(1, dot))
        else:
            directional_gain = 1.0  # Omnidirectional
        
        signal *= directional_gain
        
        return signal
    
    def generate_block(self, samples: int) -> np.ndarray:
        """
        Generate a block of audio samples for all microphone channels.
        
        Args:
            samples: Number of samples to generate
        
        Returns:
            Audio block of shape (channels, samples) in volts
        """
        drone_pos = self._read_drone_position()
        
        block = []
        for mic_idx in range(self.channels):
            # Calculate absolute microphone position
            mic_pos_abs = self.node_position + self.mic_positions[mic_idx]
            
            if drone_pos is not None:
                # Vector from microphone to drone
                vec = drone_pos - mic_pos_abs
                distance = float(np.linalg.norm(vec))
                
                if distance > 0.01:
                    direction = vec / distance
                else:
                    direction = np.array([0, 0, 1], dtype=np.float32)
                
                # Generate drone signal
                signal = self._generate_drone_signal(samples, mic_idx, distance, direction)
            else:
                # No drone present - just noise
                signal = np.zeros(samples, dtype=np.float32)
            
            # Add background noise
            noise = self.rng.normal(0, self.noise_level, size=samples)
            channel_signal = signal + noise
            
            block.append(channel_signal)
        
        return np.asarray(block, dtype=np.float32)


def write_drone_state(position: list[float], state_file: str = "/tmp/drone_sim_state.json"):
    """Write drone position to shared state file."""
    state = {
        'position': position,
        'timestamp': time.time()
    }
    with open(state_file, 'w') as f:
        json.dump(state, f)

