import sys
from app import create_app

if __name__ == "__main__":
    app = create_app()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"Servidor Flask iniciado en http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
