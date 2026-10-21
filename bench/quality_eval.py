#!/usr/bin/env python
"""Banc de mesure de qualité VLM + RAG + Decider pour le flux RoadGuard.

Pour chacune des 6 images d'échantillon, le script rejoue le pipeline réel
``POST /uploads`` -> téléversement S3 -> ``POST /query`` en mode ``situation``
(le focus qualité), puis relève par image :

- le ``mode`` renvoyé,
- les intentions générées (exactement 3 manœuvres envisagées par le conducteur),
- le score Decider par intention (probabilités exposées dans ``cards[].options``),
- le nombre et les scores de similarité des références RAG retrouvées
  (``debug.knowledge_references[].score``),
- la durée serveur ``debug.elapsed_ms``.

Il imprime un tableau Markdown par image plus des agrégats (moyenne elapsed_ms,
moyenne du meilleur score de référence) et écrit ``docs/quality-eval.md``.

Usage :

    uv run python bench/quality_eval.py --api <url> --images-dir <path>

Le script saute proprement (message clair, sortie 0) si l'URL de l'API ou le
dossier d'images sont absents.

Mode hors-ligne :

    uv run python bench/quality_eval.py --mock

Le mode ``--mock`` n'effectue AUCUN appel réseau et NE LIT AUCUN fichier image
(les 6 images ne sont pas présentes dans le worktree) : il construit un
enregistrement synthétique déterministe par image depuis une table constante.
Les chiffres produits sont SYNTHÉTIQUES / ILLUSTRATIFS et clairement étiquetés
comme tels ; ils ne doivent jamais être présentés comme mesurés. Le mode mock
émet aussi ``docs/quality-eval.md`` (sauf ``--no-emit-report``) et sort toujours
en code 0.

Émission du rapport : par défaut le banc écrit ``docs/quality-eval.md`` (résolu
relativement à la racine du dépôt), que le run soit live ou mock. Utiliser
``--emit-report <chemin>`` pour viser un autre fichier, ou ``--no-emit-report``
pour désactiver l'écriture.
"""

from __future__ import annotations

import argparse
import io
import json
import statistics
import sys
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Mode privilégié par le banc qualité : la situation (3 intentions + RAG décor).
DEFAULT_MODE = "situation"

# Les 6 images d'échantillon, codées en dur : elles vivent HORS du worktree
# (c:\Users\tanto\work\aws_hackathon\samples\) et ne sont donc pas lues en mock.
SAMPLE_IMAGES = (
    "code.jpg",
    "code2.webp",
    "codes-rousseau.webp",
    "image.png",
    "image2.jpg",
    "image3.jpg",
)

# Chemin par défaut du rapport, résolu relativement à la racine du dépôt (parent
# de bench/), pas au répertoire courant.
DEFAULT_REPORT_PATH = Path(__file__).resolve().parent.parent / "docs" / "quality-eval.md"

# Placeholder FR pour les chiffres qui exigent un run live réel.
LIVE_PLACEHOLDER = "<à remplir après un run live>"

# Variables d'environnement requises côté serveur pour un run live.
REQUIRED_ENV_VARS = (
    "DECIDER_ENDPOINT",
    "KNOWLEDGE_BASE_ID",
    "MEDIA_BUCKET",
    "VISION_MODEL_ID",
    "credentials AWS (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION)",
)

