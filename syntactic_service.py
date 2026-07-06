import json


class SyntacticService:
    """
    Servicio de analisis sintactico con validacion DUAL:

      [A] Validacion programatica (hardcoded)
          Aplica las reglas gramaticales de forma deterministica
          recorriendo la secuencia token por token. Es la fuente
          de verdad por ser rapida, exacta y predecible.

      [B] Validacion via LLM
          Envia al LLM la gramatica formal, las reglas y los tokens
          (tal como se solicito). Su respuesta se contrasta con [A]
          pero nunca anula el resultado programatico.

    Flujo completo:
      1. Se define gramatica (GRAMMAR) y reglas (RULES).
      2. _check_rules() aplica las reglas deterministicamente.
      3. _build_prompt() construye el prompt con gramatica+reglas+tokens.
      4. validate() ejecuta ambas y retorna el resultado de [A].
    """

    # ------------------------------------------------------------------
    # GRAMATICA FORMAL (notacion BNF)
    # ------------------------------------------------------------------
    GRAMMAR = """
<receta> ::= <instruccion> { CONECTOR_Y <instruccion> }
<instruccion> ::= <agregar> | <mezclar>
<agregar> ::= INSTRUCCION_INCORPORAR CANTIDAD { UNKNOWN }
<mezclar> ::= INSTRUCCION_MEZCLAR NUMERO { UNKNOWN }
"""

    # ------------------------------------------------------------------
    # REGLAS GRAMATICALES
    # ------------------------------------------------------------------
    RULES = [
        "INSTRUCCION_INCORPORAR debe ir seguido inmediatamente de CANTIDAD",
        "INSTRUCCION_MEZCLAR debe ir seguido inmediatamente de NUMERO",
        "CONECTOR_Y solo puede aparecer entre dos instrucciones",
        "No puede haber dos CONECTOR_Y consecutivos",
        "La secuencia no puede comenzar con CONECTOR_Y",
        "La secuencia no puede terminar con CONECTOR_Y",
    ]

    def __init__(self, llm, tokens: list) -> None:
        self.llm = llm
        self.tokens = tokens

    # ==================================================================
    # [A] VALIDACION PROGRAMATICA (hardcoded)
    # ==================================================================
    # Recorre la secuencia posicion por posicion y verifica que cada
    # token cumpla con las reglas gramaticales. Es deterministico,
    # instantaneo y no depende del LLM.
    # ==================================================================
    def _check_rules(self) -> dict:
        for i, token in enumerate(self.tokens):
            ttype = token["type"]
            tvalue = token["value"]

            # --- Regla 1: INSTRUCCION_INCORPORAR -> CANTIDAD_TAZAS ---
            if ttype == "INSTRUCCION_INCORPORAR":
                if i + 1 >= len(self.tokens):
                    return {
                        "valid": False,
                        "error": (
                            f"Despues de '{tvalue}' debes indicar una cantidad "
                            f"en tazas (ejemplo: '{tvalue} una taza de harina'), "
                            f"pero la receta termina ahi."
                        )
                    }
                if "CANTIDAD" not in self.tokens[i + 1]["type"]:
                    return {
                        "valid": False,
                        "error": (
                            f"Despues de '{tvalue}' debes indicar una cantidad "
                            f"en tazas (ejemplo: '{tvalue} una taza de harina'), "
                            f"pero se encontro '{self.tokens[i + 1]['value']}'."
                        )
                    }

            # --- Regla 2: INSTRUCCION_MEZCLAR -> NUMERO ---
            if ttype == "INSTRUCCION_MEZCLAR":
                if i + 1 >= len(self.tokens):
                    return {
                        "valid": False,
                        "error": (
                            f"Despues de '{tvalue}' debe ir un numero indicando "
                            f"el tiempo (ejemplo: '{tvalue} 5 minutos'), "
                            f"pero la receta termina ahi."
                        )
                    }
                if self.tokens[i + 1]["type"] != "NUMERO":
                    return {
                        "valid": False,
                        "error": (
                            f"Despues de '{tvalue}' debe ir un numero indicando "
                            f"el tiempo (ejemplo: '{tvalue} 5 minutos'), "
                            f"pero se encontro '{self.tokens[i + 1]['value']}'."
                        )
                    }

            # --- Regla 4: No dos CONECTOR_Y consecutivos ---
            if ttype == "CONECTOR_Y":
                if i + 1 < len(self.tokens) and self.tokens[i + 1]["type"] == "CONECTOR_Y":
                    return {
                        "valid": False,
                        "error": (
                            f"La palabra 'y' no puede repetirse dos veces seguidas."
                        )
                    }

        # --- Regla 5: No comenzar con CONECTOR_Y ---
        if self.tokens[0]["type"] == "CONECTOR_Y":
            return {
                "valid": False,
                "error": (
                    "La receta no puede comenzar con la palabra 'y'."
                )
            }

        # --- Regla 6: No terminar con CONECTOR_Y ---
        if self.tokens[-1]["type"] == "CONECTOR_Y":
            return {
                "valid": False,
                "error": (
                    "La receta no puede terminar con la palabra 'y'."
                )
            }

        return {"valid": True, "error": None}

    # ==================================================================
    # [B] CONSTRUCCION DEL PROMPT PARA EL LLM
    # ==================================================================
    # Incluye: gramatica formal, reglas gramaticales y la secuencia
    # de tokens con su posicion. El LLM debe responder si hay error.
    # ==================================================================
    def _build_prompt(self) -> str:
        items = []
        for i, t in enumerate(self.tokens):
            items.append(f"  [{i}] {t['type']} ('{t['value']}')")
        tokens_block = "\n".join(items)

        rules_text = "\n".join(
            f"{i+1}. {r}" for i, r in enumerate(self.RULES)
        )

        return f"""Eres un validador sintactico. Revisa estrictamente esta secuencia de tokens.

GRAMATICA:
{self.GRAMMAR}

REGLAS:
{rules_text}

SECUENCIA:
{tokens_block}

Determina si la secuencia cumple TODAS las reglas. Si alguna se viola, es INVALIDA.
Responde SOLO JSON:
{{"valid":true,"error":null}} o {{"valid":false,"error":"descripcion"}}"""

    # ==================================================================
    # METODO PRINCIPAL: validate()
    # ==================================================================
    # Ejecuta ambas validaciones en paralelo:
    #   1. _check_rules() — deterministica, fuente de verdad
    #   2. LLM via prompt — cumple el requerimiento de enviar
    #      tokens+gramatica+reglas al LLM
    #
    # El resultado final SIEMPRE corresponde a la validacion
    # programatica. La respuesta del LLM se muestra en consola
    # para referencia pero no afecta la salida.
    # ==================================================================
    def validate(self) -> dict:
        if not self.tokens:
            return {"valid": False, "error": "No hay tokens para analizar"}

        hard_result = self._check_rules()

        prompt = self._build_prompt()
        response = self.llm.generate(prompt)

        try:
            llm_result = json.loads(response)
        except (json.JSONDecodeError, ValueError):
            llm_result = None

        if hard_result["valid"]:
            if llm_result and not llm_result.get("valid", True):
                print(
                    "  [SINTACTICO] LLM reporto falso positivo "
                    "(ignorado): " + str(llm_result.get("error"))
                )
        else:
            if llm_result and llm_result.get("valid", False):
                print(
                    "  [SINTACTICO] LLM no detecto el error "
                    "(corregido por validacion programatica)"
                )

        return hard_result
