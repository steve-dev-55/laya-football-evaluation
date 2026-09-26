"""Agent Laya (protocole §14.6, §2, §8, §9, §21 « Agent Laya »).

Rôle : pour chaque snapshot VALIDÉ :
1. charger `state_json` et vérifier son hash et son statut anti-fuite (§9.1) ;
2. sérialiser l'état canonique (déjà canonique, vérifié par hash) ;
3. exécuter la version de questions prévue (v1, §8.5) ;
4. appeler le client (checkpoint déclaré dans le manifeste) ;
5. écrire la réponse brute IMMÉDIATEMENT dans
   `data/predictions/{run_id}/raw/` (§9.1) ;
6. valider puis parser (§8.6) — jamais de renormalisation ;
7. dériver le 1X2 (§8.1) et les espérances censurées ;
8. enregistrer latence, statut, erreur éventuelle et hash (§9.3).

ABSTRACTION : `LayaClient` est une classe abstraite ; `MockLayaClient`
fournit une implémentation DÉTERMINISTE (RNG seedé par le hash de l'état,
Poisson simulé) pour les tests et la CI — aucune donnée réelle, aucune clé
API. L'implémentation SDK réelle sera branchée à l'étape d'exécution.

Audit de répétition (§9.2) : k = 5 requêtes identiques sur au moins 10 %
des snapshots (échantillon déterministe stratifié par tier).

Usage (§16) :
    python -m agents.laya --run-id RUN_ID --task-version v1 \
        [--config configs/experiment.yaml]
"""

from __future__ import annotations

import abc
import argparse
import hashlib
import json
import math
import platform
import random
from pathlib import Path
from typing import Any

from agents.common import (
    bulk_upsert,
    config_paths,
    load_config,
    log_error,
    log_event,
    now_utc,
    setup_logging,
    sha256_text,
    write_artifact,
)
from src.core.canonical import canonical_json
from src.core.errors import ErrorCode, ValidationError
from src.core.ids import prediction_id as compute_prediction_id
from src.core.ids import sha256_bytes
from src.core.metrics import jensen_shannon_distance
from src.core.tasks import (
    QUESTIONS_V1,
    expected_value,
    parse_raw_response,
    score_bucket_to_1x2,
    validate_distribution,
)
from src.storage.database import Database

AGENT_NAME = "laya"
PRODUCER = "laya_agent"

# Métadonnées du système sous test (§2.1) — client mock par défaut.
MOCK_PACKAGE = "laya-mock"
MOCK_VERSION = "1.0.0"
MOCK_CHECKPOINT = "PINNED_CHECKPOINT"
MOCK_MAX_CONTEXT_CHARS = 200_000
NOMINAL_MATCH_SECONDS = 5400
"""Durée de temps de jeu nominale pour la fraction restante (annexe B)."""


class LayaClient(abc.ABC):
    """Abstraction du client d'inférence Laya (§2, §9.1).

    Le client réel (SDK) retournera la réponse brute du routeur ; le contrat
    est : entrée = état sérialisé + questions versionnées, sortie = texte
    brut + latence en millisecondes. La réponse brute doit contenir, par
    tâche, un objet `{"probabilities": {catégorie: probabilité}}`.
    """

    package: str = "abstract"
    version: str = "0"
    checkpoint: str = "unknown"
    variant: str = "laya"
    max_context_chars: int = 0

    @abc.abstractmethod
    def predict(
        self, state_json: str, questions: dict[str, Any]
    ) -> tuple[str, float]:
        """Retourne (réponse brute, latence_ms) pour un état et des questions."""


def _poisson_pmf(lam: float, k_max: int) -> list[float]:
    """PMF de Poisson sur 0..k_max (Knuth, lam modéré)."""
    if lam <= 0.0:
        return [1.0] + [0.0] * k_max
    log_p = -lam
    probs: list[float] = []
    for k in range(k_max + 1):
        if k == 0:
            probs.append(math.exp(log_p))
        else:
            log_p += math.log(lam) - math.log(k)
            probs.append(math.exp(min(log_p, 0.0)))
    return probs


def _exact_sum(values: dict[str, float]) -> dict[str, float]:
    """Arrondit à 12 décimales et reporte le résidu sur le mode.

    Garantit |somme - 1| <= ~1e-12 : la distribution reste une construction
    du modèle (aucune renormalisation d'une réponse reçue, interdite §8.6).
    """
    rounded = {k: round(v, 12) for k, v in values.items()}
    mode = max(rounded, key=lambda k: rounded[k])
    residual = 1.0 - sum(rounded.values())
    rounded[mode] = round(rounded[mode] + residual, 12)
    return rounded


