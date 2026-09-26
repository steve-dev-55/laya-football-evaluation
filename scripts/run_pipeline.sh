#!/usr/bin/env bash
# Pipeline complet §16 — Laya Football Evaluation (protocole v2.0.0).
#
# Usage :
#   bash scripts/run_pipeline.sh [RUN_ID]
#   RUN_ID par défaut : run_$(date -u +%Y%m%dT%H%M%SZ)
#
# Ordre §16 : init DB → collector → cleaner → pre_match → snapshot → laya
# → baselines → evaluator → analyst. Le script s'arrête à la première erreur
# (set -euo pipefail). Si data/raw est vide, des données SYNTHÉTIQUES
# déterministes sont générées au préalable (aucune donnée réelle ; le
# générateur est idempotent et produit des octets identiques).

set -euo pipefail

cd "$(dirname "$0")/.."

RUN_ID="${1:-run_$(date -u +%Y%m%dT%H%M%SZ)}"
CONFIG="configs/experiment.yaml"

echo "=== Pipeline §16 — run_id=${RUN_ID} (config=${CONFIG}) ==="

# Données synthétiques locales si le collecteur n'aurait rien à lire :
# avec un data/raw vide, collector.py bloque (document manquant, §14.2).
if [ ! -f "data/raw/EPL/2021-2022/matches.json" ]; then
    echo "=== data/raw incomplet : génération de données synthétiques ==="
    python3 scripts/generate_synthetic_data.py --config "${CONFIG}"
fi

echo "=== 0/9. Initialisation de la base (§16) ==="
python3 -m src.storage.database init

echo "=== 1/9. Collecteur (§14.2) ==="
python3 -m agents.collector --config "${CONFIG}" --run-id "${RUN_ID}"

echo "=== 2/9. Nettoyeur (§14.3) ==="
python3 -m agents.cleaner --run-id "${RUN_ID}" --config "${CONFIG}"

echo "=== 3/9. Pré-match (§14.4) ==="
python3 -m agents.pre_match --run-id "${RUN_ID}" --config "${CONFIG}"

echo "=== 4/9. Snapshot (§14.5) ==="
python3 -m agents.snapshot --run-id "${RUN_ID}" --config "${CONFIG}"

echo "=== 5/9. Agent Laya (§14.6) ==="
python3 -m agents.laya --run-id "${RUN_ID}" --config "${CONFIG}" --task-version v1

echo "=== 6/9. Baselines (§14.7) ==="
python3 -m agents.baselines --run-id "${RUN_ID}" --config "${CONFIG}"

echo "=== 7/9. Évaluateur (§14.8) ==="
python3 -m agents.evaluator --run-id "${RUN_ID}" --config "${CONFIG}"

echo "=== 8/9. Analyste (§14.9) ==="
python3 -m agents.analyst --run-id "${RUN_ID}" --config "${CONFIG}"

echo "=== Pipeline terminé : run_id=${RUN_ID} ==="
echo "Rapport final : reports/final_report.md"
