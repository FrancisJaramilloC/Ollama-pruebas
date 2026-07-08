import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from src.clients.ollama import OllamaClient
from src.analyzers.lexical import LexicalService
from src.analyzers.syntactic import SyntacticService
from src.storage import RecipeStorage


storage = RecipeStorage()


class CompilerHandler(BaseHTTPRequestHandler):

    # ------------------------------------------------------------------
    # Enrutamiento por path
    # ------------------------------------------------------------------
    def _route(self, method: str):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if method == "GET" and path == "/health":
            self._handle_health()
            return
        elif method == "GET" and path == "":
            self._handle_root()
            return
        if method == "POST" and path == "/analyze":
            self._handle_analyze()
            return
        elif method == "GET" and path == "/internal/recipes":
            self._handle_get_recipes()
            return
        elif method == "POST" and path == "/internal/recipes":
            self._handle_receive_recipe()
            return
        elif method == "POST" and path == "/internal/sync":
            self._handle_trigger_sync()
            return
        else:
            self._send_json(404, {"error": "Ruta no encontrada"})

    # ------------------------------------------------------------------
    # Endpoint publico: POST /analyze
    # ------------------------------------------------------------------
    def _handle_health(self):
        self._send_json(200, {"status": "ok", "node": os.environ.get("NODE_ROLE", "unknown")})

    def _handle_root(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def _handle_analyze(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            self._send_json(400, {"error": "JSON invalido"})
            return

        source = data.get("source", "").strip()
        if not source:
            self._send_json(400, {"error": "Campo 'source' requerido"})
            return

        llm = OllamaClient()
        lexer = LexicalService(llm)
        tokens = lexer.analyze(source)

        parser = SyntacticService(llm, tokens)
        sintaxis = parser.validate()

        result = {
            "entrada": source,
            "tokens": tokens,
            "sintaxis": sintaxis
        }

        # Persistir en la base central y dejar la coherencia entre primary/replica a la BD
        record = storage.save(source, tokens, sintaxis)
        result["id"] = record["id"]
        result["nodo"] = os.environ.get("NODE_ROLE", "unknown")

        self._send_json(200, result)

    # ------------------------------------------------------------------
    # Endpoint interno: GET /internal/recipes
    # ------------------------------------------------------------------
    def _handle_get_recipes(self):
        recipes = storage.get_all()
        self._send_json(200, recipes)

    # ------------------------------------------------------------------
    # Endpoint interno: POST /internal/recipes
    # Recibe una receta replicada desde el nodo principal
    # ------------------------------------------------------------------
    def _handle_receive_recipe(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            record = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            self._send_json(400, {"error": "JSON invalido"})
            return

        local = storage.get_by_id(record["id"])
        if local is None:
            storage.save(
                record["entrada"],
                record["tokens"],
                record["sintaxis"],
                recipe_id=record["id"],
            )
            print(f"  [SYNC] Receta {record['id']} recibida del nodo-principal")
            self._send_json(200, {"status": "sincronizado"})
        else:
            self._send_json(200, {"status": "ya existe"})

    # ------------------------------------------------------------------
    # Endpoint interno: POST /internal/sync
    # ------------------------------------------------------------------
    def _handle_trigger_sync(self):
        self._send_json(200, {"status": "sincronizacion gestionada por la base de datos"})

    def do_GET(self):
        self._route("GET")

    def do_POST(self):
        self._route("POST")

    def _send_json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

    server = HTTPServer(("0.0.0.0", port), CompilerHandler)
    print(f"  Nodo: {os.environ.get('NODE_ROLE', 'unknown')}")
    print(f"  Puerto: {port}")
    print(f"  Servidor en http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
