"""
Controlador principal de la aplicación.
Define las rutas HTTP para renderizar la interfaz de usuario y procesar las peticiones
de análisis de recetas culinarias, canalizando el texto de entrada a través de los
diferentes analizadores del compilador (Léxico, Sintáctico, Semántico y AST).
"""
from flask import Blueprint, request, jsonify, render_template
from app.models.ollama_client import OllamaClient
from app.models.lexical_service import LexicalService
from app.models.syntactic_service import SyntacticService
from app.models.semantic_service import SemanticService
from app.models.error_interpreter_service import ErrorInterpreterService


# Define el Blueprint para agrupar las rutas relacionadas con el compilador.
compiler_bp = Blueprint('compiler', __name__)

@compiler_bp.route('/')
def index():
    """
    Renderiza la vista principal del dashboard (index.html).
    """
    return render_template('index.html')

@compiler_bp.route('/analyze', methods=['POST'])
def analyze():
    """
    Recibe la receta en formato JSON, ejecuta secuencialmente las tres fases del compilador
    (Léxico, Sintáctico y Semántico) y genera el árbol de sintaxis abstracta (AST).
    """
    # Si la petición no es JSON, intenta leerla como datos de formulario (para compatibilidad)
    if not request.is_json:
        source = request.form.get("source", "").strip()
    else:
        data = request.get_json()
        source = data.get("source", "").strip()

    # Valida que el texto de la receta no esté vacío
    if not source:
        return jsonify({"error": "Debe proporcionar una receta en el campo 'source'."}), 400

    try:
        # Pre-procesar la receta para admitir múltiples líneas y unirlas con " y " de forma limpia
        lines = [line.strip() for line in source.splitlines() if line.strip()]
        cleaned_lines = []
        for line in lines:
            # Elimina " y" al final o "y " al inicio de cada línea si existen para evitar conectores duplicados
            if line.endswith(" y"):
                line = line[:-2].strip()
            if line.startswith("y "):
                line = line[2:].strip()
            if line:
                cleaned_lines.append(line)
        
        processed_source = " y ".join(cleaned_lines)

        # Inicializar el cliente LLM (Ollama) y los servicios del compilador
        llm = OllamaClient()
        lexer = LexicalService(llm)
        
        # 1. Fase 1: Análisis Léxico Concurrente
        # Clasifica palabras del texto usando un AFD y llamadas paralelas al LLM
        tokens = lexer.analyze(processed_source)
        
        # 2. Fase 2: Análisis Sintáctico (Dual: Programático + LLM)
        # Valida que el orden de los tokens cumpla con las reglas gramaticales definidas
        parser = SyntacticService(llm, tokens)
        syntax_res = parser.validate()
        
        # Genera el árbol de sintaxis abstracta (AST) de la receta (incluso si hay errores parciales)
        ast = parser.build_ast()
        
        # 3. Fase 3: Análisis Semántico en Java
        semantic_res = {"valid": True, "errors": [], "warnings": [], "ingredients": []}
        if syntax_res["valid"]:
            # Solo ejecutamos el análisis semántico si la estructura sintáctica es válida
            semantic_service = SemanticService()
            semantic_res = semantic_service.analyze(tokens)
        else:
            # Si hay un error sintáctico, no es posible evaluar reglas de negocio (semántica)
            semantic_res["valid"] = False
            semantic_res["errors"] = ["No se puede realizar el análisis semántico debido a errores de sintaxis."]

        # 4. Fase de Interpretación de Errores por LLM
        interpreter = ErrorInterpreterService(llm)
        error_explicacion = interpreter.interpret_errors(source, syntax_res, semantic_res)

        # Retorna el resultado consolidado de todas las fases en formato JSON
        return jsonify({
            "entrada": source,
            "tokens": tokens,
            "sintaxis": syntax_res,
            "semantica": semantic_res,
            "ast": ast,
            "error_explicacion": error_explicacion
        })

    except Exception as e:
        # Maneja cualquier error inesperado durante el flujo de compilación
        return jsonify({
            "error": f"Error interno en la compilación: {str(e)}"
        }), 500