# Table synthétique déterministe par image (mode mock). Chaque enregistrement
# expose 3 intentions de manœuvre, 2 scores Decider synthétiques par intention,
# un nombre de références avec scores de similarité synthétiques et une durée
# serveur synthétique. TOUS ces chiffres sont ILLUSTRATIFS, jamais mesurés.
_MOCK_TABLE: dict[str, dict[str, Any]] = {
    "code.jpg": {
        "intentions": [
            "Maintenir sa trajectoire",
            "Ralentir à l'approche",
            "Céder le passage",
        ],
        "decider_scores": [(0.72, 0.28), (0.61, 0.39), (0.55, 0.45)],
        "reference_scores": [0.81, 0.74, 0.69],
        "elapsed_ms": 640.0,
    },
    "code2.webp": {
        "intentions": [
            "S'arrêter au feu",
            "Franchir l'intersection",
            "Tourner à droite",
        ],
        "decider_scores": [(0.83, 0.17), (0.49, 0.51), (0.58, 0.42)],
        "reference_scores": [0.88, 0.70],
        "elapsed_ms": 705.0,
    },
    "codes-rousseau.webp": {
        "intentions": [
            "Dépasser le véhicule lent",
            "Rester derrière",
            "Se rabattre",
        ],
        "decider_scores": [(0.44, 0.56), (0.67, 0.33), (0.62, 0.38)],
        "reference_scores": [0.79, 0.73, 0.66, 0.61],
        "elapsed_ms": 598.0,
    },
    "image.png": {
        "intentions": [
            "Freiner pour le piéton",
            "Continuer prudemment",
            "Klaxonner",
        ],
        "decider_scores": [(0.91, 0.09), (0.52, 0.48), (0.21, 0.79)],
        "reference_scores": [0.90, 0.77, 0.71],
        "elapsed_ms": 712.0,
    },
    "image2.jpg": {
        "intentions": [
            "Céder au rond-point",
            "S'engager directement",
            "Marquer un arrêt",
        ],
        "decider_scores": [(0.78, 0.22), (0.46, 0.54), (0.63, 0.37)],
        "reference_scores": [0.84, 0.72],
        "elapsed_ms": 656.0,
    },
    "image3.jpg": {
        "intentions": [
            "Suivre la file de gauche",
            "Changer de voie",
            "Ralentir",
        ],
        "decider_scores": [(0.69, 0.31), (0.57, 0.43), (0.60, 0.40)],
        "reference_scores": [0.76, 0.70, 0.64],
        "elapsed_ms": 621.0,
    },
}


@dataclass
class QualityRecord:
    """Enregistrement qualité par image (live ou mock)."""

    image: str
    mode: str
    intentions: list[str]
    decider_scores: list[tuple[float, float]]
    reference_scores: list[float]
    elapsed_ms: float

    @property
    def reference_count(self) -> int:
        return len(self.reference_scores)

    @property
    def top_reference_score(self) -> float:
        return max(self.reference_scores) if self.reference_scores else 0.0


def _content_type_for(image_name: str) -> str:
    suffix = Path(image_name).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "image/png")


