from __future__ import annotations

import threading
import time

from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO

from ..config import FusionConfig
from ..state_store import FrameStore

app = Flask(__name__, static_folder="static", template_folder="templates")
socketio = SocketIO(app, cors_allowed_origins="*")
STORE: FrameStore | None = None
CONFIG: FusionConfig | None = None


def init_app(store: FrameStore, config: FusionConfig) -> None:
    global STORE, CONFIG
    STORE = store
    CONFIG = config


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
    while True:
        socketio.emit("fusion_update", STORE.get_fusion_state().__dict__)
        time.sleep(0.2)


def start_background_emit() -> None:
    thread = threading.Thread(target=_emit_loop, daemon=True)
    thread.start()


def run(host: str = "0.0.0.0", port: int = 80) -> None:
    start_background_emit()
    socketio.run(app, host=host, port=port)
