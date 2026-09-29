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
import gc
import hashlib
import json
import math
import platform
import random
import time
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
    PROB_SUM_TOLERANCE,
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


# --- Client SDK réel (§2.1, épinglage obligatoire avant le run) --------------
#
# Checkpoint FIGÉ ET HASHÉ avant l'exécution (décision préenregistrée du
# manifeste « laya_checkpoint ») :
#   - dépôt  : convaiinnovations/laya-multilingual (standalone)
#   - commit : e4e9ddf21a7b1903b7acffd8814ad4307bf63a67 (2026-09-24)
#   - sha256 model.safetensors (vérifié au chargement) :
#       9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204
#   - tokenizer sha256 :
#       609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f
# Le routeur explicite `model="multilingual"` garantit qu'un seul checkpoint
# est utilisé (aucune reroute par détection de langue, §2.1 reproductibilité).
SDK_PACKAGE = "laya"
SDK_VERSION = "0.3.21"
SDK_CHECKPOINT_REPO = "convaiinnovations/laya-multilingual"
SDK_CHECKPOINT_REVISION = "e4e9ddf21a7b1903b7acffd8814ad4307bf63a67"
SDK_CHECKPOINT_SHA256 = (
    "9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204"
)
SDK_TOKENIZER_SHA256 = (
    "609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f"
)
# Longueur maximale de contexte du checkpoint (positions RoPE = 8192). Le run
# confirmatoire vise max_len=8192 (maximum du checkpoint) ; un pilot CPU
# contraint peut baisser ce paramètre (documenté comme écart d'exécution D2 :
# troncature tokenizer préfixe-keeper, la section live — score inclus — reste
# en tête de l'état sérialisé, cf. docs/amendments/A3_execution_notes.md).
SDK_DEFAULT_MAX_LEN = 8192


def _to_sdk_questions(questions_v1: dict[str, Any]) -> dict[str, Any]:
    """Mappe QUESTIONS_V1 (protocole, wording figé §8.5) vers le format SDK.

    Règle de mapping figée (déterministe, neutre) :
    - ``choice`` (score_bucket) : chaque catégorie devient une option dont le
      texte est le libellé seul (`criteria = {label: None}`) — aucune
      description qui puisse orienter la réponse ;
    - ``score`` (corners, cartons) : la liste ordonnée des niveaux est passée
      telle quelle (le SDK rend ``level i: <niveau>`` et renvoie des
      probabilités indicées par position) ;
    - les instructions sont recopiées VERBATIM depuis la version figée v1.
    """
    sdk_q: dict[str, Any] = {}
    for task, q in questions_v1.items():
        crit = q["criteria"]
        if q["type"] == "choice":
            # liste figée de libellés -> dict {libellé: None}
            sdk_q[task] = {
                "type": "choice",
                "instructions": q["instructions"],
                "criteria": dict.fromkeys(crit),
            }
        else:  # score : liste ordonnée inchangée
            sdk_q[task] = {
                "type": "score",
                "instructions": q["instructions"],
                "criteria": list(crit),
            }
    return sdk_q


def _map_score_probabilities(
    probabilities: dict[str, Any], criteria: list[str]
) -> dict[str, float]:
    """Traduit les probabilités indicées d'une question ``score`` SDK vers
    les libellés de niveaux du protocole (index -> criteria[i])."""
    out: dict[str, float] = {}
    for idx, level in enumerate(criteria):
        key = str(idx)
        if key not in probabilities:
            raise ValidationError(
                ErrorCode.MISSING_CATEGORY,
                f"niveau d'indice {key} absent de la réponse score",
            )
        out[level] = float(probabilities[key])
    return out


