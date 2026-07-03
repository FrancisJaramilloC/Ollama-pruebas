import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

from ollama_client import OllamaClient
from lexical_service import LexicalService
from syntactic_service import SyntacticService


class CompilerHandler(BaseHTTPRequestHandler):

    def do_POST(self):
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

        parser = SyntacticService(tokens)
        sintaxis = parser.validate()

        self._send_json(200, {
            "entrada": source,
            "tokens": tokens,
            "sintaxis": sintaxis
        })

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"POST /analyze con JSON body: {\"source\": \"...\"}")

    def _send_json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = HTTPServer(("0.0.0.0", port), CompilerHandler)
    print(f"Servidor en http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