def _post_json(url: str, payload: dict[str, Any], *, timeout: float = 35.0) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _upload_to_s3(upload: dict[str, Any], image_path: Path, *, timeout: float = 35.0) -> None:
    """Téléverse l'image via le formulaire S3 présigné renvoyé par /uploads."""
    boundary = f"----roadguardquality{uuid.uuid4().hex}"
    buffer = io.BytesIO()

    def _field(name: str, value: str) -> None:
        buffer.write(f"--{boundary}\r\n".encode())
        buffer.write(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        )
        buffer.write(f"{value}\r\n".encode())

    for name, value in upload["fields"].items():
        _field(name, str(value))

    buffer.write(f"--{boundary}\r\n".encode())
    buffer.write(
        b'Content-Disposition: form-data; name="file"; filename="sample"\r\n'
    )
    buffer.write(f'Content-Type: {upload["content_type"]}\r\n\r\n'.encode())
    buffer.write(image_path.read_bytes())
    buffer.write(f"\r\n--{boundary}--\r\n".encode())

    request = urllib.request.Request(
        upload["upload_url"],
        data=buffer.getvalue(),
        headers={"content-type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout):
        return


def _extract_intentions(result: dict[str, Any]) -> list[str]:
    """Extrait les 3 intentions depuis les faits de scène ou les cartes."""
    debug = result.get("debug", {})
    facts = debug.get("scene_facts") or debug.get("facts") or {}
    intentions = facts.get("intentions")
    if isinstance(intentions, list) and intentions:
        return [str(item) for item in intentions]
    # Repli : titres de cartes.
    return [str(card.get("title", "")) for card in result.get("cards", [])]


def _extract_decider_scores(result: dict[str, Any]) -> list[tuple[float, float]]:
    """Score Decider par intention depuis ``cards[].options``.

    Chaque carte expose des options (p. ex. Autorisé / Interdit) portant une
    probabilité ; on relève les deux premières valeurs numériques par carte.
    """
    scores: list[tuple[float, float]] = []
    for card in result.get("cards", []):
        options = card.get("options", [])
        values: list[float] = []
        for option in options:
            if isinstance(option, dict):
                raw = option.get("score", option.get("probability"))
                if isinstance(raw, (int, float)):
                    values.append(float(raw))
        if len(values) >= 2:
            scores.append((values[0], values[1]))
        elif len(values) == 1:
            scores.append((values[0], 0.0))
    return scores


def _extract_reference_scores(result: dict[str, Any]) -> list[float]:
    """Scores de similarité des références RAG depuis debug.knowledge_references."""
    references = result.get("debug", {}).get("knowledge_references", [])
    scores: list[float] = []
    for reference in references:
        raw = reference.get("score") if isinstance(reference, dict) else None
        if isinstance(raw, (int, float)):
            scores.append(float(raw))
    return scores


def run_once(
    api_base: str,
    image_path: Path,
    mode: str,
    content_type: str,
    *,
    post_json: Callable[..., dict[str, Any]] = _post_json,
    upload: Callable[..., None] = _upload_to_s3,
) -> QualityRecord:
    """Exécute un cycle /uploads -> S3 -> /query et construit un QualityRecord.

    Les callables ``post_json`` / ``upload`` sont injectables (comme dans
    ``bench/latency.py``) pour rendre le chemin live testable hors-ligne.
    """
    uploads_url = api_base.rstrip("/") + "/uploads"
    query_url = api_base.rstrip("/") + "/query"

    authorization = post_json(uploads_url, {"content_type": content_type})
    upload(authorization, image_path)
    result = post_json(
        query_url,
        {
            "mode": mode,
            "content_type": content_type,
            "s3_key": authorization["s3_key"],
        },
    )

    return QualityRecord(
        image=image_path.name,
        mode=str(result.get("mode", mode)),
        intentions=_extract_intentions(result),
        decider_scores=_extract_decider_scores(result),
        reference_scores=_extract_reference_scores(result),
        elapsed_ms=float(result.get("debug", {}).get("elapsed_ms", 0)),
    )


def _mock_record(image: str, mode: str) -> QualityRecord:
    """Construit un enregistrement synthétique déterministe pour ``image``.

    Aucun réseau, aucune lecture de fichier : les valeurs proviennent de la table
    constante ``_MOCK_TABLE`` et sont explicitement ILLUSTRATIVES.
    """
    entry = _MOCK_TABLE[image]
    return QualityRecord(
        image=image,
        mode=mode,
        intentions=list(entry["intentions"]),
        decider_scores=[tuple(pair) for pair in entry["decider_scores"]],
        reference_scores=list(entry["reference_scores"]),
        elapsed_ms=float(entry["elapsed_ms"]),
    )


def _format_intentions(record: QualityRecord) -> str:
    return "<br>".join(record.intentions) if record.intentions else "—"


def _format_scores(record: QualityRecord) -> str:
    if not record.decider_scores:
        return "—"
    return "<br>".join(f"{a:.2f}/{b:.2f}" for a, b in record.decider_scores)


def _format_ref_scores(record: QualityRecord) -> str:
    if not record.reference_scores:
        return "—"
    return ", ".join(f"{score:.2f}" for score in record.reference_scores)


def format_markdown_table(records: list[QualityRecord]) -> str:
    """Tableau Markdown par image (intentions, scores Decider, refs RAG, durée)."""
    header = (
        "| image | mode | intentions | scores | #refs | ref scores | elapsed_ms |\n"
        "| --- | --- | --- | --- | ---: | --- | ---: |"
    )
    rows = [header]
    for record in records:
        rows.append(
            f"| {record.image} "
            f"| {record.mode} "
            f"| {_format_intentions(record)} "
            f"| {_format_scores(record)} "
            f"| {record.reference_count} "
            f"| {_format_ref_scores(record)} "
            f"| {record.elapsed_ms:.0f} |"
        )
    return "\n".join(rows)


def aggregate_stats(records: list[QualityRecord]) -> dict[str, float]:
    """Agrégats : moyenne elapsed_ms et moyenne du meilleur score de référence."""
    if not records:
        return {"count": 0, "mean_elapsed_ms": 0.0, "mean_top_ref_score": 0.0}
    return {
        "count": len(records),
        "mean_elapsed_ms": statistics.mean(r.elapsed_ms for r in records),
        "mean_top_ref_score": statistics.mean(r.top_reference_score for r in records),
    }


def write_report_markdown(
    records: list[QualityRecord],
    *,
    path: Path,
    mock: bool,
    mode: str,
) -> None:
    """Écrit le rapport Markdown FR de qualité VLM + RAG + Decider."""
    env_lines = "\n".join(f"- `{name}`" for name in REQUIRED_ENV_VARS)
    table = format_markdown_table(records)
    stats = aggregate_stats(records)

    if mock:
        banner = (
            "> ⚠️ **Chiffres SYNTHÉTIQUES / ILLUSTRATIFS** — générés en mode "
            "`--mock` (hors-ligne, sans appel réseau et sans lecture des images). "
            "Ils servent à valider la structure du rapport et le harnais ; ils ne "
            "reflètent **aucune mesure réelle**. Les agrégats live restent à "
            f"produire : {LIVE_PLACEHOLDER}.\n"
        )
        aggregate_line = (
            f"- Moyenne elapsed_ms (ILLUSTRATIF) : **{stats['mean_elapsed_ms']:.0f} ms**\n"
            f"- Moyenne du meilleur score de référence (ILLUSTRATIF) : "
            f"**{stats['mean_top_ref_score']:.2f}**\n"
            f"- Agrégats mesurés (run live) : {LIVE_PLACEHOLDER}"
        )
    else:
        banner = (
            "> Chiffres mesurés contre une API déployée, mode "
            f"`{mode}` (focus qualité : VLM + RAG + Decider).\n"
        )
        aggregate_line = (
            f"- Moyenne elapsed_ms : **{stats['mean_elapsed_ms']:.0f} ms**\n"
            f"- Moyenne du meilleur score de référence : "
            f"**{stats['mean_top_ref_score']:.2f}**"
        )

    content = f"""# Évaluation qualité — RoadGuard (VLM + RAG + Decider)

{banner}
## Tableau par image

Pour chaque image d'échantillon, le banc relève le mode, les 3 intentions
générées par le VLM, le score Decider par intention, le nombre et les scores de
similarité des références RAG, et la durée serveur `elapsed_ms`.

{table}

## Agrégats

{aggregate_line}

Agrégats live à confirmer : {LIVE_PLACEHOLDER} (moyenne elapsed_ms et moyenne du
meilleur score de référence, pour un run réel contre l'API déployée).

## Images d'échantillon

Les {len(SAMPLE_IMAGES)} images vivent HORS du worktree
(`samples/` à la racine du projet) : {", ".join(SAMPLE_IMAGES)}.

## Commandes de reproduction

Run live (mesure réelle contre l'API déployée) :

```bash
uv run python bench/quality_eval.py --api <url> --images-dir <path> --mode {mode}
```

Run hors-ligne (structure/harnais, chiffres synthétiques) :

```bash
uv run python bench/quality_eval.py --mock
```

## Variables d'environnement requises (run live)

Côté serveur Lambda, le chemin `/uploads` -> S3 -> `/query` exige :

{env_lines}
"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_mock(mode: str) -> list[QualityRecord]:
    """Construit un enregistrement synthétique par image (aucun réseau/fichier)."""
    records: list[QualityRecord] = []
    for image in SAMPLE_IMAGES:
        record = _mock_record(image, mode)
        records.append(record)
        print(
            f"[{image}] (mock) mode={record.mode} "
            f"intentions={len(record.intentions)} "
            f"#refs={record.reference_count} "
            f"elapsed={record.elapsed_ms:.0f} ms"
        )
    return records


def _run_live(api_base: str, images_dir: Path, mode: str) -> list[QualityRecord]:
    """Rejoue chaque image présente dans ``images_dir`` contre l'API live."""
    records: list[QualityRecord] = []
    for image in SAMPLE_IMAGES:
        image_path = images_dir / image
        if not image_path.is_file():
            print(f"[{image}] ignoré : image introuvable ({image_path}).")
            continue
        content_type = _content_type_for(image)
        record = run_once(api_base, image_path, mode, content_type)
        records.append(record)
        print(
            f"[{image}] mode={record.mode} "
            f"intentions={len(record.intentions)} "
            f"#refs={record.reference_count} "
            f"elapsed={record.elapsed_ms:.0f} ms"
        )
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Banc de qualité RoadGuard.")
    parser.add_argument("--api", help="URL de base de l'API (sans /query).")
    parser.add_argument("--images-dir", help="Dossier contenant les images d'échantillon.")
    parser.add_argument(
        "--mode",
        default=DEFAULT_MODE,
        help=f"Mode interrogé (défaut {DEFAULT_MODE}).",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help=(
            "Mode hors-ligne : aucun appel réseau ni lecture d'image, chiffres "
            "SYNTHÉTIQUES/ILLUSTRATIFS pour exercer le harnais et émettre le rapport."
        ),
    )
    parser.add_argument(
        "--emit-report",
        nargs="?",
        const=str(DEFAULT_REPORT_PATH),
        default=str(DEFAULT_REPORT_PATH),
        help=(
            "Chemin du rapport Markdown à écrire "
            f"(défaut {DEFAULT_REPORT_PATH})."
        ),
    )
    parser.add_argument(
        "--no-emit-report",
        action="store_true",
        help="Ne pas écrire de fichier de rapport.",
    )
    args = parser.parse_args(argv)

    if args.mock:
        print(
            "=== BANC QUALITÉ EN MODE MOCK (HORS-LIGNE) ===\n"
            "Chiffres SYNTHÉTIQUES / ILLUSTRATIFS : aucun appel réseau n'est "
            "effectué et aucune image n'est lue. Ces valeurs valident la structure "
            "du rapport et le harnais ; elles ne reflètent AUCUNE mesure réelle.\n"
        )
        records = _run_mock(args.mode)
        print()
        print(format_markdown_table(records))
        print()
        if not args.no_emit_report:
            report_path = Path(args.emit_report)
            write_report_markdown(
                records, path=report_path, mock=True, mode=args.mode
            )
            print(f"Rapport (synthétique) écrit dans {report_path}.")
        return 0

    if not args.api or not args.images_dir:
        print(
            "Banc ignoré : fournissez --api <url> et --images-dir <path> pour "
            "évaluer la qualité contre une API déployée."
        )
        return 0

    images_dir = Path(args.images_dir)
    if not images_dir.is_dir():
        print(f"Banc ignoré : dossier d'images introuvable ({images_dir}).")
        return 0

    records = _run_live(args.api, images_dir, args.mode)
    if not records:
        print("Banc ignoré : aucune image d'échantillon trouvée dans le dossier.")
        return 0

    print()
    print(format_markdown_table(records))
    print()

    if not args.no_emit_report:
        report_path = Path(args.emit_report)
        write_report_markdown(
            records, path=report_path, mock=False, mode=args.mode
        )
        print(f"Rapport écrit dans {report_path}.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
