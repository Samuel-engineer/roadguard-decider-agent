#!/usr/bin/env python
"""Banc de mesure de latence end-to-end pour le flux RoadGuard.

Pour chaque mode (``exam`` puis ``situation``), le script enchaîne
``POST /uploads`` -> téléversement S3 -> ``POST /query`` N fois (5 par défaut),
en relevant à la fois la durée horloge par appel et la mesure serveur
``debug.elapsed_ms``. Il imprime min/médiane/p50/p95 et un mini tableau comparé à
« Nova décide tout », puis sort en code non nul si le p95 horloge atteint le
plafond de 29 s d'API Gateway.

Usage :

    uv run python bench/latency.py --api <url> --image <path>

Le script saute proprement (message clair, sortie 0) si l'URL de l'API ou
l'image d'échantillon sont absentes.

Mode hors-ligne :

    uv run python bench/latency.py --mock

Le mode ``--mock`` n'effectue AUCUN appel réseau : il exerce le code de
chronométrage (``run_once``) avec des callables ``post_json``/``upload`` injectés
renvoyant une mesure serveur déterministe, puis imprime la structure du tableau.
Les chiffres produits sont SYNTHÉTIQUES/ILLUSTRATIFS et clairement étiquetés comme
tels ; ils ne doivent jamais être présentés comme mesurés. Le mode mock émet aussi
``docs/metrics.md`` (sauf ``--no-emit-metrics``) et sort toujours en code 0 (le
plafond 29 s réel ne s'applique pas aux chiffres synthétiques).

Émission des métriques : par défaut le banc écrit ``docs/metrics.md`` (résolu
relativement à la racine du dépôt), que le run soit live ou mock. Utiliser
``--emit-metrics <chemin>`` pour viser un autre fichier, ou ``--no-emit-metrics``
pour désactiver l'écriture.

OPTION (non implémentée, S7) : si le p95 s'approche de 29 s, bascule possible vers
une Lambda Function URL (plafond 60 s, même code Lambda). Ce n'est qu'une piste de
repli documentée, pas une bascule construite ici.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Plafond d'intégration d'API Gateway HTTP API (voir api_stack.py, timeout 29 s).
API_GATEWAY_TIMEOUT_MS = 29000
DEFAULT_RUNS = 5
MODES = ("exam", "situation")

# Repère indicatif pour la colonne « Nova décide tout » du tableau : une approche
# mono-appel VLM (sans Decider ni RAG) n'est pas mesurée ici, on affiche n/a.
NOVA_BASELINE_LABEL = "Nova décide tout"

# Libellé de l'approche mesurée (Decider en forme fermée + RAG).
DECIDER_LABEL = "Strands Decider forme fermée"

# Chemin par défaut du fichier de métriques, résolu relativement à la racine du
# dépôt (parent de bench/), pas au répertoire courant.
DEFAULT_METRICS_PATH = Path(__file__).resolve().parent.parent / "docs" / "metrics.md"

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

# Mesure serveur synthétique (ms) injectée par mode en mode mock. Déterministe.
_MOCK_SERVER_ELAPSED_MS = {"exam": 420.0, "situation": 680.0}


def percentile(samples: list[float], fraction: float) -> float:
    """Percentile par interpolation linéaire (``fraction`` dans [0, 1])."""
    if not samples:
        raise ValueError("percentile() requiert au moins un échantillon.")
    ordered = sorted(samples)
    if len(ordered) == 1:
        return ordered[0]
    rank = fraction * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] + (ordered[high] - ordered[low]) * weight


def summarize(samples: list[float]) -> dict[str, float]:
    """min/median/p50/p95/max pour une série de latences (ms)."""
    if not samples:
        raise ValueError("summarize() requiert au moins un échantillon.")
    return {
        "count": len(samples),
        "min": min(samples),
        "median": statistics.median(samples),
        "p50": percentile(samples, 0.50),
        "p95": percentile(samples, 0.95),
        "max": max(samples),
    }


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
    import io
    import uuid

    boundary = f"----roadguardbench{uuid.uuid4().hex}"
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
    buffer.write(
        f'Content-Type: {upload["content_type"]}\r\n\r\n'.encode()
    )
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


def run_once(
    api_base: str,
    image_path: Path,
    mode: str,
    content_type: str,
    *,
    post_json: Callable[..., dict[str, Any]] = _post_json,
    upload: Callable[..., None] = _upload_to_s3,
) -> tuple[float, float]:
    """Exécute un cycle /uploads -> S3 -> /query.

    Renvoie ``(wall_ms, server_elapsed_ms)`` : la durée horloge totale du cycle et
    la mesure serveur ``debug.elapsed_ms`` de l'appel Decider.
    """
    uploads_url = api_base.rstrip("/") + "/uploads"
    query_url = api_base.rstrip("/") + "/query"

    started = time.monotonic()
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
    wall_ms = (time.monotonic() - started) * 1000.0
    server_ms = float(result.get("debug", {}).get("elapsed_ms", 0))
    return wall_ms, server_ms


def _content_type_for(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "image/png")


def format_table(stats_by_mode: dict[str, dict[str, float]]) -> str:
    """Mini tableau latence (ms) par mode vs « Nova décide tout »."""
    lines = [
        f"{'mode':<12}{'min':>10}{'p50':>10}{'p95':>10}{'max':>10}",
        "-" * 52,
    ]
    for mode, stats in stats_by_mode.items():
        lines.append(
            f"{mode:<12}"
            f"{stats['min']:>10.0f}"
            f"{stats['p50']:>10.0f}"
            f"{stats['p95']:>10.0f}"
            f"{stats['max']:>10.0f}"
        )
    lines.append(
        f"{NOVA_BASELINE_LABEL:<12}{'n/a':>10}{'n/a':>10}{'n/a':>10}{'n/a':>10}"
    )
    return "\n".join(lines)


def format_markdown_table(
    stats_by_mode: dict[str, dict[str, float]], *, mock: bool
) -> str:
    """Tableau Markdown latence (ms) par mode + comparaison Decider vs Nova.

    En mode live, la ligne « Nova décide tout » affiche ``n/a`` car cette approche
    mono-appel VLM n'est pas mesurée par ce banc. En mode mock, les chiffres sont
    SYNTHÉTIQUES : la ligne de comparaison est explicitement préfixée
    « illustratif » et ne doit jamais être lue comme une mesure réelle.
    """
    header = (
        "| mode | min | p50 | p95 | mean | max |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: |"
    )
    rows = [header]
    for mode, stats in stats_by_mode.items():
        mean = stats.get("mean", stats["median"])
        rows.append(
            f"| {DECIDER_LABEL} — {mode} "
            f"| {stats['min']:.0f} "
            f"| {stats['p50']:.0f} "
            f"| {stats['p95']:.0f} "
            f"| {mean:.0f} "
            f"| {stats['max']:.0f} |"
        )
    if mock:
        rows.append(
            f"| {NOVA_BASELINE_LABEL} (illustratif, NON mesuré) "
            "| illustratif | illustratif | illustratif | illustratif "
            "| illustratif |"
        )
    else:
        rows.append(
            f"| {NOVA_BASELINE_LABEL} (non mesuré) "
            "| n/a | n/a | n/a | n/a | n/a |"
        )
    return "\n".join(rows)


def write_metrics_markdown(
    stats_by_mode: dict[str, dict[str, float]],
    *,
    path: Path,
    mock: bool,
    runs: int,
) -> None:
    """Écrit un fichier Markdown FR récapitulant les mesures de latence.

    Le fichier contient : un titre, le tableau Markdown par mode (comparaison
    « Strands Decider forme fermée » vs « Nova décide tout »), des placeholders
    ``<à remplir après un run live>`` pour les chiffres live, les commandes exactes
    de repro (live et mock), la liste des variables d'environnement requises et la
    valeur de N. En mode mock, un en-tête signale explicitement que les chiffres
    sont synthétiques/illustratifs et ne reflètent aucune mesure réelle.
    """
    env_lines = "\n".join(f"- `{name}`" for name in REQUIRED_ENV_VARS)
    table = format_markdown_table(stats_by_mode, mock=mock)

    if mock:
        banner = (
            "> ⚠️ **Chiffres SYNTHÉTIQUES / ILLUSTRATIFS** — générés en mode "
            "`--mock` (hors-ligne, sans appel réseau). Ils servent à valider la "
            "structure du tableau et le harnais de chronométrage ; ils ne "
            "reflètent **aucune mesure réelle**. Les valeurs live restent à "
            f"produire : {LIVE_PLACEHOLDER}.\n"
        )
    else:
        banner = (
            "> Chiffres mesurés contre une API déployée. La ligne « Nova décide "
            "tout » reste `n/a` : cette approche mono-appel VLM n'est pas mesurée "
            "par ce banc.\n"
        )

    content = f"""# Métriques de latence — RoadGuard

