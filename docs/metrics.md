# Métriques de latence — RoadGuard

> Chiffres mesurés contre une API déployée. La ligne « Nova décide tout » reste `n/a` : cette approche mono-appel VLM n'est pas mesurée par ce banc.

## Tableau par mode

Comparaison côte à côte de l'approche mesurée (**Strands Decider forme fermée**, Decider en
forme fermée + RAG) face à la baseline **Nova décide tout** (mono-appel VLM,
non mesurée par ce banc).

| mode | min | p50 | p95 | mean | max |
| --- | ---: | ---: | ---: | ---: | ---: |
| Strands Decider forme fermée — exam | 1500 | 1500 | 1500 | 1500 | 1500 |
| Strands Decider forme fermée — situation | 1500 | 1500 | 1500 | 1500 | 1500 |
| Nova décide tout (non mesuré) | n/a | n/a | n/a | n/a | n/a |

Chiffres live à confirmer : <à remplir après un run live> (min / p50 / p95 / mean / max en ms
par mode, pour un run réel contre l'API déployée).

## Paramètres du run

- Nombre d'appels par mode (N) : **3**
- Modes exercés : exam, situation

## Commandes de reproduction

Run live (mesure réelle contre l'API déployée) :

```bash
uv run python bench/latency.py --api <url> --image <path> --runs 3
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
