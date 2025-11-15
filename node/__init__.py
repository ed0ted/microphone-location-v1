"""
Node-side package for the acoustic drone localization prototype.

Modules:
    config          – Dataclasses + helpers for YAML config.
    ads_sampler     – Hardware/simulated ADS1115 sampling utilities.
    dsp             – Feature extraction, noise tracking, detection logic.
    packets         – Serialization helpers and CRC tagging.
    node_agent      – Main CLI entry point for Pi Zero nodes.
"""

__all__ = [
    "config",
    "ads_sampler",
    "dsp",
    "packets",
    "node_agent",
]
