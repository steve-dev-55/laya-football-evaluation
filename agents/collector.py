"""Agent Collecteur (protocole §14.2, §3.2, §21 checklist « Collecteur »).

Rôle :
- lire `configs/experiment.yaml` (compétitions, saisons, source autorisée) ;
- récupérer les documents sources SANS AUCUNE TRANSFORMATION (§14.2) ;
- calculer le hash SHA-256 de chaque réponse brute (§3.2) ;
- journaliser chaque appel (tentatives, statut, erreurs) avec retries bornés ;
- publier un rapport de couverture par compétition et saison.

ABSTRACTION : la récupération passe par un `SourceAdapter`. L'implémentation
fournie, `LocalFileSource`, lit les fichiers JSON déposés dans
`data/raw/{competition}/{season}/`. L'adapter API réel (réseau) sera branché
à l'étape d'exécution sans modifier le reste du pipeline.

Usage (§16) :
    python -m agents.collector --config configs/experiment.yaml [--run-id RUN_ID]
"""

from __future__ import annotations

import abc
import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents.common import (
    config_paths,
    load_config,
    log_error,
    log_event,
    now_utc,
    setup_logging,
    write_artifact,
)
from src.core.ids import sha256_bytes

AGENT_NAME = "collector"
PRODUCER = "collector_agent"

# Retries bornés (§14.2) : 3 tentatives, backoff exponentiel court.
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 0.05


@dataclass
class SourceDocument:
    """Document source attendu (§3.2 : fournisseur, endpoint, identifiant)."""

    provider: str
    endpoint: str
    competition: str
    season: str

    @property
    def document_id(self) -> str:
        """Identifiant source déterministe du document."""
        return f"{self.provider}:{self.competition}:{self.season}"


@dataclass
class FetchResult:
    """Résultat de la récupération d'un document."""

    document: SourceDocument
    status: str  # ok | error | missing
    sha256: str | None = None
    content: bytes | None = None
    license: str | None = None
    n_matches: int | None = None
    attempts: list[dict[str, Any]] = field(default_factory=list)


class SourceAdapter(abc.ABC):
    """Abstraction de la source de données (§3.2, §14.2).

    L'adapter réel (API réseau) viendra à l'étape d'exécution : il devra
    implémenter `list_documents` et `fetch` sans jamais transformer les
    réponses brutes.
    """

    provider: str = "abstract"

    @abc.abstractmethod
    def list_documents(
        self, competitions: list[str], seasons: list[str]
    ) -> list[SourceDocument]:
        """Liste les documents attendus pour le périmètre de l'expérience."""

    @abc.abstractmethod
    def fetch(self, document: SourceDocument) -> bytes:
        """Récupère le contenu brut du document (sans transformation)."""


class LocalFileSource(SourceAdapter):
    """Source locale : fichiers JSON dans `data/raw/{competition}/{season}/`.

    Contrat de fichier : un document par (compétition, saison) nommé
    `matches.json`, encodé UTF-8, contenant une clé `matches` (liste) et un
    bloc `source` (fournisseur, licence, date de récupération).
    """

    provider = "local_file"

    def __init__(self, raw_dir: str | Path) -> None:
        self.raw_dir = Path(raw_dir)

    def list_documents(
        self, competitions: list[str], seasons: list[str]
    ) -> list[SourceDocument]:
        return [
            SourceDocument(
                provider=self.provider,
                endpoint=str(self.raw_dir / comp / season / "matches.json"),
                competition=comp,
                season=season,
            )
            for comp in competitions
            for season in seasons
        ]

    def fetch(self, document: SourceDocument) -> bytes:
        return Path(document.endpoint).read_bytes()


def fetch_with_retries(
    adapter: SourceAdapter, document: SourceDocument, logger: Any, run_id: str
) -> FetchResult:
    """Récupère un document avec retries bornés et backoff (§9.3, §14.2).

    Chaque tentative est journalisée ; une reprise ne remplace jamais une
    réponse d'origine (aucune transformation ici, donc aucune déduction à
    partir d'une réponse partielle).
    """
    result = FetchResult(document=document, status="error")
    for attempt in range(1, MAX_RETRIES + 1):
        call = {"attempt": attempt, "status": "ok", "message": ""}
        try:
            content = adapter.fetch(document)
        except FileNotFoundError as exc:
            call["status"] = "missing"
            call["message"] = f"fichier absent : {exc}"
        except OSError as exc:
            call["status"] = "error"
            call["message"] = f"erreur de lecture : {exc}"
        else:
            result.content = content
            result.sha256 = sha256_bytes(content)
            result.attempts.append(call)
            log_event(
                logger, "fetch", "ok",
                f"{document.document_id} sha256={result.sha256[:12]}",
                run_id=run_id, entity_id=document.document_id,
            )
            result.status = "ok"
            return result
        result.attempts.append(call)
        log_event(
            logger, "fetch", call["status"], call["message"],
            run_id=run_id, entity_id=document.document_id,
        )
        if attempt < MAX_RETRIES:
            time.sleep(BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)))
    return result


