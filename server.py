"""
Punto de entrada alternativo para iniciar el servidor de recetas Flask con arquitectura MVC.
Lee opcionalmente un puerto desde los argumentos de la línea de comandos (por defecto 8000).
"""
import sys
from app import create_app

if __name__ == "__main__":
    # Crea la instancia de la aplicación Flask.
    app = create_app()
    
    # Determina el puerto de ejecución; si se pasa un argumento, se usa este, de lo contrario se inicia en el puerto 8000.
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"Servidor de Recetas (Flask - MVC) corriendo en http://localhost:{port}")
    
    # Inicia el servidor de desarrollo Flask accesible de forma externa y con modo de depuración activado.
    app.run(host="0.0.0.0", port=port, debug=True)

