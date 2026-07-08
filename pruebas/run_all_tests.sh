#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RESULTADOS="$REPO_ROOT/resultados/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTADOS"
echo "Resultados en: $RESULTADOS"

# ==========================================
# 1. Verificar servicios
# ==========================================
echo "=== Verificando servicios ==="
for svc in http://localhost/ http://localhost:8001/health http://localhost:8002/health; do
  if curl -sf "$svc" > /dev/null 2>&1; then
    echo "  OK: $svc"
  else
    echo "  ERROR: $svc no responde"
    exit 1
  fi
done

if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
  echo "  OK: Ollama :11434"
else
  echo "  ERROR: Ollama no responde"
  exit 1
fi

# ==========================================
# 2. Baseline (sin carga)
# ==========================================
echo ""
echo "=== Baseline (sin carga) ==="
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" \
  > "$RESULTADOS/baseline.txt"
cat "$RESULTADOS/baseline.txt"

# ==========================================
# 3. Apache Benchmark
# ==========================================
echo ""
echo "========================================"
echo "PRUEBA 1: Apache Benchmark"
echo "========================================"
echo '{"source": "incorporar 2 tazas de harina y mezclar 5 minutos"}' > /tmp/ab_payload.json

ab -n 10 -c 2 \
  -p /tmp/ab_payload.json \
  -T "application/json" \
  http://localhost/analyze \
  > "$RESULTADOS/ab_results.txt" 2>&1

echo "Resultados:"
grep -E "(Requests per second|Time per request|Failed requests|Transfer rate|Percentage of requests served)" "$RESULTADOS/ab_results.txt"

# ==========================================
# 4. Locust
# ==========================================
echo ""
echo "========================================"
echo "PRUEBA 2: Locust"
echo "========================================"

if python3 -c "import locust" 2>/dev/null; then
  locust -f "$SCRIPT_DIR/locustfile.py" \
    --host=http://localhost \
    --headless \
    -u 3 \
    -r 1 \
    -t 60s \
    --csv "$RESULTADOS/locust_results" \
    --html "$RESULTADOS/locust_report.html" \
    --logfile "$RESULTADOS/locust.log" \
    2>&1 | tee "$RESULTADOS/locust_output.txt"

  echo ""
  echo "Resumen Locust:"
  if [ -f "$RESULTADOS/locust_results_stats.csv" ]; then
    cat "$RESULTADOS/locust_results_stats.csv"
  fi
else
  echo "Locust no instalado. Saltando..."
fi

# ==========================================
# 5. JMeter
# ==========================================
echo ""
echo "========================================"
echo "PRUEBA 3: JMeter"
echo "========================================"

if command -v jmeter &> /dev/null; then
  if [ -f "$SCRIPT_DIR/jmeter_test_plan.jmx" ]; then
    jmeter -n -t "$SCRIPT_DIR/jmeter_test_plan.jmx" \
      -l "$RESULTADOS/jmeter_results.csv" \
      -e -o "$RESULTADOS/jmeter_report/" \
      2>&1 | tee "$RESULTADOS/jmeter_output.txt"
    echo "Reporte JMeter: $RESULTADOS/jmeter_report/index.html"
  else
    echo "jmeter_test_plan.jmx no encontrado. Saltando..."
  fi
else
  echo "JMeter no instalado. Saltando..."
fi

# ==========================================
# 6. Resumen final
# ==========================================
echo ""
echo "========================================"
echo "PRUEBAS COMPLETADAS"
echo "========================================"
echo "Resultados en: $RESULTADOS/"
echo ""
echo "Metricas de ab:"
grep -E "(Requests per second|Time per request|Failed requests|Transfer rate|Percentage)" "$RESULTADOS/ab_results.txt" 2>/dev/null || echo "  (sin datos)"
echo ""
echo "Para Insomnia, ejecutar manualmente el Runner desde la UI"
echo "  (ver GUIA_PRUEBAS_CARGA.md seccion 4.4)"
