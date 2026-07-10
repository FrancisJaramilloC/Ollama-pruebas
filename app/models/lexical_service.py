"""
Servicio encargado del análisis léxico de la receta.
Implementa un enfoque híbrido/concurrente:
1. Un Autómata Finito Determinista (AFD) basado en expresiones regulares para tokens "duros" (números, conectores).
2. Llamadas en paralelo a un LLM (Ollama) usando ThreadPoolExecutor para clasificar fragmentos no reconocidos ("soft tokens").
3. Una fase de validación y unificación para reconstruir la secuencia ordenada de tokens con su origen (AFD o LLM).
"""
import concurrent.futures
import json
import re
import threading
import time


class LexicalService:
    """
    Clase que realiza el análisis léxico híbrido de la receta culinaria.
    """

    # Expresiones regulares para los tokens que pueden ser identificados de manera determinista (AFD)
    TOKEN_PATTERNS = [
        ("NUMERO",    r"\d+"),
        ("CONECTOR_Y", r"\by\b"),
        ("SPACE",     r"\s+"),
        ("UNKNOWN",   r"\S+"),
    ]

    def __init__(self, llm):
        """
        Inicializa el analizador léxico asociando el cliente de LLM.

        :param llm: Instancia de OllamaClient para resolver tokens de lenguaje natural.
        """
        self.llm = llm

    def _build_prompt(self, block_text: str) -> str:
        """
        Construye el prompt estructurado para solicitar la clasificación de tokens al LLM.
        """
        return f"""
Eres un clasificador lexico especializado en recetas de cocina.
Analiza a detalle el siguiente fragmento de texto y asigna tokens a las palabras o frases que reconozcas:

Fragmento: "{block_text}"

Tokens disponibles:
- INSTRUCCION_INCORPORAR: verbos que indican agregar o incorporar (ej: "agregar", "anadir", "añadir", "poner", "incorporar", "adicionar", "echar", "verter", "colocar", "agrega", "agregue", "anade", "añade", "integra", "integrar", "integrando", "suma", "sumar", "introduce", "introducir", "vierte", "vertiendo", "espolvorea", "espolvorear", "rocía", "rociar", "vaciar", "vacía", "combina", "combinar")
- CANTIDAD: palabras o frases que indican únicamente una unidad de medida. Ejemplos válidos: "una cucharada de", "un par de tazas de", "dos cucharaditas de", "500 gramos de", "100 ml de", "una pizca de". IMPORTANTE: NO debes incluir el nombre del ingrediente dentro del token CANTIDAD. Por ejemplo, en la frase "una cucharada de harina", debes clasificar únicamente "una cucharada de" como CANTIDAD, de modo que "harina" quede sin clasificar (UNKNOWN) y pueda ser identificada como el ingrediente.
- INSTRUCCION_MEZCLAR: instrucciones de mezclado, cocción o preparación física. Ejemplos: "mezclar", "batir", "revolver", "remover", "agitar", "mezcle", "bata", "revuelva", "mezcla", "bate", "licuar", "licue", "hornear", "hornee", "reposar", "cocinar", "cocine", "hervir", "hierva", "asar", "ase", "dorar", "dore", "saltear", "saltee", "refrigerar", "refrigerar por", "saltear por", "freir por", "amasar", "amasar por", "licuar por", "batir durante", "hornear durante", "reposar por", "enfriar", "congelar", "derretir", "fundir", "colar", "tamizar", "licuando", "batiendo", "mezclando".

Instrucciones:
1. Identifica dentro del fragmento las palabras o frases que coincidan con los tokens.
2. Asigna UNICAMENTE los tokens listados.
3. Si hay multiples clasificaciones, incluyelas todas.
4. Omite texto que no coincida con ningun token, siempre y cuando no interfiera con el análisis.

Responde UNICAMENTE con un JSON plano donde cada clave sea el texto clasificado y cada valor sea el token.

Ejemplo: {{"agregar": "INSTRUCCION_INCORPORAR", "un par de tazas de": "CANTIDAD"}}

No uses markdown.
No agregues comentarios ni texto adicional. 
Utiliza un lenguaje claro, sencillo y facil de entender. """

    @staticmethod
    def _validate_classifications(
        classifications: dict, block_text: str
    ) -> dict:
        """
        Filtra y valida las clasificaciones recibidas del LLM para evitar alucinaciones,
        errores de concordancia o tokens inválidos.
        """
        KNOWN_INSTRUCCION_INCORPORAR = {
            "agregar", "anadir", "añadir", "poner", "incorporar",
            "adicionar", "echar", "verter", "colocar", "agrega",
            "agregue", "anade", "añade", "integra", "integrar",
            "integrando", "suma", "sumar", "introduce", "introducir",
            "vierte", "vertiendo", "espolvorea", "espolvorear",
            "rocía", "rociar", "vaciar", "vacía", "combina", "combinar"
        }
        KNOWN_INSTRUCCION_MEZCLAR = {
            "mezclar", "batir", "revolver", "remover", "agitar",
            "mezcle", "bata", "revuelva", "mezcla", "bate",
            "licuar", "licue", "hornear", "hornee", "reposar",
            "cocinar", "cocine", "hervir", "hierva", "asar",
            "ase", "dorar", "dore", "saltear", "saltee",
            "refrigerar", "freir", "amasar", "enfriar", "congelar",
            "derretir", "fundir", "colar", "tamizar", "licuando",
            "batiendo", "mezclando"
        }
        CONCORDANCIA_ERRONEA = [
            "un tazas", "un taza", "una tazas", "el tazas",
            "la tazas", "los taza", "las taza"
        ]

        valid = {}
        for fragment, token_type in classifications.items():
            fragment_lower = fragment.strip().lower()

            # Validar que los tokens tipo CANTIDAD contengan palabras clave obligatorias y concordancia de número/género
            if token_type == "CANTIDAD":
                cantidad_keywords = [
                    "tazas medidoras", "taza medidora", "porciones individuales", "taza", "tazas", "porcion", "porciones",
                    "gramos", "gr", "cucharada", "cucharadas", "cucharadita", "cucharaditas",
                    "mililitros", "ml", "litros", "lt", "l", "kilogramos", "kg", "kilo", "kilos",
                    "pieza", "piezas", "pizca", "pizcas", "puño", "puños", "scoop", "scoops",
                    "chorro", "chorritos", "grs"
                ]
                # Ordenar por longitud descendente para dar prioridad a frases más largas en la regex
                cantidad_keywords.sort(key=len, reverse=True)
                pattern = r"\b(" + "|".join(re.escape(k) for k in cantidad_keywords) + r")\b(?:\s+(?:de\s+(?:la|las|lo|los)\b|de\b))?"
                match = re.search(pattern, fragment_lower)
                if match:
                    if any(error in fragment_lower for error in CONCORDANCIA_ERRONEA):
                        continue
                    # Ajustar el fragmento de cantidad para excluir el nombre del ingrediente si se incluyó por error
                    clean_fragment = fragment[:match.end()].strip()
                    valid[clean_fragment] = token_type

            # Validar que INSTRUCCION_INCORPORAR sea exactamente un verbo conocido.
            # Si el LLM agrupó de más (ej: "agregar una cucharada de"), extraemos solo la primera palabra (el verbo)
            elif token_type == "INSTRUCCION_INCORPORAR":
                if fragment_lower in KNOWN_INSTRUCCION_INCORPORAR:
                    valid[fragment] = token_type
                else:
                    first_word = fragment_lower.split()[0]
                    if first_word in KNOWN_INSTRUCCION_INCORPORAR:
                        valid[first_word] = token_type

            # Validar que INSTRUCCION_MEZCLAR comience con un verbo de mezclado conocido
            elif token_type == "INSTRUCCION_MEZCLAR":
                if fragment_lower in KNOWN_INSTRUCCION_MEZCLAR:
                    valid[fragment] = token_type
                else:
                    words = fragment_lower.split()
                    if words[0] in KNOWN_INSTRUCCION_MEZCLAR:
                        # Si el fragmento es de 2 palabras (ej. "batir por"), lo consideramos válido completo
                        if len(words) == 2:
                            valid[fragment] = token_type
                        else:
                            # Si es más largo, nos quedamos con "verbo + preposición" (las primeras 2 palabras)
                            # siempre y cuando la segunda palabra no sea numérica ni de cantidad
                            clean_frag = " ".join(words[:2])
                            if not any(char.isdigit() for char in clean_frag) and words[1] not in ("minutos", "minuto", "segundos", "horas"):
                                valid[clean_frag] = token_type
                            else:
                                valid[words[0]] = token_type

            else:
                valid[fragment] = token_type

        return valid

    @staticmethod
    def _afd_task(hard_tokens: list) -> list:
        """
        Tarea ejecutada concurrentemente para estructurar los tokens identificados por el AFD.
        """
        thread_name = threading.current_thread().name
        start = time.time()

        result = [
            {"type": t["type"], "value": t["value"], "origin": "AFD"}
            for t in hard_tokens
        ]

        elapsed_ms = (time.time() - start) * 1000
        print(
            f"  [AFD] '{thread_name}' clasifico {len(result)} "
            f"tokens en {elapsed_ms:.3f}ms"
        )
        return result

    def _llm_task(self, block_text: str, idx: int) -> dict:
        """
        Tarea de hilo concurrente para consultar al LLM sobre la clasificación de un bloque UNKNOWN,
        procesar y validar el JSON de respuesta.
        """
        thread_name = threading.current_thread().name
        start = time.time()

        prompt = self._build_prompt(block_text)
        response = self.llm.generate(prompt)

        try:
            raw = json.loads(response)
            if isinstance(raw, dict):
                classifications = {
                    str(k): str(v) for k, v in raw.items()
                    if isinstance(k, str) and isinstance(v, str)
                }
            else:
                classifications = {}
        except (json.JSONDecodeError, ValueError):
            classifications = {}

        # Filtra las respuestas de acuerdo con las reglas y listas de palabras conocidas
        validated = self._validate_classifications(classifications, block_text)

        elapsed_ms = (time.time() - start) * 1000
        print(
            f"  [LLM] '{thread_name}' clasifico bloque {idx} "
            f"('{block_text[:30]}...') en {elapsed_ms:.2f}ms"
        )
        return {
            "idx": idx,
            "text": block_text,
            "classifications": validated
        }

    def analyze(self, source: str) -> list:
        """
        Punto de entrada principal para el análisis léxico de la receta.
        Tokeniza inicialmente, agrupa los fragmentos no reconocidos (UNKNOWN),
        los clasifica mediante consultas concurrentes al LLM y unifica la salida final en orden original.

        :param source: El texto fuente de la receta.
        :return: Lista de tokens ordenados con tipo, valor y origen (AFD/LLM).
        """
        start_total = time.time()

        # 1. Tokenizacion inicial basada en las expresiones regulares (AFD)
        pattern = "|".join(
            f"(?P<{name}>{regex})"
            for name, regex in self.TOKEN_PATTERNS
        )

        raw_tokens = []
        for match in re.finditer(pattern, source):
            ttype = match.lastgroup
            tvalue = match.group()
            if ttype == "SPACE":
                # Se descartan los espacios del análisis léxico
                continue
            raw_tokens.append({"type": ttype, "value": tvalue})

        # 2. Separar los tokens "duros" de los bloques UNKNOWN que requieren el LLM
        hard_tokens = [t for t in raw_tokens if t["type"] != "UNKNOWN"]

        unknown_blocks = []
        current_block = None
        for t in raw_tokens:
            if t["type"] == "UNKNOWN":
                if current_block is None:
                    current_block = []
                    unknown_blocks.append(current_block)
                current_block.append(t)
            else:
                current_block = None

        # Reconstruir las cadenas de texto correspondientes a cada secuencia continua de tokens UNKNOWN
        blocks_text = [
            " ".join(t["value"] for t in block)
            for block in unknown_blocks
        ]

        # 3. Ejecucion concurrente de las tareas usando ThreadPoolExecutor
        num_llm_calls = len(blocks_text)
        max_workers = max(2, num_llm_calls + 1)

        results = {"hard": [], "soft": {}}

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="LLM-worker"
        ) as executor:

            # Lanza la estructuración de tokens del AFD en paralelo a las llamadas al LLM
            afd_future = executor.submit(self._afd_task, hard_tokens)

            llm_futures = {}
            for idx, btext in enumerate(blocks_text):
                fut = executor.submit(self._llm_task, btext, idx)
                llm_futures[fut] = idx

            # Recupera los resultados del AFD
            results["hard"] = afd_future.result()

            # Recupera los resultados del LLM conforme se vayan completando
            for future in concurrent.futures.as_completed(llm_futures):
                idx = llm_futures[future]
                results["soft"][idx] = future.result()

        # 4. Unificar y fusionar resultados del AFD y del LLM en el orden original
        final_tokens = []
        bidx = 0
        i = 0

        def _make_token(ttype, tvalue, origin):
            return {
                "type": str(ttype or "UNKNOWN"),
                "value": str(tvalue or ""),
                "origin": origin
            }

        # Reconstruir la lista de tokens respetando el índice del texto original
        while i < len(raw_tokens):
            if raw_tokens[i]["type"] != "UNKNOWN":
                final_tokens.append(_make_token(
                    raw_tokens[i]["type"],
                    raw_tokens[i]["value"],
                    "AFD"
                ))
                i += 1
            else:
                block_info = results["soft"].get(bidx)
                block_tokens = unknown_blocks[bidx]

                if block_info and block_info["classifications"]:
                    classifications = block_info["classifications"]
                    block_text = block_info["text"]

                    # Filtrar fragmentos clasificados válidos que existan en el texto del bloque
                    matching = {
                        frag: tok
                        for frag, tok in classifications.items()
                        if frag in block_text
                    }

                    if matching:
                        # Ordena los fragmentos según su posición de aparición en el bloque
                        sorted_frags = sorted(
                            matching.items(),
                            key=lambda x: block_text.index(x[0])
                        )
                        pos = 0
                        for fragment, tok_type in sorted_frags:
                            idx_f = block_text.find(fragment, pos)
                            if idx_f == -1:
                                continue
                            # Si hay texto previo no clasificado antes del fragmento, se marca como UNKNOWN
                            if idx_f > pos:
                                remaining = block_text[pos:idx_f].strip()
                                if remaining:
                                    final_tokens.append(_make_token(
                                        "UNKNOWN", remaining, "LLM"
                                    ))
                            # Agregar el token clasificado por el LLM
                            final_tokens.append(_make_token(
                                tok_type, fragment, "LLM"
                              ))
                            pos = idx_f + len(fragment)
                        # Agregar cualquier texto restante no clasificado al final del bloque como UNKNOWN
                        remaining = block_text[pos:].strip()
                        if remaining:
                            final_tokens.append(_make_token(
                                "UNKNOWN", remaining, "LLM"
                            ))
                    else:
                        # Si no hay coincidencias válidas, restauramos todo el bloque como tokens UNKNOWN individuales
                        for t in block_tokens:
                            final_tokens.append(_make_token(
                                "UNKNOWN", t["value"], "LLM"
                            ))
                else:
                    # En caso de que falle la clasificación del LLM, se mantiene como UNKNOWN
                    for t in block_tokens:
                        final_tokens.append(_make_token(
                            "UNKNOWN", t["value"], "LLM"
                        ))

                i += len(block_tokens)
                bidx += 1

        return final_tokens

