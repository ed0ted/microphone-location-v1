from __future__ import annotations

import threading
import time

from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO

from ..config import FusionConfig
from ..state_store import FrameStore

app = Flask(__name__, static_folder="static", template_folder="templates")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading", logger=False, engineio_logger=False)
STORE: FrameStore | None = None
CONFIG: FusionConfig | None = None


def init_app(store: FrameStore, config: FusionConfig) -> None:
    global STORE, CONFIG
    STORE = store
    CONFIG = config


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
    socketio.run(app, host=host, port=port)
