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
Eres un asistente experto en cocina y compiladores de recetas. Tu objetivo es explicarle al usuario de forma muy breve, clara y directa los errores de compilación que ocurrieron con su receta.

Receta ingresada por el usuario:
"{source}"

Errores técnicos detectados:
{errors_text}

Instrucciones para tu respuesta (CUMPLE ESTRICTAMENTE):
1. NO uses ningún tipo de emoji.
2. Sé extremadamente conciso y preciso. Explica el problema en un máximo de 2 o 3 oraciones cortas.
3. Traduce los términos técnicos a explicaciones cotidianas y sencillas.
4. Proporciona un único ejemplo corregido de receta que el compilador acepte sin problemas.
5. Usa formato Markdown limpio (por ejemplo, negritas o viñetas simples).

Respuesta:
"""
        try:
            explanation = self.llm.generate(prompt)
            return explanation.strip()
        except Exception as e:
            return f"No se pudo generar la interpretación de los errores: {str(e)}"
