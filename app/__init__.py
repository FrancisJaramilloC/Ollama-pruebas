"""
Módulo de inicialización de la aplicación Flask.
Define la fábrica de aplicaciones `create_app` para configurar las rutas
de plantillas (templates) y archivos estáticos (static), así como registrar los blueprints de la app.
"""
import os
from flask import Flask
from app.controllers.compiler_controller import compiler_bp

def create_app():
    """
    Crea, configura e inicializa una instancia de la aplicación Flask.
    Registra el blueprint del controlador del compilador y establece las rutas de recursos.
    
    :return: Instancia configurada de la aplicación Flask.
    """
    # Obtener el directorio base de este archivo (directorio 'app/')
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')
    
    # Inicializa la aplicación Flask especificando los directorios de plantillas y archivos estáticos
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    
    # Registra el Blueprint que maneja las rutas del compilador
    app.register_blueprint(compiler_bp)
    
    return app
