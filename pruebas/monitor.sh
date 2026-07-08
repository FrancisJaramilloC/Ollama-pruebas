#!/bin/bash
# Uso: ./monitor.sh <nombre_prueba>
# Ejemplo: ./monitor.sh ab_test_1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TEST_NAME="${1:-prueba}"
OUTPUT_DIR="$REPO_ROOT/resultados/$TEST_NAME"
mkdir -p "$OUTPUT_DIR"

echo "=== MONITOREO: $TEST_NAME ==="
echo "Fecha: $(date)"
echo ""

# 1. Baseline
echo "=== DOCKER STATS ===" >> "$OUTPUT_DIR/docker_stats.csv"
echo "timestamp,name,cpu_percent,mem_used,mem_percent" >> "$OUTPUT_DIR/docker_stats.csv"

echo "=== BASELINE ==="
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" \
  > "$OUTPUT_DIR/docker_stats_baseline.txt"

# 2. vmstat (CPU/Memoria del host)
echo "Iniciando vmstat..."
vmstat 1 60 > "$OUTPUT_DIR/vmstat.log" &
VMSTAT_PID=$!

# 3. Monitoreo continuo de docker stats (cada 2s)
echo "Iniciando docker stats cada 2s..."
(
  for i in $(seq 1 60); do
    TS=$(date +%H:%M:%S)
    STATS=$(docker stats --no-stream --format '{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}}' 2>/dev/null | tr '\n' ';')
    echo "$TS,$STATS" >> "$OUTPUT_DIR/docker_stats.csv"
    sleep 2
  done
) &
DOCKER_PID=$!

echo ""
echo "Monitoreando... Presiona Ctrl+C cuando termine la prueba de carga"
echo "  VMSTAT PID: $VMSTAT_PID"
echo "  DOCKER PID: $DOCKER_PID"
echo ""

# Esperar
wait $DOCKER_PID
kill $VMSTAT_PID 2>/dev/null

echo ""
echo "=== MONITOREO COMPLETADO ==="
echo "Resultados en: $OUTPUT_DIR/"
echo ""
echo "Archivos generados:"
ls -la "$OUTPUT_DIR/"
