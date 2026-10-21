# Évaluation qualité — RoadGuard (VLM + RAG + Decider)

> ⚠️ **Chiffres SYNTHÉTIQUES / ILLUSTRATIFS** — générés en mode `--mock` (hors-ligne, sans appel réseau et sans lecture des images). Ils servent à valider la structure du rapport et le harnais ; ils ne reflètent **aucune mesure réelle**. Les agrégats live restent à produire : <à remplir après un run live>.

## Tableau par image

Pour chaque image d'échantillon, le banc relève le mode, les 3 intentions
générées par le VLM, le score Decider par intention, le nombre et les scores de
similarité des références RAG, et la durée serveur `elapsed_ms`.

| image | mode | intentions | scores | #refs | ref scores | elapsed_ms |
| --- | --- | --- | --- | ---: | --- | ---: |
| code.jpg | situation | Maintenir sa trajectoire<br>Ralentir à l'approche<br>Céder le passage | 0.72/0.28<br>0.61/0.39<br>0.55/0.45 | 3 | 0.81, 0.74, 0.69 | 640 |
| code2.webp | situation | S'arrêter au feu<br>Franchir l'intersection<br>Tourner à droite | 0.83/0.17<br>0.49/0.51<br>0.58/0.42 | 2 | 0.88, 0.70 | 705 |
| codes-rousseau.webp | situation | Dépasser le véhicule lent<br>Rester derrière<br>Se rabattre | 0.44/0.56<br>0.67/0.33<br>0.62/0.38 | 4 | 0.79, 0.73, 0.66, 0.61 | 598 |
| image.png | situation | Freiner pour le piéton<br>Continuer prudemment<br>Klaxonner | 0.91/0.09<br>0.52/0.48<br>0.21/0.79 | 3 | 0.90, 0.77, 0.71 | 712 |
| image2.jpg | situation | Céder au rond-point<br>S'engager directement<br>Marquer un arrêt | 0.78/0.22<br>0.46/0.54<br>0.63/0.37 | 2 | 0.84, 0.72 | 656 |
| image3.jpg | situation | Suivre la file de gauche<br>Changer de voie<br>Ralentir | 0.69/0.31<br>0.57/0.43<br>0.60/0.40 | 3 | 0.76, 0.70, 0.64 | 621 |

## Agrégats

- Moyenne elapsed_ms (ILLUSTRATIF) : **655 ms**
- Moyenne du meilleur score de référence (ILLUSTRATIF) : **0.83**
- Agrégats mesurés (run live) : <à remplir après un run live>

Agrégats live à confirmer : <à remplir après un run live> (moyenne elapsed_ms et moyenne du
meilleur score de référence, pour un run réel contre l'API déployée).

## Images d'échantillon

Les 6 images vivent HORS du worktree
(`samples/` à la racine du projet) : code.jpg, code2.webp, codes-rousseau.webp, image.png, image2.jpg, image3.jpg.

## Commandes de reproduction

Run live (mesure réelle contre l'API déployée) :

```bash
uv run python bench/quality_eval.py --api <url> --images-dir <path> --mode situation
```

Run hors-ligne (structure/harnais, chiffres synthétiques) :

```bash
uv run python bench/quality_eval.py --mock
```

## Variables d'environnement requises (run live)

Côté serveur Lambda, le chemin `/uploads` -> S3 -> `/query` exige :

- `DECIDER_ENDPOINT`
- `KNOWLEDGE_BASE_ID`
- `MEDIA_BUCKET`
- `VISION_MODEL_ID`
- `credentials AWS (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_REGION)`
