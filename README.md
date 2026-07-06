# Compilador de Recetas de Cocina (Algoritmos DSL)

Mini-compilador con ejecucion concurrente: AFD y LLM trabajan en paralelo mediante ThreadPoolExecutor.

## Requisitos

- Python 3.10+
- Ollama corriendo en `http://localhost:11434` con el modelo `llama3.2:3b`

## Instalacion

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Uso

Iniciar el servidor:

```bash
source .venv/bin/activate
python server.py
```

## Estructura

| Archivo | Proposito |
|---|---|
| `ollama_client.py` | Cliente HTTP para peticiones POST a `/api/generate` de Ollama |
| `lexical_service.py` | Analisis lexico concurrente: AFD + LLM via ThreadPoolExecutor |
| `syntactic_service.py` | Gramatica formal (BNF) + analisis sintactico via LLM |
| `server.py` | Servidor HTTP (un puerto: 8000) para probar desde Insomnia |

## Arquitectura concurrente (Fase 1 — Analisis lexico)

1. El scanner tokeniza la entrada con regex, separando tokens duros (NUMERO, CONECTOR_Y) de bloques UNKNOWN.
2. El AFD clasifica los tokens duros en el hilo principal.
3. Cada bloque UNKNOWN se envía al LLM en un hilo separado del ThreadPoolExecutor.
4. AFD y LLM se ejecutan en paralelo; el tiempo total es el maximo entre ambos, no la suma.
5. Los resultados se unifican preservando el orden original.

## Gramatica formal (Fase 2 — Analisis sintactico)

La gramatica del DSL de recetas esta definida en `syntactic_service.py` en notacion BNF:

```
<receta>       ::= <instruccion> { CONECTOR_Y <instruccion> }
<instruccion>  ::= <agregar> | <mezclar>
<agregar>      ::= INSTRUCCION_INCORPORAR CANTIDAD_TAZAS { UNKNOWN }
<mezclar>      ::= INSTRUCCION_MEZCLAR NUMERO { UNKNOWN }
```

## Reglas gramaticales

El LLM recibe estas reglas junto con los tokens y la gramatica, y determina si hay error:

- Toda instruccion debe comenzar con `INSTRUCCION_INCORPORAR` o `INSTRUCCION_MEZCLAR`
- `INSTRUCCION_INCORPORAR` debe ir seguido de `CANTIDAD_TAZAS`
- `INSTRUCCION_MEZCLAR` debe ir seguido de `NUMERO`
- Las instrucciones deben estar separadas por `CONECTOR_Y`
- No puede haber dos `CONECTOR_Y` consecutivos
- La secuencia no puede terminar con `CONECTOR_Y`

## Entrada de ejemplo

```
agregar un par de tazas de harina y mezclar por 5 minutos
```

## Peticion HTTP para Insomnia

Un solo puerto expuesto al usuario: `8000` (el servidor del compilador). Internamente llama a Ollama en `11434`.

Iniciar el servidor:

```bash
source .venv/bin/activate
python server.py
```

En Insomnia:

```
POST http://localhost:8000/analyze
Content-Type: application/json

{
  "source": "agregar un par de tazas de harina y mezclar por 5 minutos"
}
```

Respuesta esperada:

```json
{
  "entrada": "agregar un par de tazas de harina y mezclar por 5 minutos",
  "tokens": [
    {"type": "INSTRUCCION_INCORPORAR", "value": "agregar", "origin": "LLM"},
    {"type": "CANTIDAD_TAZAS", "value": "un par de tazas de", "origin": "LLM"},
    {"type": "UNKNOWN", "value": "harina", "origin": "LLM"},
    {"type": "CONECTOR_Y", "value": "y", "origin": "AFD"},
    {"type": "INSTRUCCION_MEZCLAR", "value": "mezclar por", "origin": "LLM"},
    {"type": "NUMERO", "value": "5", "origin": "AFD"},
    {"type": "UNKNOWN", "value": "minutos", "origin": "LLM"}
  ],
  "sintaxis": {"valid": true, "error": null}
}
```
