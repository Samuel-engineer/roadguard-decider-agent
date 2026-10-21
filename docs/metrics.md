# Métriques de latence — RoadGuard

> ⚠️ **Chiffres SYNTHÉTIQUES / ILLUSTRATIFS** — générés en mode `--mock` (hors-ligne, sans appel réseau). Ils servent à valider la structure du tableau et le harnais de chronométrage ; ils ne reflètent **aucune mesure réelle**. Les valeurs live restent à produire : <à remplir après un run live>.

## Tableau par mode

Comparaison côte à côte de l'approche mesurée (**Strands Decider forme fermée**, Decider en
forme fermée + RAG) face à la baseline **Nova décide tout** (mono-appel VLM,
non mesurée par ce banc).

| mode | min | p50 | p95 | mean | max |
| --- | ---: | ---: | ---: | ---: | ---: |
| Strands Decider forme fermée — exam | 1 | 2 | 2 | 1 | 2 |
| Strands Decider forme fermée — situation | 1 | 2 | 2 | 2 | 2 |
| Nova décide tout (illustratif, NON mesuré) | illustratif | illustratif | illustratif | illustratif | illustratif |

Chiffres live à confirmer : <à remplir après un run live> (min / p50 / p95 / mean / max en ms
par mode, pour un run réel contre l'API déployée).

## Paramètres du run

- Nombre d'appels par mode (N) : **5**
- Modes exercés : exam, situation

## Commandes de reproduction

Run live (mesure réelle contre l'API déployée) :

```bash
uv run python bench/latency.py --api <url> --image <path> --runs 5
```

Run hors-ligne (structure/harnais, chiffres synthétiques) :

```bash
uv run python bench/latency.py --mock
```

## Variables d'environnement requises (run live)

Côté serveur Lambda, le chemin `/uploads` -> S3 -> `/query` exige :

- `DECIDER_ENDPOINT`
- `KNOWLEDGE_BASE_ID`
- `MEDIA_BUCKET`
- `VISION_MODEL_ID`
- `credentials AWS (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION)`
