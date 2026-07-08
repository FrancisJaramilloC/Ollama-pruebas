# Guía de Pruebas de Carga — Compilador de Recetas

## Arquitectura

```
Herramienta de Carga  ──►  NGINX :80   ──┬──►  Nodo Principal :8001
(ab / Locust / JMeter /      (round-robin) └──►  Nodo Réplica   :8002
 Insomnia Runner)
                                              Ambos usan Ollama :11434
```

| Contenedor | Puerto | Rol |
|---|---|---|
| **nodo-principal** | 8001 | Procesa recetas, replica a la réplica |
| **nodo-replica** | 8002 | Procesa recetas, recibe replicación |
| **balanceador** (NGINX) | 80 | Round-robin entre los 2 nodos |

Todas las requests van al **balanceador** (`:80`), que distribuye entre ambos nodos.

---

## 1. Requisitos

### Herramientas de carga

| Herramienta | Debian/Ubuntu | Arch Linux |
|---|---|---|
| **ab** (Apache Benchmark) | `sudo apt install apache2-utils -y` | `sudo pacman -S apache-tools` |
| **JMeter** | `sudo apt install jmeter -y` | `sudo pacman -S jmeter` |
| **Locust** | `pip install locust` | `pip install locust` |
| **Insomnia** | Descargar de https://insomnia.rest | `sudo pacman -S insomnia` o desde AUR |
| **curl** | `sudo apt install curl -y` | `sudo pacman -S curl` |

### Monitoreo

| Herramienta | Instalación | Para qué |
|---|---|---|
| **docker stats** | Viene con Docker | CPU/memoria de cada contenedor |
| **vmstat** | `sudo apt install procps` / `sudo pacman -S procps-ng` | CPU/memoria del sistema |
| **htop** | `sudo apt install htop` / `sudo pacman -S htop` | Monitoreo en tiempo real |

### Verificar que todo funciona

```bash
ss -tlnp | grep 11434          # Ollama debe mostrar *:11434
docker ps                       # Los 3 contenedores deben estar "Up"
curl -s http://localhost/       # Balanceador responde
curl -s http://localhost:8001/health  # Nodo principal responde
curl -s http://localhost:8002/health  # Nodo réplica responde
```

---

## 2. Datos de Prueba

El archivo `test_data.json` contiene 10 recetas. Cada request envía una al `POST /analyze`.

```json
[
  {"source": "incorporar 2 tazas de harina"},
  {"source": "mezclar 3 huevos con una taza de azucar"},
  {"source": "incorporar 1 cucharada de sal y mezclar 5 minutos"},
  {"source": "incorporar 500 gramos de harina y mezclar 10 minutos con una taza de leche"},
  {"source": "licuar 3 bananitas y mezclar 2 minutos"},
  {"source": "incorporar una pizca de sal y mezclar 2 minutos"},
  {"source": "asar 15 minutos a 180 grados"},
  {"source": "incorporar 2 tazas de azucar y 3 huevos"},
  {"source": "batir 4 claras a punto de nieve e incorporar 1 taza de azucar"},
  {"source": "hornear 30 minutos y dejar reposar 10 minutos"}
]
```

---

## 3. Monitoreo de Recursos

Usa el script `monitor.sh` que viene en el proyecto:

```bash
chmod +x monitor.sh
./monitor.sh nombre_de_la_prueba
```

Esto genera en `resultados/<nombre>/`:
- `docker_stats.csv` — CPU% y memoria de cada contenedor cada 2 segundos
- `vmstat.log` — CPU y memoria del sistema operativo
- `docker_stats_baseline.txt` — consumo sin carga (para comparar)

Ejecútalo **antes** de iniciar la prueba de carga y detenlo (Ctrl+C) cuando termine.

---

## 4. Pruebas de Carga

Cada request toma 30–90 segundos (el LLM tarda). Las pruebas usan baja concurrencia.

### 4.1 Apache Benchmark (ab)

`ab` envía requests concurrentes desde la terminal. Mide throughput y percentiles.

```bash
# Crear payload (ab solo acepta un body fijo)
echo '{"source": "incorporar 2 tazas de harina y mezclar 5 minutos"}' > /tmp/payload.json

# Ejecutar: 10 requests, 2 simultáneos
ab -n 10 -c 2 -p /tmp/payload.json -T application/json \
  http://localhost/analyze > resultados/ab_resultados.txt
```

| Flag | Significado |
|---|---|
| `-n` | Total de requests |
| `-c` | Concurrentes (2–5 recomendado) |
| `-p` | Archivo con el body POST |
| `-T` | Content-Type |

**Qué buscar en la salida:**
```
Requests per second:           X.XX [#/sec]
Time per request:              XXXX.XXX [ms] (mean)
Percentage of requests served within a certain time (ms):
  50%    XXXX    90%    XXXX    99%    XXXX
```

---

### 4.2 JMeter

Plan gráfico con múltiples hilos. El archivo `jmeter_test_plan.jmx` ya está listo.

```bash
# Headless (sin ventana)
jmeter -n -t jmeter_test_plan.jmx \
  -l resultados/jmeter_results.csv \
  -e -o resultados/jmeter_report/

# Con interfaz gráfica
jmeter -t jmeter_test_plan.jmx
```

**Para variar recetas por request** (en la GUI):
1. Crea `recetas.csv` con:
   ```
   source
   "incorporar 2 tazas de harina"
   "mezclar 3 huevos con una taza de azucar"
   ```
2. Agrega "CSV Data Set Config" → variable: `source`, archivo: `recetas.csv`
3. Cambia el body a: `{"source": "${source}"}`

**Resultados:** `jmeter_results.csv` incluye `elapsed` (ms por request), `responseCode` y `success`.

