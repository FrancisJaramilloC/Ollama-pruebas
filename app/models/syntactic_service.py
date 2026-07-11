"""
Servicio encargado del análisis sintáctico de las recetas.
Implementa una validación sintáctica dual:
1. Una validación programática dura mediante reglas locales de tokens.
2. Una llamada opcional al LLM en segundo plano como control secundario y reporte de discrepancias.
Además, este servicio construye el Árbol de Sintaxis Abstracta (AST) que estructura
las instrucciones analizadas en nodos (Receta, InstruccionAgregar, InstruccionMezclar, etc.).
"""
import json


class SyntacticService:
    """
    Clase que valida que el orden de los tokens siga la gramática y reglas definidas para recetas culinarias,
    y construye el AST.
    """

    # Definición de la gramática BNF para validación teórica de recetas
    GRAMMAR = """
<receta> ::= <instruccion> { CONECTOR_Y <instruccion> }
<instruccion> ::= <agregar> | <mezclar>
<agregar> ::= INSTRUCCION_INCORPORAR ( CANTIDAD | NUMERO [ CANTIDAD | UNIDAD_MEDIDA ] ) { UNKNOWN }
<mezclar> ::= INSTRUCCION_MEZCLAR { UNKNOWN } NUMERO { UNKNOWN }
"""

    # Reglas lógicas aplicadas de forma programática por el analizador
    RULES = [
        "La receta debe comenzar con una instruccion (agregar, mezclar, batir, licuar, etc.)",
        "INSTRUCCION_INCORPORAR debe ir seguido de una cantidad (tazas, gramos, porciones, etc.)",
        "INSTRUCCION_MEZCLAR debe contener un tiempo de mezclado/coccion indicado por un NUMERO",
        "CONECTOR_Y separa dos instrucciones y debe ir seguido de una instruccion",
        "No puede haber dos CONECTOR_Y consecutivos",
        "La secuencia no puede comenzar con CONECTOR_Y",
        "La secuencia no puede terminar con CONECTOR_Y",
    ]

    INSTRUCCIONES = {"INSTRUCCION_INCORPORAR", "INSTRUCCION_MEZCLAR"}

    def __init__(self, llm=None, tokens: list = None) -> None:
        """
        Inicializa el analizador sintáctico.

        :param llm: Cliente de Ollama (opcional, ya no se requiere).
        :param tokens: Lista de tokens generados en el análisis léxico.
        """
        if isinstance(llm, list):
            self.tokens = llm
            self.llm = None
        else:
            self.llm = llm
            self.tokens = tokens

    def _check_rules(self) -> dict:
        """
        Valida programáticamente las reglas sintácticas recorriendo los tokens secuencialmente.

        :return: Diccionario con el estado de validez y mensaje de error si existiese.
        """
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

                # Patrón A: INSTRUCCION_INCORPORAR -> CANTIDAD (ej: agregar una taza)
                if next_type == "CANTIDAD":
                    pass  # Válido

                # Patrón B: INSTRUCCION_INCORPORAR -> NUMERO -> CANTIDAD o UNIDAD_MEDIDA o UNKNOWN (ej: agregar 100 gramos o agregar 2 huevos)
                elif next_type == "NUMERO":
                    if i + 2 >= len(self.tokens) or self.tokens[i + 2]["type"] not in ("CANTIDAD", "UNIDAD_MEDIDA", "UNKNOWN"):
                        return {
                            "valid": False,
                            "error": (
                                f"Despues de '{tvalue} {self.tokens[i + 1]['value']}' "
                                f"debe ir una unidad de medida o ingrediente "
                                f"(ejemplo: '{tvalue} 100 gr de azucar' o '{tvalue} 2 huevos'), "
                                f"pero se encontro "
                                f"'{self.tokens[i + 2]['value'] if i + 2 < len(self.tokens) else 'fin de la receta'}'."
                            )
                        }

                # Error: No sigue número ni unidad de medida válida
                else:
                    return {
                        "valid": False,
                        "error": (
                            f"Despues de '{tvalue}' debe ir una cantidad valida "
                            f"(ejemplo: '{tvalue} una taza de harina' "
                            f"o '{tvalue} 100 gr de azucar'), "
                            f"pero se encontro '{self.tokens[i + 1]['value']}'."
                        )
                    }

            # --- Regla 3: INSTRUCCION_MEZCLAR -> NUMERO ---
            if ttype == "INSTRUCCION_MEZCLAR":
                found_number = False
                for j in range(i + 1, len(self.tokens)):
                    next_tok = self.tokens[j]
                    next_type = next_tok["type"]
                    if next_type == "NUMERO":
                        found_number = True
                        break
                    elif next_type in ("CONECTOR_Y", "INSTRUCCION_MEZCLAR", "INSTRUCCION_INCORPORAR"):
                        break
                
                if not found_number:
                    return {
                        "valid": False,
                        "error": (
                            f"Despues de '{tvalue}' debe ir un numero indicando "
                            f"el tiempo (ejemplo: '{tvalue} 5 minutos'), "
                            f"pero no se encontro ningun numero en esta instruccion."
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

    def validate(self) -> dict:
        """
        Valida la secuencia de tokens usando la lógica programática determinista.

        :return: El dict con la validez determinada por la lógica programática.
        """
        return self._check_rules()

    def build_ast(self) -> dict:
        """
        Genera el árbol de sintaxis abstracta (AST) a partir de los tokens de forma recursiva/estructurada.
        Representa de forma jerárquica y semántica las instrucciones de la receta.

        :return: Estructura dict del AST con la raíz del nodo Receta.
        """
        if not self.tokens:
            return None

        # Agrupar los tokens en instrucciones individuales separándolas por el token CONECTOR_Y
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
            # Caso 1: Estructurar una instrucción de Agregar/Incorporar
            if first_token["type"] == "INSTRUCCION_INCORPORAR":
                action = first_token["value"]
                quantity_tokens = []
                idx = 1
                
                # Extrae el número y la unidad de medida si existen (ej. 2 tazas)
                if idx < len(inst_toks) and inst_toks[idx]["type"] == "NUMERO":
                    quantity_tokens.append(inst_toks[idx]["value"])
                    idx += 1
                if idx < len(inst_toks) and inst_toks[idx]["type"] in ("CANTIDAD", "CANTIDAD_TAZAS", "UNIDAD_MEDIDA"):
                    quantity_tokens.append(inst_toks[idx]["value"])
                    idx += 1
                
                quantity = " ".join(quantity_tokens)
                
                # Todos los tokens UNKNOWN restantes se interpretan como el nombre del ingrediente
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

            # Caso 2: Estructurar una instrucción de Mezclar/Batir/Cocinar
            elif first_token["type"] == "INSTRUCCION_MEZCLAR":
                action = first_token["value"]
                duration = ""
                
                # Buscar el token NUMERO
                num_token_idx = -1
                for idx, t in enumerate(inst_toks):
                    if idx > 0 and t["type"] == "NUMERO":
                        duration = t["value"]
                        num_token_idx = idx
                        break

                # Todos los tokens restantes (excepto el de acción y el número) se acumulan como detalle/unidad de tiempo
                detail_tokens = []
                for idx, t in enumerate(inst_toks):
                    if idx == 0 or idx == num_token_idx:
                        continue
                    detail_tokens.append(t["value"])
                detail = " ".join(detail_tokens)

                recipe_nodes.append({
                    "type": "InstruccionMezclar",
                    "label": "Mezclar",
                    "action": action,
                    "duration": duration if duration else "(No especificada)",
                    "detail": detail if detail else "minutos"
                })
            else:
                # Fallback para instrucciones que no coinciden con las gramáticas esperadas
                recipe_nodes.append({
                    "type": "UnknownInstruction",
                    "label": "Instrucción Desconocida",
                    "value": " ".join(t["value"] for t in inst_toks)
                })

        # Retorna el nodo raíz del AST 'Receta' conteniendo la lista secuencial de instrucciones estructuradas
        return {
            "type": "Receta",
            "label": "Receta de Cocina",
            "children": recipe_nodes
        }

