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
    args = parser.parse_args(argv)

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
        stats_by_mode[mode] = stats
        worst_p95 = max(worst_p95, stats["p95"])

    print()
    print(format_table(stats_by_mode))
    print()

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
