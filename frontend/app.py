import os
import json
import time
import threading
from datetime import datetime
from collections import deque

import requests
from flask import Flask, render_template, request as flask_request, jsonify

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------
BALANCEADOR = os.getenv("BALANCEADOR_URL", "http://balanceador:80")
NODO_PRINCIPAL = os.getenv("NODO_PRINCIPAL_URL", "http://nodo-principal:80")
NODO_REPLICA = os.getenv("NODO_REPLICA_URL", "http://nodo-replica:80")
NODOS = {"nodo-principal": NODO_PRINCIPAL, "nodo-replica": NODO_REPLICA}

HISTORY_MAX = 50
history = deque(maxlen=HISTORY_MAX)
lock = threading.Lock()

# ---------------------------------------------------------------------------
# Utilerias
# ---------------------------------------------------------------------------
def check_node(name: str, url: str) -> dict:
    try:
        r = requests.get(f"{url}/health", timeout=3)
        data = r.json()
        return {
            "name": name,
            "status": "healthy" if r.ok else "error",
            "role": data.get("node", "unknown"),
        }
    except Exception as exc:
        return {"name": name, "status": "down", "role": str(exc)}


def get_nodes_status() -> list[dict]:
    results = []
    for name, url in NODOS.items():
        results.append(check_node(name, url))
    return results


def add_history(entry: dict):
    entry["time"] = datetime.now().strftime("%H:%M:%S")
    with lock:
        history.appendleft(entry)


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def api_health():
    return jsonify({"nodes": get_nodes_status()})


@app.route("/api/history")
def api_history():
    with lock:
        return jsonify(list(history))


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    source = flask_request.json.get("source", "").strip()
    if not source:
        return jsonify({"error": "source required"}), 400

    result = None
    node_name = "unknown"
    error = None

    for name, url in NODOS.items():
        try:
            r = requests.post(
                f"{url}/analyze",
                json={"source": source},
                timeout=120,
            )
            if r.ok:
                result = r.json()
                node_name = result.get("nodo", name)
                break
            error = r.text
        except Exception as exc:
            error = str(exc)
            continue

    if result is None:
        add_history({
            "source": source,
            "node": "—",
            "status": "error",
            "detail": error or "No nodes available",
        })
        return jsonify({"error": error or "No nodes available"}), 503

    add_history({
        "source": source,
        "node": node_name,
        "status": "ok",
        "tokens": result.get("tokens", []),
        "sintaxis": result.get("sintaxis", {}),
    })
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.getenv("FRONTEND_PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
