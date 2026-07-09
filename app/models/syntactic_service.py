import json


class SyntacticService:

    GRAMMAR = """
<receta> ::= <instruccion> { CONECTOR_Y <instruccion> }
<instruccion> ::= <agregar> | <mezclar>
<agregar> ::= INSTRUCCION_INCORPORAR ( CANTIDAD | NUMERO CANTIDAD ) { UNKNOWN }
<mezclar> ::= INSTRUCCION_MEZCLAR NUMERO { UNKNOWN }
"""

    RULES = [
        "La receta debe comenzar con una instruccion (agregar, mezclar, batir, licuar, etc.)",
        "INSTRUCCION_INCORPORAR debe ir seguido de una cantidad (tazas, gramos, porciones, etc.)",
        "INSTRUCCION_MEZCLAR debe ir seguido inmediatamente de NUMERO",
        "CONECTOR_Y separa dos instrucciones y debe ir seguido de una instruccion",
        "No puede haber dos CONECTOR_Y consecutivos",
        "La secuencia no puede comenzar con CONECTOR_Y",
        "La secuencia no puede terminar con CONECTOR_Y",
    ]

    INSTRUCCIONES = {"INSTRUCCION_INCORPORAR", "INSTRUCCION_MEZCLAR"}

    def __init__(self, llm, tokens: list) -> None:
        self.llm = llm
        self.tokens = tokens

    def _check_rules(self) -> dict:
        if not self.tokens:
            return {"valid": False, "error": "No hay tokens para analizar"}

        # --- Regla 1: La receta debe comenzar con una instruccion valida ---
        if self.tokens[0]["type"] not in self.INSTRUCCIONES:
            return {
                "valid": False,
                "error": (
                    "La receta debe comenzar con una accion valida "
                    "(ejemplo: 'agregar una taza de harina' o "
                    "'mezclar por 5 minutos'), "
                    f"pero comienza con '{self.tokens[0]['value']}'."
                )
            }

        for i, token in enumerate(self.tokens):
            ttype = token["type"]
            tvalue = token["value"]

            # --- Regla 2: INSTRUCCION_INCORPORAR -> CANTIDAD | NUMERO CANTIDAD ---
            if ttype == "INSTRUCCION_INCORPORAR":
                if i + 1 >= len(self.tokens):
                    return {
                        "valid": False,
                        "error": (
                            f"Despues de '{tvalue}' debe ir una cantidad "
                            f"(ejemplo: '{tvalue} una taza de harina' "
                            f"o '{tvalue} 100 gr de azucar'), "
                            f"pero la receta termina ahi."
                        )
                    }

                next_type = self.tokens[i + 1]["type"]

                # Pattern A: INSTRUCCION_INCORPORAR -> CANTIDAD
                if "CANTIDAD" in next_type:
                    pass  # valido

                # Pattern B: INSTRUCCION_INCORPORAR -> NUMERO -> CANTIDAD
                elif next_type == "NUMERO":
                    if i + 2 >= len(self.tokens) or "CANTIDAD" not in self.tokens[i + 2]["type"]:
                        return {
                            "valid": False,
                            "error": (
                                f"Despues de '{tvalue} {self.tokens[i + 1]['value']}' "
                                f"debe ir una unidad de medida "
                                f"(ejemplo: '{tvalue} 100 gr de azucar'), "
                                f"pero se encontro "
                                f"'{self.tokens[i + 2]['value'] if i + 2 < len(self.tokens) else 'fin de la receta'}'."
                            )
                        }

                # Error: no es CANTIDAD ni NUMERO
                else:
                    return {
                        "valid": False,
                        "error": (
                            f"Despues de '{tvalue}' debe ir una cantidad "
                            f"(ejemplo: '{tvalue} una taza de harina' "
                            f"o '{tvalue} 100 gr de azucar'), "
                            f"pero se encontro '{self.tokens[i + 1]['value']}'."
                        )
                    }

            # --- Regla 3: INSTRUCCION_MEZCLAR -> NUMERO ---
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

            # --- Regla 4: CONECTOR_Y debe ir seguido de una instruccion ---
            if ttype == "CONECTOR_Y":
                if i + 1 >= len(self.tokens):
                    return {
                        "valid": False,
                        "error": (
                            "La receta no puede terminar con la palabra 'y'."
                        )
                    }
                if self.tokens[i + 1]["type"] not in self.INSTRUCCIONES:
                    return {
                        "valid": False,
                        "error": (
                            f"Despues de 'y' debe ir una accion valida "
                            f"(ejemplo: '... y agregar ...' o '... y mezclar ...'), "
                            f"pero se encontro '{self.tokens[i + 1]['value']}'."
                        )
                    }

            # --- Regla 5: No dos CONECTOR_Y consecutivos ---
            if ttype == "CONECTOR_Y":
                if i + 1 < len(self.tokens) and self.tokens[i + 1]["type"] == "CONECTOR_Y":
                    return {
                        "valid": False,
                        "error": (
                            "La palabra 'y' no puede repetirse dos veces seguidas."
                        )
                    }

        return {"valid": True, "error": None}

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

    def validate(self) -> dict:
        if not self.tokens:
            return {"valid": False, "error": "No hay tokens para analizar"}

        hard_result = self._check_rules()

        # Se hace la llamada al LLM en segundo plano como se solicita
        try:
            prompt = self._build_prompt()
            response = self.llm.generate(prompt)
            llm_result = json.loads(response)
        except Exception:
            llm_result = None

        if hard_result["valid"]:
            if llm_result and not llm_result.get("valid", True):
                print(
                    "  [SINTACTICO] LLM reporto falso positivo (ignorado): "
                    + str(llm_result.get("error"))
                )
        else:
            if llm_result and llm_result.get("valid", False):
                print(
                    "  [SINTACTICO] LLM no detecto el error "
                    "(corregido por validacion programatica)"
                )

        return hard_result

    def build_ast(self) -> dict:
        """
        Genera el árbol de sintaxis abstracta (AST) a partir de los tokens.
        Representa de forma estructurada las instrucciones de la receta.
        """
        if not self.tokens:
            return None

        instructions_tokens = []
        current_inst = []
        
        for t in self.tokens:
            if t["type"] == "CONECTOR_Y":
                if current_inst:
                    instructions_tokens.append(current_inst)
                current_inst = []
            else:
                current_inst.append(t)
        if current_inst:
            instructions_tokens.append(current_inst)

        recipe_nodes = []
        for inst_toks in instructions_tokens:
            if not inst_toks:
                continue

            first_token = inst_toks[0]
            if first_token["type"] == "INSTRUCCION_INCORPORAR":
                action = first_token["value"]
                quantity_tokens = []
                idx = 1
                
                # Buscar número y cantidad
                if idx < len(inst_toks) and inst_toks[idx]["type"] == "NUMERO":
                    quantity_tokens.append(inst_toks[idx]["value"])
                    idx += 1
                if idx < len(inst_toks) and inst_toks[idx]["type"] in ("CANTIDAD", "CANTIDAD_TAZAS"):
                    quantity_tokens.append(inst_toks[idx]["value"])
                    idx += 1
                
                quantity = " ".join(quantity_tokens)
                
                # El resto de tokens desconocidos (UNKNOWN) corresponden al ingrediente
                ingredient_tokens = []
                while idx < len(inst_toks):
                    if inst_toks[idx]["type"] == "UNKNOWN":
                        ingredient_tokens.append(inst_toks[idx]["value"])
                    idx += 1
                ingredient = " ".join(ingredient_tokens)

                recipe_nodes.append({
                    "type": "InstruccionAgregar",
                    "label": "Agregar Ingrediente",
                    "action": action,
                    "quantity": quantity if quantity else "(Porción estándar)",
                    "ingredient": ingredient if ingredient else "(No especificado)"
                })

            elif first_token["type"] == "INSTRUCCION_MEZCLAR":
                action = first_token["value"]
                duration = ""
                idx = 1
                
                if idx < len(inst_toks) and inst_toks[idx]["type"] == "NUMERO":
                    duration = inst_toks[idx]["value"]
                    idx += 1

                detail_tokens = []
                while idx < len(inst_toks):
                    if inst_toks[idx]["type"] == "UNKNOWN":
                        detail_tokens.append(inst_toks[idx]["value"])
                    idx += 1
                detail = " ".join(detail_tokens)

                recipe_nodes.append({
                    "type": "InstruccionMezclar",
                    "label": "Mezclar",
                    "action": action,
                    "duration": duration if duration else "(No especificada)",
                    "detail": detail if detail else "minutos"
                })
            else:
                recipe_nodes.append({
                    "type": "UnknownInstruction",
                    "label": "Instrucción Desconocida",
                    "value": " ".join(t["value"] for t in inst_toks)
                })

        return {
            "type": "Receta",
            "label": "Receta de Cocina",
            "children": recipe_nodes
        }
