"""
Servicio encargado de interpretar los errores de compilación para el usuario usando el LLM.
"""

class ErrorInterpreterService:
    """
    Clase de servicio que analiza los errores de las fases de compilación
    y le pide al LLM una explicación amigable con sugerencias de corrección.
    """

    def __init__(self, llm) -> None:
        """
        Inicializa el intérprete de errores con la instancia del cliente LLM.

        :param llm: Cliente de OllamaClient.
        """
        self.llm = llm

    def interpret_errors(self, source: str, syntax_res: dict, semantic_res: dict) -> str:
        """
        Genera una explicación amigable y con sugerencias de corrección sobre los errores
        sintácticos y semánticos encontrados.

        :param source: La receta original ingresada.
        :param syntax_res: Resultado de la fase sintáctica.
        :param semantic_res: Resultado de la fase semántica.
        :return: Explicación formateada en markdown.
        """
        # Si no hay errores, no se requiere interpretación
        if syntax_res.get("valid", True) and semantic_res.get("valid", True):
            return ""

        errors_list = []
        if not syntax_res.get("valid", True):
            errors_list.append(f"- Error Sintáctico: {syntax_res.get('error')}")
        if not semantic_res.get("valid", True):
            for err in semantic_res.get("errors", []):
                # Evitamos el error genérico si es por sintaxis previa
                if "No se puede realizar el análisis semántico debido a errores de sintaxis" in err:
                    continue
                errors_list.append(f"- Error Semántico: {err}")

        # Si tras filtrar no quedan errores significativos, no hay nada que explicar
        if not errors_list:
            if not syntax_res.get("valid", True):
                errors_list.append(f"- Error Sintáctico: {syntax_res.get('error')}")
            else:
                return ""

        errors_text = "\n".join(errors_list)

        prompt = f"""
Eres un asistente experto en cocina y compiladores de recetas. Tu objetivo es explicarle al usuario de forma clara, amigable y muy didáctica los errores de compilación (sintácticos o semánticos) que ocurrieron con su receta.

Receta ingresada por el usuario:
"{source}"

Errores técnicos detectados:
{errors_text}

Instrucciones para tu respuesta:
1. Explica de manera simple y constructiva por qué falló la receta, traduciendo el error técnico a lenguaje cotidiano.
2. Identifica el origen exacto del problema (ej. falta de ingredientes, mezclar antes de agregar, cantidades mal especificadas, etc.).
3. Proporciona un ejemplo corregido y válido de cómo debería escribirse la receta para que el compilador la acepte sin problemas.
4. Responde en español utilizando formato Markdown (negritas, viñetas, etc.). Mantén un tono amigable, claro y conciso.

Respuesta:
"""
        try:
            explanation = self.llm.generate(prompt)
            return explanation.strip()
        except Exception as e:
            return f"No se pudo generar la interpretación de los errores: {str(e)}"
