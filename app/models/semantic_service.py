"""
Servicio encargado del análisis semántico.
Se comunica con un analizador semántico externo escrito en Java (SemanticAnalyzer)
pasándole la lista de tokens mediante la entrada estándar y leyendo el resultado JSON procesado.
"""
import subprocess
import json
import os


class SemanticService:
    """
    Clase de servicio que envuelve la invocación al analizador semántico en Java.
    """

    def __init__(self, java_classpath="java", class_name="SemanticAnalyzer"):
        """
        Inicializa el servicio configurando el classpath de Java y la clase analizadora.

        :param java_classpath: Ruta relativa o absoluta al directorio de archivos .class de Java.
        :param class_name: Nombre de la clase principal compilada en Java.
        """
        self.java_classpath = java_classpath
        self.class_name = class_name

    def analyze(self, tokens: list) -> dict:
        """
        Envía los tokens en formato JSON al analizador semántico en Java
        a través de la entrada estándar (stdin) y recibe el resultado JSON (stdout).

        :param tokens: Lista de diccionarios que representan los tokens léxicos.
        :return: Diccionario con el resultado de la validación semántica (errores, advertencias, ingredientes).
        """
        if not tokens:
            return {
                "valid": False,
                "errors": ["No se proporcionaron tokens para el análisis semántico."],
                "warnings": [],
                "ingredients": []
            }

        # Serializa la lista de tokens a formato JSON
        tokens_json = json.dumps(tokens)

        try:
            # Determinar la ruta absoluta al directorio java
            # app/models/semantic_service.py -> ../../java
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            cp_path = os.path.join(base_dir, self.java_classpath)

            # Ejecutar el subproceso Java redirigiendo stdin, stdout y stderr
            process = subprocess.Popen(
                ["java", "-cp", cp_path, self.class_name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8"
            )

            # Escribe la cadena JSON de los tokens y espera el resultado de la ejecución
            stdout, stderr = process.communicate(input=tokens_json)

            # Si el proceso Java falló con un código de salida distinto de cero
            if process.returncode != 0:
                return {
                    "valid": False,
                    "errors": [f"Error del proceso Java (ret: {process.returncode}): {stderr.strip()}"],
                    "warnings": [],
                    "ingredients": []
                }

            # Parsear y retornar el JSON devuelto por Java en stdout
            return json.loads(stdout)

        except Exception as e:
            # Captura y reporta fallos en la ejecución de la JVM o errores de tuberías/pipes
            return {
                "valid": False,
                "errors": [f"Error de comunicación con el analizador Java: {str(e)}"],
                "warnings": [],
                "ingredients": []
            }