{banner}
## Tableau par mode

Comparaison côte à côte de l'approche mesurée (**{DECIDER_LABEL}**, Decider en
forme fermée + RAG) face à la baseline **{NOVA_BASELINE_LABEL}** (mono-appel VLM,
non mesurée par ce banc).

{table}

Chiffres live à confirmer : {LIVE_PLACEHOLDER} (min / p50 / p95 / mean / max en ms
par mode, pour un run réel contre l'API déployée).

## Paramètres du run

- Nombre d'appels par mode (N) : **{runs}**
- Modes exercés : {", ".join(MODES)}

## Commandes de reproduction

Run live (mesure réelle contre l'API déployée) :

```bash
uv run python bench/latency.py --api <url> --image <path> --runs {runs}
```

Run hors-ligne (structure/harnais, chiffres synthétiques) :

```bash
uv run python bench/latency.py --mock
```

## Variables d'environnement requises (run live)

Côté serveur Lambda, le chemin `/uploads` -> S3 -> `/query` exige :

{env_lines}
"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _mock_callables(mode: str) -> tuple[Callable[..., dict[str, Any]], Callable[..., None]]:
    """Callables injectés pour run_once en mode mock (aucun réseau).

    ``post_json`` renvoie une autorisation /uploads factice puis une réponse /query
    exposant un ``debug.elapsed_ms`` synthétique déterministe pour ``mode``. Une
    très courte latence horloge est introduite par ``run_once`` lui-même.
    """
    server_ms = _MOCK_SERVER_ELAPSED_MS.get(mode, 500.0)

    def fake_post_json(url: str, _payload: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        if url.endswith("/uploads"):
            return {
                "upload_url": "https://s3.invalid/mock",
                "fields": {"key": "requests/mock.png"},
                "s3_key": "requests/mock.png",
                "content_type": "image/png",
            }
        # Petite pause déterministe pour une durée horloge non nulle.
        time.sleep(0.001)
        return {"mode": mode, "cards": [], "debug": {"elapsed_ms": server_ms}}

    def fake_upload(_authorization: dict[str, Any], _image_path: Path, **_kwargs: Any) -> None:
        return None

    return fake_post_json, fake_upload


def _run_mock(runs: int) -> dict[str, dict[str, float]]:
    """Exerce run_once en mode mock pour chaque mode et renvoie les stats."""
    stats_by_mode: dict[str, dict[str, float]] = {}
    for mode in MODES:
        post_json, upload = _mock_callables(mode)
        wall_samples: list[float] = []
        for _ in range(runs):
            wall_ms, server_ms = run_once(
                "https://api.invalid",
                Path("mock.png"),
                mode,
                "image/png",
                post_json=post_json,
                upload=upload,
            )
            wall_samples.append(wall_ms)
            print(f"[{mode}] (mock) horloge={wall_ms:.0f} ms serveur={server_ms:.0f} ms")
        stats = summarize(wall_samples)
        stats["mean"] = statistics.mean(wall_samples)
        stats_by_mode[mode] = stats
    return stats_by_mode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Banc de latence RoadGuard.")
    parser.add_argument("--api", help="URL de base de l'API (sans /query).")
    parser.add_argument("--image", help="Chemin de l'image d'échantillon.")
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help=f"Nombre d'appels par mode (défaut {DEFAULT_RUNS}).",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help=(
            "Mode hors-ligne : aucun appel réseau, chiffres SYNTHÉTIQUES/"
            "ILLUSTRATIFS pour exercer le harnais et émettre metrics.md."
        ),
    )
    parser.add_argument(
        "--emit-metrics",
        nargs="?",
        const=str(DEFAULT_METRICS_PATH),
        default=str(DEFAULT_METRICS_PATH),
        help=(
            "Chemin du fichier de métriques Markdown à écrire "
            f"(défaut {DEFAULT_METRICS_PATH})."
        ),
    )
    parser.add_argument(
        "--no-emit-metrics",
        action="store_true",
        help="Ne pas écrire de fichier de métriques.",
    )
    args = parser.parse_args(argv)

    if args.mock:
        print(
            "=== BANC EN MODE MOCK (HORS-LIGNE) ===\n"
            "Chiffres SYNTHÉTIQUES / ILLUSTRATIFS : aucun appel réseau n'est "
            "effectué. Ces valeurs valident la structure du tableau et le harnais "
            "de chronométrage ; elles ne reflètent AUCUNE mesure réelle.\n"
        )
        stats_by_mode = _run_mock(args.runs)
        print()
        print(format_markdown_table(stats_by_mode, mock=True))
        print()
        if not args.no_emit_metrics:
            metrics_path = Path(args.emit_metrics)
            write_metrics_markdown(
                stats_by_mode, path=metrics_path, mock=True, runs=args.runs
            )
            print(f"Métriques (synthétiques) écrites dans {metrics_path}.")
        return 0

    if not args.api or not args.image:
        print(
            "Banc ignoré : fournissez --api <url> et --image <path> pour mesurer "
            "la latence contre une API déployée."
        )
        return 0

    image_path = Path(args.image)
    if not image_path.is_file():
        print(f"Banc ignoré : image introuvable ({image_path}).")
        return 0

    content_type = _content_type_for(image_path)
    stats_by_mode: dict[str, dict[str, float]] = {}
    worst_p95 = 0.0

    for mode in MODES:
        wall_samples: list[float] = []
        for _ in range(args.runs):
            wall_ms, server_ms = run_once(args.api, image_path, mode, content_type)
            wall_samples.append(wall_ms)
            print(
                f"[{mode}] horloge={wall_ms:.0f} ms serveur={server_ms:.0f} ms"
            )
        stats = summarize(wall_samples)
        stats["mean"] = statistics.mean(wall_samples)
        stats_by_mode[mode] = stats
        worst_p95 = max(worst_p95, stats["p95"])

    print()
    print(format_table(stats_by_mode))
    print()

    if not args.no_emit_metrics:
        metrics_path = Path(args.emit_metrics)
        write_metrics_markdown(
            stats_by_mode, path=metrics_path, mock=False, runs=args.runs
        )
        print(f"Métriques écrites dans {metrics_path}.")

    if worst_p95 >= API_GATEWAY_TIMEOUT_MS:
        print(
            f"ÉCHEC : p95 {worst_p95:.0f} ms >= plafond {API_GATEWAY_TIMEOUT_MS} ms "
            "d'API Gateway. OPTION de repli (non construite) : Lambda Function URL "
            "(60 s, même code)."
        )
        return 1

    print(f"OK : p95 {worst_p95:.0f} ms < plafond {API_GATEWAY_TIMEOUT_MS} ms.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