---

### 4.3 Locust

Herramienta Python con código simple. El `locustfile.py` ya está listo.

```bash
# Headless: 3 usuarios, 1 usuario/segundo, 60 segundos
locust -f locustfile.py --host=http://localhost --headless \
  -u 3 -r 1 -t 60s \
  --csv resultados/locust_results \
  --html resultados/locust_report.html

# Con web UI (abrir http://localhost:8089)
locust -f locustfile.py --host=http://localhost
```

| Flag | Qué hace |
|---|---|
| `-u 3` | 3 usuarios virtuales simultáneos |
| `-r 1` | 1 nuevo usuario por segundo |
| `-t 60s` | Duración de la prueba |
| `--csv` | Prefijo para archivos CSV de resultados |
| `--html` | Reporte HTML visual |

**Resultados:**
- `locust_results_stats.csv` — avg, min, max, percentiles por endpoint
- `locust_results_stats_history.csv` — evolución en el tiempo (cada segundo)
- `locust_report.html` — gráficos y tablas

---

### 4.4 Insomnia Runner

**1. Crear la colección**
- Abre Insomnia → Create → Request Collection → "Compilador Recetas"

**2. Agregar requests**
- Click derecho en la colección → New Request
- Método: `POST`, URL: `http://localhost/analyze`
- Body → JSON: `{"source": "incorporar 2 tazas de harina"}`
- Crea varias requests iguales con distintas recetas (puedes duplicar y cambiar el body)

**3. Health check (opcional)**
- Nueva request: `GET http://localhost/`

**4. Ejecutar Runner**
- `Ctrl+Shift+R` o View → Toggle Runner
- Selecciona la colección
- Configura: Delay: `1000ms`, Iterations: `3`, Fail on error: desmarcado
- Click "Start Run"

**5. Exportar resultados**
- En el Runner → ícono de exportar → guarda como `insomnia_results.json`

**Alternativa desde terminal (sin Insomnia):**

```bash
RECETAS=(
  "incorporar 2 tazas de harina"
  "mezclar 3 huevos con una taza de azucar"
  "incorporar 500 gramos de harina y mezclar 10 minutos"
  "licuar 3 bananitas y mezclar 2 minutos"
  "asar 15 minutos a 180 grados"
  "incorporar 2 tazas de azucar y 3 huevos"
  "batir 4 claras a punto de nieve e incorporar 1 taza de azucar"
  "hornear 30 minutos y dejar reposar 10 minutos"
  "incorporar una pizca de sal y mezclar 2 minutos"
  "incorporar 1 cucharada de sal y mezclar 5 minutos"
)

echo "receta,status,tiempo_ms" > resultados/insomnia_results.csv
for receta in "${RECETAS[@]}"; do
  INICIO=$(date +%s%N)
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost/analyze \
    -H "Content-Type: application/json" \
    -d "{\"source\":\"$receta\"}" --max-time 120)
  FIN=$(date +%s%N)
  TIEMPO=$(( (FIN - INICIO) / 1000000 ))
  echo "\"$receta\",$STATUS,$TIEMPO" >> resultados/insomnia_results.csv
  echo "[$STATUS] $TIEMPO ms - $receta"
done
```

---

## 5. Script Automático

`run_all_tests.sh` ejecuta ab + Locust + JMeter secuencialmente:

```bash
chmod +x run_all_tests.sh
./run_all_tests.sh
```

Crea `resultados/<fecha>/` con los archivos de cada herramienta y un resumen.

---

## 6. Formato de Reporte

Completa estas tablas con los resultados de cada herramienta:

### Métricas por herramienta

| Métrica | ab | Locust | JMeter | Insomnia |
|---|---|---|---|---|
| Tiempo promedio (ms) | | | | |
| Tiempo mínimo (ms) | | | | |
| Tiempo máximo (ms) | | | | |
| P50 (ms) | | | | |
| P90 (ms) | | | | |
| P99 (ms) | | | | |
| Requests/segundo | | | | |
| % errores | | | | |

### Consumo de recursos

| Contenedor | CPU avg (%) | CPU max (%) | Memoria avg | Memoria max |
|---|---|---|---|---|
| nodo-principal | | | | |
| nodo-replica | | | | |
| balanceador | | | | |
| **Host total** | | | | |

---

## 7. Solución de Problemas

| Problema | Revisar |
|---|---|
| **Balanceador no responde** | `docker compose logs balanceador` · `ss -tlnp \| grep 80` |
| **Ollama no accesible** | `ss -tlnp \| grep 11434` → debe mostrar `*:11434` (no `127.0.0.1`). Si está mal: `pkill ollama && OLLAMA_HOST=0.0.0.0 nohup ollama serve &` |
| **Request se cuelga** | `docker compose logs nodo-principal --tail 20` · Probar con `curl --max-time 90` |
| **Réplica sin datos** | `curl -X POST http://localhost:8002/internal/sync` · Verificar: `curl -s http://localhost:8001/internal/recipes` vs `curl -s http://localhost:8002/internal/recipes` |

---

## 8. Referencia de Endpoints

| Método | Endpoint | Para qué |
|---|---|---|
| `GET` | `/` | Health check |
| `POST` | `/analyze` | **Analizar una receta** (envía `{"source":"..."}`) |
| `GET` | `/internal/recipes` | Listar recetas guardadas (interno) |
| `POST` | `/internal/recipes` | Recibir receta replicada (interno) |
| `POST` | `/internal/sync` | Forzar sincronización réplica (interno) |

---

## 9. Limpieza

```bash
docker compose down
docker volume rm ollama-pruebas_recipe-data
ss -tlnp | grep -E "8001|8002|80|11434"
```
