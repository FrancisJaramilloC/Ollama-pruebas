import subprocess
import json
import os


class SemanticService:

    def __init__(self, java_classpath="java", class_name="SemanticAnalyzer"):
        self.java_classpath = java_classpath
        self.class_name = class_name

    def analyze(self, tokens: list) -> dict:
        """
        Envía los tokens en formato JSON al analizador semántico en Java
        a través de la entrada estándar y recibe el resultado JSON.
        """
        if not tokens:
            return {
                "valid": False,
                "errors": ["No se proporcionaron tokens para el análisis semántico."],
                "warnings": [],
                "ingredients": []
            }

        tokens_json = json.dumps(tokens)

        try:
            # Determinar la ruta absoluta al directorio java
            # app/models/semantic_service.py -> ../../java
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            cp_path = os.path.join(base_dir, self.java_classpath)

            # Ejecutar el proceso Java
            process = subprocess.Popen(
                ["java", "-cp", cp_path, self.class_name],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8"
            )

            stdout, stderr = process.communicate(input=tokens_json)

            if process.returncode != 0:
                return {
                    "valid": False,
                    "errors": [f"Error del proceso Java (ret: {process.returncode}): {stderr.strip()}"],
                    "warnings": [],
                    "ingredients": []
                }

            # Parsear el JSON devuelto por Java
            return json.loads(stdout)

        except Exception as e:
            return {
                "valid": False,
                "errors": [f"Error de comunicación con el analizador Java: {str(e)}"],
                "warnings": [],
                "ingredients": []
            }
