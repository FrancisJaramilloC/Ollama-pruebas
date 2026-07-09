from flask import Blueprint, request, jsonify, render_template
from app.models.ollama_client import OllamaClient
from app.models.lexical_service import LexicalService
from app.models.syntactic_service import SyntacticService
from app.models.semantic_service import SemanticService

compiler_bp = Blueprint('compiler', __name__)

@compiler_bp.route('/')
def index():
    """Renders the main dashboard view."""
    return render_template('index.html')

@compiler_bp.route('/analyze', methods=['POST'])
def analyze():
    """
    Recibe la receta en formato JSON, ejecuta las tres fases del compilador
    (Léxico, Sintáctico y Semántico) y genera el AST.
    """
    if not request.is_json:
        # Intentar leer desde formulario si no es JSON (para compatibilidad de formularios tradicionales)
        source = request.form.get("source", "").strip()
    else:
        data = request.get_json()
        source = data.get("source", "").strip()

    if not source:
        return jsonify({"error": "Debe proporcionar una receta en el campo 'source'."}), 400

    try:
        # Inicializar el cliente LLM y servicios
        llm = OllamaClient()
        lexer = LexicalService(llm)
        
        # 1. Fase 1: Análisis Léxico Concurrente
        tokens = lexer.analyze(source)
        
        # 2. Fase 2: Análisis Sintáctico (Dual: Programático + LLM)
        parser = SyntacticService(llm, tokens)
        syntax_res = parser.validate()
        
        # Generar el árbol AST (incluso si la sintaxis es inválida, intentamos generar una estructura parcial)
        ast = parser.build_ast()
        
        # 3. Fase 3: Análisis Semántico en Java
        semantic_res = {"valid": True, "errors": [], "warnings": [], "ingredients": []}
        if syntax_res["valid"]:
            # Solo ejecutamos el analizador semántico si la sintaxis es correcta
            semantic_service = SemanticService()
            semantic_res = semantic_service.analyze(tokens)
        else:
            # Si hay error sintáctico, la semántica no puede validarse
            semantic_res["valid"] = False
            semantic_res["errors"] = ["No se puede realizar el análisis semántico debido a errores de sintaxis."]

        # Retornar todas las fases para ser consumidas por el frontend
        return jsonify({
            "entrada": source,
            "tokens": tokens,
            "sintaxis": syntax_res,
            "semantica": semantic_res,
            "ast": ast
        })

    except Exception as e:
        return jsonify({
            "error": f"Error interno en la compilación: {str(e)}"
        }), 500