class MockLayaClient(LayaClient):
    """Client déterministe pour tests et CI (aucune donnée réelle).

    Génère des distributions valides par Poisson simulé : les paramètres
    dépendent uniquement de l'état (pré-match + live au cutoff) et d'un RNG
    seedé par le hash de l'état — deux appels identiques donnent la même
    réponse (audit de répétition §9.2).
    """

    package = MOCK_PACKAGE
    version = MOCK_VERSION
    checkpoint = MOCK_CHECKPOINT
    variant = "laya-mock"
    max_context_chars = MOCK_MAX_CONTEXT_CHARS

    def __init__(self, seed: int = 20260925) -> None:
        self.seed = seed

    def _rng(self, state_json: str) -> random.Random:
        """RNG déterministe seedé par le hash de l'état (≈ snapshot_id)."""
        digest = hashlib.sha256(
            f"{self.seed}:{state_json}".encode()
        ).digest()
        return random.Random(int.from_bytes(digest[:8], "big"))

    def predict(
        self, state_json: str, questions: dict[str, Any]
    ) -> tuple[str, float]:
        """Produit les trois distributions (buts, corners, cartons)."""
        rng = self._rng(state_json)
        state = json.loads(state_json)
        meta = state.get("metadata") or {}
        cutoff = int(meta.get("cutoff_seconds") or 0)
        live = state.get("live") or {}
        pre = state.get("pre_match") or {}
        remaining = max(0.0, (NOMINAL_MATCH_SECONDS - cutoff) / NOMINAL_MATCH_SECONDS)

        # Paramètres de buts : pré-match si disponible, défauts sinon.
        home_pre = pre.get("home") or {}
        away_pre = pre.get("away") or {}
        att_h = home_pre.get("goals_scored_avg") or 1.2
        def_a = away_pre.get("goals_conceded_avg") or 1.2
        att_a = away_pre.get("goals_scored_avg") or 1.2
        def_h = home_pre.get("goals_conceded_avg") or 1.2
        jitter_h = 1.0 + 0.08 * (2.0 * rng.random() - 1.0)
        jitter_a = 1.0 + 0.08 * (2.0 * rng.random() - 1.0)
        lam_h = min(3.0, max(0.25, 0.55 * (att_h + def_a))) * jitter_h * remaining
        lam_a = min(3.0, max(0.25, 0.55 * (att_a + def_h))) * jitter_a * remaining

        score = (live.get("score") or {})
        cur_h = int(score.get("home") or 0)
        cur_a = int(score.get("away") or 0)

        # Distribution de score regroupé (§8.2) : Poisson indépendants du
        # reste de match, cumulés au score courant, cap 3 + « other ».
        pmf_h = _poisson_pmf(lam_h, 9)
        pmf_a = _poisson_pmf(lam_a, 9)
        buckets: dict[str, float] = {}
        for i, ph in enumerate(pmf_h):
            for j, pa in enumerate(pmf_a):
                h, a = cur_h + i, cur_a + j
                cat = f"{h}-{a}" if h <= 3 and a <= 3 else "other"
                buckets[cat] = buckets.get(cat, 0.0) + ph * pa
        bucket_dist = _exact_sum(
            {cat: buckets.get(cat, 0.0) for cat in QUESTIONS_V1["score_bucket"]["criteria"]}
        )

        # Corners et cartons : compteur courant + Poisson du reste.
        corners = (live.get("corners") or {})
        cur_c = int(corners.get("home") or 0) + int(corners.get("away") or 0)
        lam_c = 10.6 * remaining * (1.0 + 0.10 * (2.0 * rng.random() - 1.0))
        corner_dist = _count_dist(cur_c, lam_c, QUESTIONS_V1["total_corners"]["criteria"])

        yellows = (live.get("yellow_cards") or {})
        cur_y = int(yellows.get("home") or 0) + int(yellows.get("away") or 0)
        lam_y = 3.5 * remaining * (1.0 + 0.10 * (2.0 * rng.random() - 1.0))
        yellow_dist = _count_dist(cur_y, lam_y,
                                   QUESTIONS_V1["total_yellow_cards"]["criteria"])

        raw = json.dumps(
            {
                "score_bucket": {"probabilities": bucket_dist},
                "total_corners": {"probabilities": corner_dist},
                "total_yellow_cards": {"probabilities": yellow_dist},
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        latency_ms = round(80.0 + 240.0 * rng.random(), 3)
        return raw, latency_ms


def _count_dist(current: int, lam: float, criteria: list[str]) -> dict[str, float]:
    """Distribution de comptage : total = courant + Poisson(reste), avec
    queue censurée au seuil (§8.3, §8.4)."""
    tail = criteria[-1]
    threshold = int(tail.rstrip("+"))
    k_max = max(threshold - current, 0) + 4
    pmf = _poisson_pmf(lam, k_max)
    dist: dict[str, float] = {}
    for cat in criteria:
        if cat == tail:
            continue
        level = int(cat)
        offset = level - current
        dist[cat] = pmf[offset] if 0 <= offset <= k_max else 0.0
    tail_mass = 1.0 - sum(dist.values())
    dist[tail] = max(0.0, tail_mass)
    return _exact_sum(dist)


def run_laya(config_path: str | Path, run_id: str, task_version: str) -> int:
    """Exécute les prédictions Laya sur les snapshots validés."""
    cfg = load_config(config_path)
    paths = config_paths(cfg)
    logger = setup_logging(AGENT_NAME, paths["logs_dir"])
    log_event(logger, "start", "ok", f"prédictions Laya task={task_version}",
              run_id=run_id)

    if task_version != "v1":
        log_error(paths["logs_dir"], AGENT_NAME, run_id, "task_version",
                  f"version de tâche inconnue : {task_version}")
        return 2
    if cfg["laya"]["client"] != "mock":
        # L'implémentation SDK réelle est branchée à l'étape d'exécution.
        log_error(paths["logs_dir"], AGENT_NAME, run_id, "client",
                  f"client non implémenté : {cfg['laya']['client']}")
        return 2

    db = Database(paths["db"])
    db.init()
    snapshots = db.query(
        "SELECT * FROM match_snapshots WHERE validation_status = 'validated' "
        "ORDER BY snapshot_id"
    )
    if not snapshots:
        log_error(paths["logs_dir"], AGENT_NAME, run_id, "snapshots",
                  "aucun snapshot validé à prédire")
        db.close()
        return 1

    client = MockLayaClient(seed=int(cfg["seed"]))
    model_version = cfg["laya"]["model_version"]
    raw_dir = paths["predictions_dir"] / run_id / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    questions = QUESTIONS_V1  # versionnée v1, wording figé (annexe B)

    rows: list[dict[str, Any]] = []
    n_valid = n_invalid = 0
    for snap in snapshots:
        state_json = snap["state_json"]
        # (§9.1 étape 2) hash et statut anti-fuite vérifiés avant l'appel.
        if sha256_bytes(state_json.encode("utf-8")) != snap["state_hash"]:
            rows.append(_invalid_row(run_id, snap, model_version, raw_dir,
                                     ErrorCode.SDK_ERROR,
                                     "state_hash incohérent"))
            n_invalid += 1
            continue
        raw, latency = client.predict(state_json, questions)
        pid = compute_prediction_id(run_id, snap["snapshot_id"], model_version)
        raw_path = raw_dir / f"{pid}.json"
        # (§9.1 étape 6) réponse brute écrite AVANT tout parsing.
        raw_path.write_text(raw, encoding="utf-8")
        raw_hash = sha256_bytes(raw.encode("utf-8"))
        try:
            parsed_full = parse_raw_response(raw)
            dists = {
                task: validate_distribution(parsed_full[task], task)
                for task in questions
                if task in parsed_full
            }
            missing = [t for t in questions if t not in dists]
            if missing:
                raise ValidationError(
                    ErrorCode.MISSING_CATEGORY,
                    f"tâches absentes de la réponse : {missing}",
                )
        except ValidationError as exc:
            log_event(logger, "predict", "invalid", exc.detail,
                      run_id=run_id, entity_id=snap["snapshot_id"])
            rows.append(_invalid_row_from(
                run_id, snap, model_version, raw_dir, pid, raw_hash,
                exc.code.value, exc.detail, latency,
            ))
            n_invalid += 1
            continue
        dist_1x2 = score_bucket_to_1x2(dists["score_bucket"])
        parsed_response = canonical_json(dists)
        rows.append(
            {
                "prediction_id": pid,
                "snapshot_id": snap["snapshot_id"],
                "model_version": model_version,
                "run_id": run_id,
                "raw_response_path": str(raw_path.relative_to(paths["predictions_dir"])),
                "raw_response_hash": raw_hash,
                "parsed_response": parsed_response,
                "probability_1": f"{dist_1x2['1']:.6f}",
                "probability_x": f"{dist_1x2['X']:.6f}",
                "probability_2": f"{dist_1x2['2']:.6f}",
                "expected_goals": round(expected_value(dists["score_bucket"]), 6),
                "expected_corners": round(expected_value(dists["total_corners"]), 6),
                "expected_yellow_cards": round(
                    expected_value(dists["total_yellow_cards"]), 6
                ),
                "model_confidence": None,  # le mock n'émet pas de confiance (§9.4)
                "latency_ms": latency,
                "status": "valid",
                "error_code": None,
            }
        )
        n_valid += 1

    bulk_upsert(db, "laya_predictions", rows)

    invalid_rate = n_invalid / max(len(snapshots), 1)
    max_invalid = float(cfg["thresholds"]["max_invalid_response_rate"])

    # Audit de répétition (§9.2) : k requêtes identiques sur >= 10 % des
    # snapshots, échantillon déterministe (1 snapshot sur 10 au plus).
    audit = _repetition_audit(client, snapshots, cfg)
    if not audit["all_identical"]:
        # §9.2 : si les sorties diffèrent, le protocole exige k = 5 pour
        # tous les snapshots ou une règle d'agrégation figée — marqué warning.
        audit_status = "warning"
    else:
        audit_status = "validated"

    status = "blocked" if invalid_rate > max_invalid else (
        "warning" if audit_status == "warning" else "validated"
    )
    payload = {
        "model_metadata": {
            "package": client.package,
            "version": client.version,
            "checkpoint": client.checkpoint,
            "variant": client.variant,
            "max_context_chars": client.max_context_chars,
            "python": platform.python_version(),
            "dependencies": {"numpy": "n/a (mock)", "sdk": "non installé"},
            "router_config": "mock (aucun routeur réel)",
            "run_date": audit["run_date"],
            "run_id": run_id,
            "inference_params": {"seed": int(cfg["seed"]), "batch": 1,
                                 "task_version": task_version},
        },
        "counts": {
            "snapshots": len(snapshots),
            "valid": n_valid,
            "invalid": n_invalid,
            "invalid_rate": invalid_rate,
            "threshold_invalid_rate": max_invalid,
        },
        "repetition_audit": {
            "k": audit["k"],
            "n_audited": audit["n_audited"],
            "share": audit["share"],
            "all_identical": audit["all_identical"],
            "max_js_distance": audit["max_js_distance"],
            "decision_change_rate": audit["decision_change_rate"],
        },
        "questions_version": task_version,
        "note": (
            "MockLayaClient : client déterministe sans donnée réelle ; "
            "le client SDK sera substitué à l'étape d'exécution (§2)."
        ),
    }
    artifact_path = paths["artifacts_dir"] / run_id / "laya_run.json"
    write_artifact(
        artifact_path,
        payload,
        experiment_id=cfg["experiment_id"],
        run_id=run_id,
        producer=PRODUCER,
        input_hashes=[
            "snapshot_validation:" + _digest(
                paths["artifacts_dir"], run_id, "snapshot_validation.json")
        ],
        status=status,
        record_count=n_valid,
        warnings=[] if invalid_rate <= max_invalid else
        [f"taux de réponses invalides {invalid_rate:.3f} > {max_invalid} (§11.4)"],
        errors=[],
    )
    # Artefact détaillé de l'audit de répétition (§9.2).
    write_artifact(
        paths["artifacts_dir"] / run_id / "repetition_audit.json",
        audit,
        experiment_id=cfg["experiment_id"],
        run_id=run_id,
        producer=PRODUCER,
        input_hashes=[
            "laya_run:"
            + _digest(paths["artifacts_dir"], run_id, "laya_run.json")
        ],
        status=audit_status,
        record_count=audit["n_audited"],
    )
    log_event(logger, "artifact", status,
              f"laya_run.json valides={n_valid}/{len(snapshots)}", run_id=run_id)
    if status == "blocked":
        log_error(paths["logs_dir"], AGENT_NAME, run_id, "predict",
                  f"taux d'invalidité {invalid_rate:.3f} > {max_invalid} (§11.4)")
        db.close()
        return 1
    db.close()
    log_event(logger, "end", "ok", "prédictions Laya terminées", run_id=run_id)
    return 0


def _invalid_row(
    run_id: str,
    snap: dict[str, Any],
    model_version: str,
    raw_dir: Path,
    code: ErrorCode,
    detail: str,
) -> dict[str, Any]:
    """Ligne de prédiction invalide (jamais réparée, §0.4)."""
    pid = compute_prediction_id(run_id, snap["snapshot_id"], model_version)
    return _invalid_row_from(
        run_id, snap, model_version, raw_dir, pid, None,
        code.value, detail, None,
    )


def _invalid_row_from(
    run_id: str,
    snap: dict[str, Any],
    model_version: str,
    raw_dir: Path,
    pid: str,
    raw_hash: str | None,
    code: str,
    detail: str,
    latency: float | None,
) -> dict[str, Any]:
    """Ligne de prédiction invalide (réponse brute conservée si présente)."""
    raw_path = raw_dir / f"{pid}.json"
    return {
        "prediction_id": pid,
        "snapshot_id": snap["snapshot_id"],
        "model_version": model_version,
        "run_id": run_id,
        "raw_response_path": str(raw_path),
        "raw_response_hash": raw_hash or "",
        "parsed_response": None,
        "probability_1": None,
        "probability_x": None,
        "probability_2": None,
        "expected_goals": None,
        "expected_corners": None,
        "expected_yellow_cards": None,
        "model_confidence": None,
        "latency_ms": latency,
        "status": "invalid",
        "error_code": code,
    }


def _repetition_audit(
    client: LayaClient, snapshots: list[dict[str, Any]], cfg: dict[str, Any]
) -> dict[str, Any]:
    """Audit de répétition §9.2 : k=5 requêtes identiques sur >= 10 % des
    snapshots (échantillon déterministe, stratifié par tier)."""
    k = int(cfg["repetition_audit"]["k"])
    min_share = float(cfg["repetition_audit"]["min_share"])
    by_tier: dict[str, list[dict[str, Any]]] = {}
    for snap in snapshots:
        by_tier.setdefault(snap["information_tier"], []).append(snap)
    audited: list[dict[str, Any]] = []
    all_identical = True
    max_js = 0.0
    decision_changes = 0
    for tier in sorted(by_tier):
        group = sorted(by_tier[tier], key=lambda s: s["snapshot_id"])
        n_pick = max(1, math.ceil(min_share * len(group)))
        step = max(1, len(group) // n_pick)
        for snap in group[::step][:n_pick]:
            outputs: list[str] = []
            for _ in range(k):
                raw, _ = client.predict(snap["state_json"], QUESTIONS_V1)
                outputs.append(raw)
            hashes = [sha256_bytes(o.encode("utf-8")) for o in outputs]
            identical = len(set(hashes)) == 1
            all_identical = all_identical and identical
            first = json.loads(outputs[0])
            last = json.loads(outputs[-1])
            js = 0.0
            changed = False
            for task, question in QUESTIONS_V1.items():
                p = [first[task]["probabilities"][c] for c in question["criteria"]]
                q = [last[task]["probabilities"][c] for c in question["criteria"]]
                js = max(js, jensen_shannon_distance(p, q))
                if max(range(len(p)), key=lambda i: p[i]) != max(
                    range(len(q)), key=lambda i: q[i]
                ):
                    changed = True
            decision_changes += 1 if changed else 0
            audited.append(
                {
                    "snapshot_id": snap["snapshot_id"],
                    "tier": tier,
                    "k": k,
                    "identical": identical,
                    "hashes": hashes,
                    "js_distance_first_last": js,
                }
            )
            max_js = max(max_js, js)
    n_audited = len(audited)
    return {
        "run_date": now_utc(),
        "k": k,
        "min_share": min_share,
        "n_audited": n_audited,
        "share": round(n_audited / max(len(snapshots), 1), 4),
        "all_identical": all_identical,
        "max_js_distance": round(max_js, 6),
        "decision_change_rate": round(
            decision_changes / max(n_audited, 1), 6
        ),
        "per_snapshot": audited,
        "rule": (
            "sorties identiques => une requête suffit (§9.2) ; sinon k=5 "
            "pour tous les snapshots ou règle d'agrégation figée avant le test"
        ),
    }


def _digest(artifacts_dir: Path, run_id: str, name: str) -> str:
    """Hash SHA-256 d'un artefact d'entrée (chaîne d'audit §15)."""
    path = artifacts_dir / run_id / name
    if not path.is_file():
        return "absent"
    return sha256_text(path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    """Parseur CLI de l'agent Laya."""
    parser = argparse.ArgumentParser(description="Agent Laya (protocole §14.6)")
    parser.add_argument("--run-id", default="run_001")
    parser.add_argument("--config", default="configs/experiment.yaml")
    parser.add_argument("--task-version", default="v1",
                        help="version des questions (seule v1 existe, §8.5)")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI (§16)."""
    args = build_parser().parse_args(argv)
    return run_laya(args.config, args.run_id, args.task_version)


if __name__ == "__main__":
    raise SystemExit(main())
