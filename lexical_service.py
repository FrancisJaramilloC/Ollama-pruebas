import concurrent.futures
import json
import re
import threading
import time


class LexicalService:

    TOKEN_PATTERNS = [
        ("NUMERO",    r"\d+"),
        ("CONECTOR_Y", r"\by\b"),
        ("SPACE",     r"\s+"),
        ("UNKNOWN",   r"\S+"),
    ]

    def __init__(self, llm):
        self.llm = llm

    # ------------------------------------------------------------------
    # Prompt para el LLM (clasifica un unico bloque UNKNOWN)
    # ------------------------------------------------------------------
    def _build_prompt(self, block_text: str) -> str:
        return f"""
Eres un clasificador lexico especializado en recetas de cocina.
Analiza a detalle el siguiente fragmento de texto y asigna tokens a las palabras o frases que reconozcas:

Fragmento: "{block_text}"

Tokens disponibles:
- INSTRUCCION_INCORPORAR: verbos que indican agregar o incorporar (ej: "agregar", "anadir", "poner")
- CANTIDAD: SOLO cuando aparece explicitamente la palabra "taza", "tazas", "porcion", "porciones", "gramos" o "gr". Ejemplos validos: "una porcion de", "un par de tazas de", "dos tazas de", "500 gramos de", "100 gr de". NO clasifiques si no aparece la palabra.
- INSTRUCCION_MEZCLAR: instrucciones de mezclado con tiempo (ej: "mezclar por", "batir durante", "hornear durante", "licuar por", "reposar")

Instrucciones:
1. Identifica dentro del fragmento las palabras o frases que coincidan con los tokens.
2. Asigna UNICAMENTE los tokens listados.
3. Si hay multiples clasificaciones, inclu yelas todas.
4. Omite texto que no coincida con ningun token, siempre y cuando no interfiera con el análisis.

Responde UNICAMENTE con un JSON plano donde cada clave sea el texto clasificado y cada valor sea el token.

Ejemplo: {{"agregar": "INSTRUCCION_INCORPORAR", "un par de tazas de": "CANTIDAD"}}

No uses markdown.
No agregues comentarios ni texto adicional. 
Utiliza un lenguaje claro, sencillo y facil de entender. """

    # ------------------------------------------------------------------
    # Validacion de clasificaciones del LLM
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_classifications(
        classifications: dict, block_text: str
    ) -> dict:
        KNOWN_INSTRUCCION_INCORPORAR = {
            "agregar", "anadir", "añadir", "poner", "incorporar",
            "adicionar", "echar", "verter", "colocar", "agrega",
            "agregue", "anade", "añade"
        }
        KNOWN_INSTRUCCION_MEZCLAR = {
            "mezclar", "batir", "revolver", "remover", "agitar",
            "mezcle", "bata", "revuelva", "mezcla", "bate",
            "licuar", "licue", "hornear", "hornee", "reposar",
            "cocinar", "cocine", "hervir", "hierva", "asar",
            "ase", "dorar", "dore", "saltear", "saltee"
        }
        CONCORDANCIA_ERRONEA = [
            "un tazas", "un taza", "una tazas", "el tazas",
            "la tazas", "los taza", "las taza"
        ]

        valid = {}
        for fragment, token_type in classifications.items():
            fragment_lower = fragment.strip().lower()

            if token_type == "CANTIDAD":
                if any(keyword in fragment_lower for keyword in ["taza", "tazas", "porcion", "porciones", "gramos", "gr"]):
                    if any(error in fragment_lower for error in CONCORDANCIA_ERRONEA):
                        continue
                    valid[fragment] = token_type

            elif token_type == "INSTRUCCION_INCORPORAR":
                first_word = fragment_lower.split()[0]
                if first_word in KNOWN_INSTRUCCION_INCORPORAR:
                    valid[fragment] = token_type

            elif token_type == "INSTRUCCION_MEZCLAR":
                first_word = fragment_lower.split()[0]
                if first_word in KNOWN_INSTRUCCION_MEZCLAR:
                    valid[fragment] = token_type

            else:
                valid[fragment] = token_type

        return valid

    # ------------------------------------------------------------------
    # Tarea del AFD (clasifica tokens duros: NUMERO, CONECTOR_Y)
    # ------------------------------------------------------------------
    @staticmethod
    def _afd_task(hard_tokens: list) -> list:
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

    # ------------------------------------------------------------------
    # Tarea del LLM (clasifica un bloque UNKNOWN)
    # ------------------------------------------------------------------
    def _llm_task(self, block_text: str, idx: int) -> dict:
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

        validated = self._validate_classifications(classifications, block_text)

        elapsed_ms = (time.time() - start) * 1000
        print(
            f"  [LLM] '{thread_name}' clasifico bloque {idx} "
            f"('{block_text[:30]}...') en {elapsed_ms:.2f}ms"
        )
        if validated != classifications:
            print(
                f"    -> clasificaciones invalidas filtradas: "
                f"{ {k: classifications[k] for k in set(classifications) - set(validated)} }"
            )
        return {
            "idx": idx,
            "text": block_text,
            "classifications": validated
        }

    # ------------------------------------------------------------------
    # Metodo principal
    # ------------------------------------------------------------------
    def analyze(self, source: str) -> list:
        start_total = time.time()
        print(f"\n  {'='*55}")
        print(f"  FASE 1 — ANALISIS LEXICO CONCURRENTE")
        print(f"  {'='*55}")

        # ----------------------------------------------------------
        # 1. Tokenizacion inicial con el AFD (expresiones regulares)
        # ----------------------------------------------------------
        pattern = "|".join(
            f"(?P<{name}>{regex})"
            for name, regex in self.TOKEN_PATTERNS
        )

        raw_tokens = []
        for match in re.finditer(pattern, source):
            ttype = match.lastgroup
            tvalue = match.group()
            if ttype == "SPACE":
                continue
            raw_tokens.append({"type": ttype, "value": tvalue})

        # ----------------------------------------------------------
        # 2. Separar tokens duros (AFD) y agrupar bloques UNKNOWN
        # ----------------------------------------------------------
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

        blocks_text = [
            " ".join(t["value"] for t in block)
            for block in unknown_blocks
        ]

        print(f"\n  Tokens duros (AFD): {[t['value'] for t in hard_tokens]}")
        print(f"  Bloques UNKNOWN  : {blocks_text}")
        print()

        # ----------------------------------------------------------
        # 3. Ejecucion concurrente con ThreadPoolExecutor
        # ----------------------------------------------------------
        num_llm_calls = len(blocks_text)
        max_workers = max(2, num_llm_calls + 1)

        results = {"hard": [], "soft": {}}

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="LLM-worker"
        ) as executor:

            afd_future = executor.submit(self._afd_task, hard_tokens)

            llm_futures = {}
            for idx, btext in enumerate(blocks_text):
                fut = executor.submit(self._llm_task, btext, idx)
                llm_futures[fut] = idx

            results["hard"] = afd_future.result()

            for future in concurrent.futures.as_completed(llm_futures):
                idx = llm_futures[future]
                results["soft"][idx] = future.result()

        # ----------------------------------------------------------
        # 4. Unificar resultados preservando el orden original
        # ----------------------------------------------------------
        final_tokens = []
        bidx = 0
        i = 0

        def _make_token(ttype, tvalue, origin):
            return {
                "type": str(ttype or "UNKNOWN"),
                "value": str(tvalue or ""),
                "origin": origin
            }

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

                    matching = {
                        frag: tok
                        for frag, tok in classifications.items()
                        if frag in block_text
                    }

                    if matching:
                        sorted_frags = sorted(
                            matching.items(),
                            key=lambda x: block_text.index(x[0])
                        )
                        pos = 0
                        for fragment, tok_type in sorted_frags:
                            idx_f = block_text.find(fragment, pos)
                            if idx_f == -1:
                                continue
                            if idx_f > pos:
                                remaining = block_text[pos:idx_f].strip()
                                if remaining:
                                    final_tokens.append(_make_token(
                                        "UNKNOWN", remaining, "LLM"
                                    ))
                            final_tokens.append(_make_token(
                                tok_type, fragment, "LLM"
                            ))
                            pos = idx_f + len(fragment)
                        remaining = block_text[pos:].strip()
                        if remaining:
                            final_tokens.append(_make_token(
                                "UNKNOWN", remaining, "LLM"
                            ))
                    else:
                        for t in block_tokens:
                            final_tokens.append(_make_token(
                                "UNKNOWN", t["value"], "LLM"
                            ))
                else:
                    for t in block_tokens:
                        final_tokens.append(_make_token(
                            "UNKNOWN", t["value"], "LLM"
                        ))

                i += len(block_tokens)
                bidx += 1

        elapsed_total = (time.time() - start_total) * 1000
        print(
            f"\n  Tiempo total del analisis lexico: {elapsed_total:.2f}ms"
        )

        return final_tokens