def _describe_document(content: bytes, result: FetchResult) -> None:
    """Extrait les métadonnées du document brut (lecture seule, §3.2)."""
    try:
        parsed = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        result.n_matches = None
        result.license = None
        result.attempts[-1]["message"] += f" | json illisible : {exc}"
        return
    source_block = parsed.get("source") or {}
    result.license = source_block.get("license")
    matches = parsed.get("matches")
    result.n_matches = len(matches) if isinstance(matches, list) else None


def collect(config_path: str | Path, run_id: str) -> int:
    """Exécute la collecte et écrit l'artefact de couverture."""
    cfg = load_config(config_path)
    paths = config_paths(cfg)
    logger = setup_logging(AGENT_NAME, paths["logs_dir"])
    log_event(
        logger, "start", "ok",
        f"collecte périmètre={cfg['competitions']}/{cfg['seasons']}",
        run_id=run_id,
    )

    adapter = LocalFileSource(paths["raw_dir"])
    documents = adapter.list_documents(list(cfg["competitions"]), list(cfg["seasons"]))

    results: list[FetchResult] = []
    for document in documents:
        result = fetch_with_retries(adapter, document, logger, run_id)
        if result.status == "ok" and result.content is not None:
            _describe_document(result.content, result)
        results.append(result)

    missing = [r.document.document_id for r in results if r.status != "ok"]
    retrieved_at = now_utc()
    payload: dict[str, Any] = {
        "source": {
            "adapter": cfg["source"]["adapter"],
            "provider": adapter.provider,
            "raw_dir": str(paths["raw_dir"]),
            "license": cfg["source"]["license"],
            "retrieved_at": retrieved_at,
        },
        "documents": [
            {
                "provider": r.document.provider,
                "endpoint": r.document.endpoint,
                "document_id": r.document.document_id,
                "competition": r.document.competition,
                "season": r.document.season,
                "retrieved_at": retrieved_at,
                "status": r.status,
                "sha256": r.sha256,
                "license": r.license,
                "n_matches": r.n_matches,
                "attempts": r.attempts,
            }
            for r in results
        ],
        "coverage": {
            "expected": len(documents),
            "found": sum(1 for r in results if r.status == "ok"),
            "missing_documents": missing,
        },
        "notes": [
            "Aucune transformation : les fichiers bruts de data/raw restent "
            "immuables (§0.4) ; seul leur hash SHA-256 est publié.",
            "Un document manquant après retries bornés bloque le run (§14.2).",
        ],
    }

    input_hashes = [f"config:{sha256_bytes(Path(config_path).read_bytes())}"]
    status = "blocked" if missing else "validated"
    warnings = [f"document manquant : {m}" for m in missing]
    artifact_path = paths["artifacts_dir"] / run_id / "collector_coverage.json"
    write_artifact(
        artifact_path,
        payload,
        experiment_id=cfg["experiment_id"],
        run_id=run_id,
        producer=PRODUCER,
        input_hashes=input_hashes,
        status=status,
        record_count=sum(1 for r in results if r.status == "ok"),
        warnings=warnings,
    )
    log_event(
        logger, "artifact", status,
        f"collector_coverage.json documents={payload['coverage']['found']}"
        f"/{payload['coverage']['expected']}",
        run_id=run_id,
    )
    if missing:
        log_error(
            paths["logs_dir"], AGENT_NAME, run_id, "collect",
            f"documents manquants : {missing}",
        )
        return 1
    log_event(logger, "end", "ok", "collecte terminée", run_id=run_id)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Parseur CLI de l'agent collecteur."""
    parser = argparse.ArgumentParser(description="Agent Collecteur (protocole §14.2)")
    parser.add_argument("--config", default="configs/experiment.yaml",
                        help="chemin du fichier de configuration YAML")
    parser.add_argument("--run-id", default="run_001",
                        help="identifiant du run (artefacts data/artifacts/RUN_ID)")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée CLI (§16)."""
    args = build_parser().parse_args(argv)
    return collect(args.config, args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
