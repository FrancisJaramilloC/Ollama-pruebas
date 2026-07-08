# Compilador de Recetas de Cocina (Algoritmos DSL)

Mini-compilador con ejecucion concurrente: AFD y LLM trabajan en paralelo mediante ThreadPoolExecutor.

## Requisitos

- Python 3.10+
- Ollama corriendo en `http://localhost:11434` con el modelo `llama3.2:3b`
- Redis para la capa de cache compartida
- MariaDB primaria y MariaDB secundaria con replicacion activa

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
python -m src.server
```

Si usas Docker Compose, el stack levanta dos nodos de aplicacion, una BD primaria, una BD secundaria replicada, Redis como cache compartido y un balanceador Nginx expuesto en el puerto 80. Los nodos exponen `/health` para sus healthchecks.

## Pruebas manuales y de carga

Todos los archivos de prueba quedaron agrupados en [pruebas/](pruebas): guía de carga, JMeter, Locust, monitoreo y script automático.

## Estructura

```
src/
├── __init__.py
├── server.py              # Servidor HTTP (nodos en 8001/8002)
├── clients/
│   ├── __init__.py
│   └── ollama.py          # Cliente HTTP para Ollama
└── analyzers/
    ├── __init__.py
    ├── lexical.py          # Analisis lexico (AFD + LLM)
    └── syntactic.py        # Analisis sintactico (gramatica BNF + LLM)
```

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

## Arquitectura de datos

La persistencia ahora usa una topologia centralizada:

1. La aplicacion escribe en la BD primaria.
2. La BD secundaria recibe la replicacion desde la primaria.
3. Las lecturas usan la secundaria cuando esta disponible.
4. Redis actua como cache compartida para `get_all` y `get_by_id`, con write-through al guardar.

Esto reemplaza el esquema anterior de una BD por nodo.

## Peticion HTTP para Insomnia

El puerto expuesto al usuario es `80` a traves del balanceador Nginx. Los nodos de aplicacion corren en `8001` y `8002`, e internamente llaman a Ollama en `11434`.

Iniciar el servidor:

```bash
source .venv/bin/activate
python -m src.server
```

En Insomnia:

```
POST http://localhost/analyze
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
