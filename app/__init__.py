import os
from flask import Flask
from app.controllers.compiler_controller import compiler_bp

def create_app():
    # Obtener el directorio de este archivo (app/)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')
    
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    app.register_blueprint(compiler_bp)
    
    return app