class RealLayaClient(LayaClient):
    """Client d'inférence sur le SDK laya réel (checkpoint épinglé §2.1).

    L'import du SDK est paresseux (l'agent reste importable sans laya/torch
    installés — CI et tests unitaires) ; la construction effective du modèle
    est différée au premier appel de ``predict``.

    Le contrat (§9.1) est respecté à la lettre : la réponse brute du SDK est
    re-sérialisée dans le format du protocole SANS AUCUNE modification des
    probabilités reçues (arrondi 4 décimales du SDK inclus, aucune
    renormalisation, §8.6) ; la latence mesurée couvre tokenisation + passe
    avant (le temps de réponse réel du système sous test).
    """

    package = SDK_PACKAGE
    version = SDK_VERSION
    checkpoint = (
        f"{SDK_CHECKPOINT_REPO}@{SDK_CHECKPOINT_REVISION}"
        f" (sha256:{SDK_CHECKPOINT_SHA256[:16]}…)"
    )
    variant = "laya-multilingual"
    # ~8192 jetons x ~1,56 char/jeton mesuré sur le JSON canonique (A3/D2).
    max_context_chars = 12_800

    def __init__(
        self,
        max_len: int = SDK_DEFAULT_MAX_LEN,
        revision: str = SDK_CHECKPOINT_REVISION,
        model_sha256: str = SDK_CHECKPOINT_SHA256,
    ) -> None:
        self.max_len = int(max_len)
        self.revision = revision
        self.model_sha256 = model_sha256
        self._agent: Any = None
        self.sdk_questions = _to_sdk_questions(QUESTIONS_V1)
        self.sdk_version_checked: str | None = None

    # -- cycle de vie -------------------------------------------------------

    def _ensure_agent(self) -> Any:
        """Construit l'Agent SDK une seule fois (épinglage vérifié)."""
        if self._agent is not None:
            return self._agent
        try:
            from importlib.metadata import version as _pkg_version

            installed = _pkg_version("laya")
        except Exception:  # pragma: no cover - environnement sans paquet
            installed = None
        if installed is not None and installed != self.version:
            raise RuntimeError(
                f"version laya installée ({installed}) != version épinglée "
                f"({self.version}) — l'épinglage §2.1 est obligatoire"
            )
        from laya import Agent  # import paresseux (CI sans SDK)

        self._agent = Agent(
            SDK_CHECKPOINT_REPO,
            revision=self.revision,
            device="cpu",
            expected_sha256={"model.safetensors": self.model_sha256},
        )
        self.sdk_version_checked = installed
        return self._agent

    def dependencies(self) -> dict[str, str]:
        """Versions effectives des dépendances (§2.1 — pas de fait non vérifié)."""
        from importlib.metadata import version as _pkg_version

        deps: dict[str, str] = {}
        for pkg in ("laya", "torch", "transformers", "safetensors", "numpy"):
            try:
                deps[pkg] = _pkg_version(pkg)
            except Exception:  # pragma: no cover
                deps[pkg] = "non installé"
        return deps

    def router_config(self) -> dict[str, Any]:
        """Configuration du système sous test (§2.1)."""
        agent = self._ensure_agent()
        cfg = dict(getattr(agent, "cfg", {}) or {})
        try:
            import torch as _torch

            threads: Any = _torch.get_num_threads()
        except Exception:  # pragma: no cover - torch absent
            threads = "non installé"
        return {
            "mode": "agent direct (model=multilingual, aucune reroute)",
            "model": self.variant,
            "max_len": self.max_len,
            "cfg_max_len": cfg.get("max_len"),
            "head_max_len": cfg.get("head_max_len"),
            "temperature": cfg.get("temperature"),
            "revision": self.revision,
            "threads": threads,
        }

    # -- contrat client (§9.1) ----------------------------------------------

    def predict(
        self, state_json: str, questions: dict[str, Any]
    ) -> tuple[str, float]:
        """Exécute le SDK réel sur l'état canonique et retourne la réponse."""
        agent = self._ensure_agent()
        t0 = time.perf_counter()
        result = agent.predict(
            state_json, self.sdk_questions, max_len=self.max_len
        )
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        answers = result["answers"]

        dists: dict[str, dict[str, float]] = {}
        for task, q in questions.items():
            answer = answers.get(task)
            if answer is None:
                raise ValidationError(
                    ErrorCode.MISSING_CATEGORY,
                    f"tâche absente de la réponse SDK : {task}",
                )
            probs = answer.get("probabilities")
            if not isinstance(probs, dict) or not probs:
                raise ValidationError(
                    ErrorCode.INVALID_SCHEMA,
                    f"{task}: pas de distribution dans la réponse SDK",
                )
            if q["type"] == "choice":
                dists[task] = {k: float(v) for k, v in probs.items()}
            else:  # score : index -> libellé de niveau
                dists[task] = _map_score_probabilities(probs, q["criteria"])

        raw = json.dumps(
            {task: {"probabilities": dist} for task, dist in dists.items()},
            sort_keys=True,
            separators=(",", ":"),
        )
        return raw, latency_ms


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

    # Fabrique de clients (§2.1) : mock (déterministe, CI) ou sdk (réel,
    # checkpoint épinglé). Tout autre valeur bloque le run (§16).
    client_name = str(cfg["laya"].get("client", "mock")).strip().lower()
    sum_tolerance = float(
        cfg["laya"].get("sum_tolerance", PROB_SUM_TOLERANCE)
    )
    if client_name == "mock":
        client: LayaClient = MockLayaClient(seed=int(cfg["seed"]))
    elif client_name == "sdk":
        max_len = int(cfg["laya"].get("max_len", SDK_DEFAULT_MAX_LEN))
        client = RealLayaClient(max_len=max_len)
    else:
        log_error(paths["logs_dir"], AGENT_NAME, run_id, "client",
                  f"client non implémenté : {client_name}")
        return 2

    db = Database(paths["db"])
    db.init()
    # Mémoire (corpus réel : ~125 000 snapshots, state_json de plusieurs Ko) :
    # pagination par pages de 10 000 rows triées par snapshot_id. Chaque page
    # est prédite puis écrite (upsert idempotent, clé prediction_id) avant de
    # charger la suivante — sémantique identique au chargement intégral.
    total_snapshots = db.query(
        "SELECT COUNT(*) AS n FROM match_snapshots "
        "WHERE validation_status = 'validated'"
    )[0]["n"]
    if not total_snapshots:
        log_error(paths["logs_dir"], AGENT_NAME, run_id, "snapshots",
                  "aucun snapshot validé à prédire")
        db.close()
        return 1

    # Échantillonnage optionnel (pilot CPU contraint — A3/D3) : sélection
    # déterministe stratifiée par (cutoff, tier). Le run confirmatoire
    # complet utilise `sampling: null` (tous les snapshots, plan enregistré).
    sampling = cfg["laya"].get("sampling") or None
    sample_ids: set[str] | None = None
    if sampling is not None:
        sample_ids = _select_stratified_sample(db, sampling)
        if not sample_ids:
            log_error(paths["logs_dir"], AGENT_NAME, run_id, "sampling",
                      "échantillon vide")
            db.close()
            return 1
        log_event(logger, "sampling", "ok",
                  f"{len(sample_ids)} snapshots sélectionnés "
                  f"(sur {total_snapshots})", run_id=run_id)
        write_artifact(
            paths["artifacts_dir"] / run_id / "sampling_selection.json",
            {
                "rule": sampling,
                "n_selected": len(sample_ids),
                "n_total": total_snapshots,
                "snapshot_ids": sorted(sample_ids),
            },
            experiment_id=cfg["experiment_id"],
            run_id=run_id,
            producer=PRODUCER,
            input_hashes=[],
            status="validated",
            record_count=len(sample_ids),
        )
    page_size = 10_000

    model_version = cfg["laya"]["model_version"]
    raw_dir = paths["predictions_dir"] / run_id / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    questions = QUESTIONS_V1  # versionnée v1, wording figé (annexe B)

    rows: list[dict[str, Any]] = []
    n_valid = n_invalid = 0
    # Mémoire (corpus réel : ~125 000 snapshots) : flush par page (les
    # upserts sont idempotents, clé prediction_id — sémantique inchangée).
    def _flush() -> None:
        if rows:
            bulk_upsert(db, "laya_predictions", rows)
            rows.clear()

    # Pagination : pages triées par snapshot_id (mémoire bornée, cf. plus haut).
    # En mode échantillonné (pilot A3/D3), les requêtes SQL ne chargent QUE
    # les ids sélectionnés — par blocs de 500 — pour ne jamais tenir en RAM
    # les state_json non prédits (~350 Mo par page complète du corpus réel).
    n_seen = 0
    n_target = len(sample_ids) if sample_ids is not None else total_snapshots
    if sample_ids is not None:
        ordered_ids = sorted(sample_ids)
        pages: list[list[dict[str, Any]]] = [
            db.query(
                "SELECT * FROM match_snapshots WHERE snapshot_id IN "
                f"({','.join('?' * len(chunk))}) ORDER BY snapshot_id",
                tuple(chunk),
            )
            for chunk in (
                ordered_ids[i:i + 500] for i in range(0, len(ordered_ids), 500)
            )
        ]
    else:
        pages = []
        page_start = 0
        while True:
            page = db.query(
                "SELECT * FROM match_snapshots WHERE validation_status = 'validated' "
                "ORDER BY snapshot_id LIMIT ? OFFSET ?",
                (page_size, page_start),
            )
            if not page:
                break
            page_start += len(page)
            pages.append(page)
            if len(page) < page_size:
                break

    for page in pages:
        gc.collect()  # libère les buffers de la page précédente (RAM bornée)
        for snap in page:
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
                    task: validate_distribution(
                        parsed_full[task], task, sum_tolerance=sum_tolerance
                    )
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
            n_seen += 1
        _flush()
        log_event(logger, "progress", "ok",
                  f"{n_seen}/{n_target} prédictions", run_id=run_id)

    invalid_rate = n_invalid / max(n_seen, 1)
    max_invalid = float(cfg["thresholds"]["max_invalid_response_rate"])

    # Audit de répétition (§9.2) : k requêtes identiques sur >= 10 % des
    # snapshots, échantillon déterministe (1 snapshot sur 10 au plus),
    # SCIPÉ AU PÉRIMÈTRE DU RUN (échantillon pilot éventuel).
    # Mémoire : la sélection déterministe se fait sur les identifiants légers
    # (id + tier) puis les états sont chargés par pages pour l'audit.
    audit = _repetition_audit(client, db, cfg, scope_ids=sample_ids)
    if not audit["all_identical"]:
        # §9.2 : si les sorties diffèrent, le protocole exige k = 5 pour
        # tous les snapshots ou une règle d'agrégation figée — marqué warning.
        audit_status = "warning"
    else:
        audit_status = "validated"

    status = "blocked" if invalid_rate > max_invalid else (
        "warning" if audit_status == "warning" else "validated"
    )
    # Métadonnées §2.1 — dépendances et configuration réelles du client
    # (aucune caractéristique non vérifiée dans l'environnement installé).
    if isinstance(client, RealLayaClient):
        try:
            deps = client.dependencies()
            router_cfg: Any = client.router_config()
        except Exception as exc:  # SDK absent — bloqué mais artefact honnête
            deps = {"laya": f"indisponible: {exc}"}
            router_cfg = {"error": str(exc)}
        client_note = (
            "RealLayaClient : SDK laya réel, checkpoint épinglé "
            f"({client.variant}, max_len={client.max_len}) ; tolérance de "
            f"somme adaptée {sum_tolerance} (écart D1, A3)."
        )
    else:
        deps = {"numpy": "n/a (mock)", "sdk": "non installé"}
        router_cfg = "mock (aucun routeur réel)"
        client_note = (
            "MockLayaClient : client déterministe sans donnée réelle ; "
            "le client SDK sera substitué à l'étape d'exécution (§2)."
        )
    payload = {
        "model_metadata": {
            "package": client.package,
            "version": client.version,
            "checkpoint": client.checkpoint,
            "variant": client.variant,
            "max_context_chars": client.max_context_chars,
            "python": platform.python_version(),
            "dependencies": deps,
            "router_config": router_cfg,
            "run_date": audit["run_date"],
            "run_id": run_id,
            "inference_params": {
                "seed": int(cfg["seed"]),
                "batch": 1,
                "task_version": task_version,
                "sum_tolerance": sum_tolerance,
                "sampling": sampling,
            },
        },
        "counts": {
            "snapshots": n_seen,
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
        "note": client_note,
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
              f"laya_run.json valides={n_valid}/{n_target}", run_id=run_id)
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


def _select_stratified_sample(
    db: Database, rule: dict[str, Any]
) -> set[str]:
    """Sélection déterministe stratifiée de snapshots (pilot, A3/D3).

    Règle : strates = produit croisé des valeurs distinctes de
    `stratified_by` (colonnes légères de match_snapshots), restreintes au
    besoin aux seuls cutoffs FIXES de la grille canonique (les snapshots
    événementiels §6.2 ont des cutoffs arbitraires qui exploseraient la
    stratification) ; dans chaque strate, les snapshot_ids triés sont
    parcourus au pas régulier `ids[::step][:n_per_stratum]` — même règle
    de répartition que l'audit §9.2, déterministe et auditable (liste
    écrite dans les artefacts).
    """
    strat_cols = list(rule.get("stratified_by") or ["cutoff_seconds", "information_tier"])
    n_per = max(1, int(rule.get("n_per_stratum", 7)))
    fixed_cutoffs = rule.get("fixed_cutoffs_only") or None
    cols_sql = ", ".join(strat_cols)
    params: list[Any] = []
    where = "validation_status = 'validated'"
    if fixed_cutoffs and "cutoff_seconds" in strat_cols:
        where += f" AND cutoff_seconds IN ({','.join('?' * len(fixed_cutoffs))})"
        params.extend(int(c) for c in fixed_cutoffs)
    rows = db.query(
        f"SELECT snapshot_id, {cols_sql} FROM match_snapshots "
        f"WHERE {where} ORDER BY snapshot_id",
        tuple(params),
    )
    strata: dict[tuple, list[str]] = {}
    for r in rows:
        key = tuple(r[c] for c in strat_cols)
        strata.setdefault(key, []).append(r["snapshot_id"])
    selected: set[str] = set()
    for key in sorted(strata, key=lambda k: tuple(str(x) for x in k)):
        ids = strata[key]
        step = max(1, len(ids) // n_per)
        selected.update(ids[::step][:n_per])
    return selected


def _repetition_audit(
    client: LayaClient, db: Database, cfg: dict[str, Any],
    scope_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Audit de répétition §9.2 : k=5 requêtes identiques sur >= 10 % des
    snapshots (échantillon déterministe, stratifié par tier), dans le
    périmètre `scope_ids` du run (None = tous les snapshots validés).

    Mémoire (corpus réel) : la sélection déterministe s'opère sur les
    identifiants légers (snapshot_id, tier) — même règle de stratification
    que la version historique (tri par snapshot_id, 1 sur `step`) — puis les
    états des seuls snapshots audités sont chargés par pages.
    """
    k = int(cfg["repetition_audit"]["k"])
    min_share = float(cfg["repetition_audit"]["min_share"])
    if scope_ids is None:
        light = db.query(
            "SELECT snapshot_id, information_tier FROM match_snapshots "
            "WHERE validation_status = 'validated' ORDER BY snapshot_id"
        )
    else:
        light = [
            {"snapshot_id": sid, "information_tier": "scoped"}
            for sid in sorted(scope_ids)
        ]
    total = len(light)
    by_tier: dict[str, list[str]] = {}
    for row in light:
        by_tier.setdefault(row["information_tier"], []).append(row["snapshot_id"])
    selected: list[tuple[str, str]] = []
    for tier in sorted(by_tier):
        ids = by_tier[tier]
        n_pick = max(1, math.ceil(min_share * len(ids)))
        step = max(1, len(ids) // n_pick)
        selected.extend((sid, tier) for sid in ids[::step][:n_pick])

    audited: list[dict[str, Any]] = []
    all_identical = True
    max_js = 0.0
    decision_changes = 0
    page = 5_000
    for start in range(0, len(selected), page):
        chunk = selected[start:start + page]
        ids = [sid for sid, _ in chunk]
        placeholders = ",".join("?" * len(ids))
        rows = db.query(
            f"SELECT snapshot_id, state_json FROM match_snapshots "
            f"WHERE snapshot_id IN ({placeholders})",
            tuple(ids),
        )
        states = {r["snapshot_id"]: r["state_json"] for r in rows}
        for sid, tier in chunk:
            state_json = states[sid]
            outputs: list[str] = []
            for _ in range(k):
                raw, _ = client.predict(state_json, QUESTIONS_V1)
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
                    "snapshot_id": sid,
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
        "share": round(n_audited / max(total, 1), 4),
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
