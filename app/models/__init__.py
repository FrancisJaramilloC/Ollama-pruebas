"""
Paquete que contiene los servicios y clientes que forman la capa de modelo (Model) en el patrón MVC.
Expone los componentes léxico, sintáctico, semántico y de comunicación con la API LLM.
"""
from app.models.ollama_client import OllamaClient
from app.models.lexical_service import LexicalService
from app.models.syntactic_service import SyntacticService
from app.models.semantic_service import SemanticService
from app.models.error_interpreter_service import ErrorInterpreterService

