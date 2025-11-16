from __future__ import annotations

import threading
import time

import os

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO

from ..config import FusionConfig
from ..state_store import FrameStore
from .calibration_manager import CalibrationManager

app = Flask(__name__, static_folder="static", template_folder="templates")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading", logger=False, engineio_logger=False)
STORE: FrameStore | None = None
CONFIG: FusionConfig | None = None
CALIBRATION_MANAGER: CalibrationManager | None = None


def init_app(store: FrameStore, config: FusionConfig) -> None:
    global STORE, CONFIG, CALIBRATION_MANAGER
    STORE = store
    CONFIG = config
    if CALIBRATION_MANAGER is None:
        config_dir = os.environ.get("NODE_CONFIG_DIR", "configs")
        CALIBRATION_MANAGER = CalibrationManager(store, config_dir)


@socketio.on("connect")
def handle_connect():
    import logging
    logger = logging.getLogger("web-socketio")
    logger.info("Client connected")


@socketio.on("disconnect")
def handle_disconnect():
    import logging
    logger = logging.getLogger("web-socketio")
    logger.info("Client disconnected")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def api_state():
    assert STORE is not None
    return jsonify(STORE.get_fusion_state().__dict__)


@app.route("/api/nodes")
def api_nodes():
    assert STORE is not None
    return jsonify(STORE.get_node_health())


@app.route("/api/config")
def api_config():
    assert CONFIG is not None
    return jsonify({
        "nodes": [{"id": node.node_id, "position": node.position} for node in CONFIG.nodes],
        "grid_bounds": CONFIG.grid_bounds,
    })


@app.route("/api/calibration", methods=["GET"])
def api_calibration_status():
    assert CALIBRATION_MANAGER is not None
    return jsonify({
        "config_dir": str(CALIBRATION_MANAGER.config_dir),
        "jobs": CALIBRATION_MANAGER.get_status(),
        "defaults": {"duration": 60.0},
    })


@app.route("/api/calibration/start", methods=["POST"])
def api_calibration_start():
    assert CALIBRATION_MANAGER is not None
    data = request.get_json(silent=True) or {}
    node_id = data.get("node_id")
    duration = data.get("duration", 60)
    if node_id is None:
        return jsonify({"error": "node_id is required"}), 400
    try:
        duration = float(duration)
        job = CALIBRATION_MANAGER.start_job(int(node_id), duration)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({
        "status": "started",
        "job": {
            "node_id": job.node_id,
            "job_id": job.job_id,
            "duration": job.duration,
            "started_at": job.started_at,
        },
    }), 201


def _emit_loop():
    assert STORE is not None
    import logging
    logger = logging.getLogger("web-emit")
    logger.info("Starting WebSocket emit loop")
    
    while True:
        try:
            state = STORE.get_fusion_state()
            if state:
                socketio.emit("fusion_update", state.__dict__)
            time.sleep(0.2)
        except Exception as exc:
            logger.error("Error in emit loop: %s", exc)
            time.sleep(1.0)


def start_background_emit() -> None:
    thread = threading.Thread(target=_emit_loop, daemon=True)
    thread.start()


def run(host: str = "0.0.0.0", port: int = 80) -> None:
    start_background_emit()
    socketio.run(app, host=host, port=port, allow_unsafe_werkzeug=True)
