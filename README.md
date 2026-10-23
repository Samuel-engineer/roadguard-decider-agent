# RoadGuard — Analyse de scène routière en double mode

RoadGuard observe une scène routière (photo ou vidéo) et évalue, intention par intention, sa conformité au Code de la route. L'application propose deux modes qui partagent un même cerveau :

- **Examen** — un QCM du Code de la route, extrait de l'image, est tranché par le Decider.
- **Conduite** — à partir de la scène, le modèle de vision (Nova Lite) propose 3 intentions plausibles ; le Decider juge la conformité de chacune d'elles.

Les deux modes s'appuient sur un **unique backbone Lambda** : `POST /query` → perception Bedrock Nova → récupération Knowledge Base → appel `decide(...)` sur l'endpoint SageMaker → réponse unifiée `{mode, cards, scene_summary, debug}`. Le seul point de bascule est le champ `mode` (réglé sur `exam` par défaut, ou `situation`).

## 🏆 Soumission au Hackathon AWS Strands Decider

[![Licence : Apache-2.0](https://img.shields.io/badge/licence-Apache--2.0-blue.svg)](LICENSE)

**Tags officiels :** `#strands-decider-2b` · `#policy`

- **Article AWS Builder Center :** [Lire l'article complet ici](https://builder.aws.com/project/3L2oB6g6YzJJ4DopnnHLPdsMlC7/roadguard-from-roads-to-drones-split-second-policy-decisions-with-strands-decider-2b)
- **Vidéo de Démo technique (< 3 min) :** [Voir sur YouTube](https://www.youtube.com/watch?v=1kB_0ua-gbY)
- **Vidéo Trailer (Concept) :** [Voir sur YouTube](https://www.youtube.com/watch?v=WO-WdzvYOGw)

### 🧩 Pattern réutilisable Strands Decider 2B

> **Le pattern réutilisable est packagé dans [`patterns/closed-form-policy/`](patterns/closed-form-policy/).**
> Il contient : la ou les questions typées, le jeu d'options, le code d'intégration plaçant la décision dans l'exécution de l'agent (`handler.py`), ainsi qu'un `README.md` expliquant son fonctionnement et comment l'importer dans vos propres agents.

### ✅ Checklist de qualification (Pass/Fail)

- [X] Article publié sur AWS Builder Center décrivant l'agent et la décision Decider 2B.
- [X] Dépôt public avec licence approuvée OSI (Apache-2.0) incluant le code source.
- [X] Pattern de décision réutilisable clairement identifié et isolé.
- [X] Vidéo de démo publique (< 3 minutes) montrant l'agent et la décision en action.
- [X] Tags requis présents.

---

## 🏛 Architecture et Pattern : Policy

Le pattern soumis est **Policy** : plutôt que de laisser un grand modèle de langage (LLM) formuler librement une décision, la scène perçue est évaluée par un **Decider** déterministe, basé sur un jeu de questions fermé (binaire ou choix multiples). 
Le modèle de vision (Bedrock Nova Lite) ne prend aucune décision — il décrit et propose des options ; c'est le Decider (Strands 2B sur SageMaker) qui tranche. Le verdict final est ainsi contraint, reproductible et auditable.

La politique est packagée dans `patterns/closed-form-policy/`, avec deux variantes (`choice` pour le mode examen, `noul` pour le mode situation). L'intégration complète à un agent Strands est démontrée et exécutable via le script `examples/strands_agent.py`.

Documentation détaillée disponible dans [`docs/`](docs/) : 
[`architecture.md`](docs/architecture.md) | [`decisions.md`](docs/decisions.md) | [`securite.md`](docs/securite.md) | [`demo.md`](docs/demo.md)

---

## 📊 Évaluation Économique et Latence (Bonus)

Pour évaluer l'efficacité à grande échelle, nous avons modélisé le coût d'inférence pour **10 000 décisions évaluées** entre un LLM monolithique et l'architecture découplée de RoadGuard.

**1. Baseline : LLM Multimodal classique (facturation au token)**
* Input : 2 images + contexte réglementaire $\approx$ 5 000 tokens. Output $\approx$ 400 tokens.
* Coût estimé pour 10k requêtes : $\approx$ **210,00 USD** (coût linéaire et variable).

**2. Architecture RoadGuard : Perception (Nova Lite) + Décision (Strands 2B sur SageMaker)**
* **Perception :** Extraction de scène légère $\approx$ **1,40 USD** / 10k appels.
* **Décision (Decider 2B) :** Hébergé sur une instance `ml.g5.xlarge` ($\approx$ 1,01 USD / heure). Avec une latence d'inférence mesurée de **~250 ms par batch de questions**, l'instance traite jusqu'à 4 req/sec (14 400 req/h). En charge continue, le coût du Decider chute à $\approx$ **0,70 USD** / 10k décisions.
* **Coût total combiné (en charge continue) :** $\approx$ **2,10 USD** / 10k évaluations.

**Conclusion :** En déplaçant l'évaluation des règles vers un modèle de décision de 2B paramètres, RoadGuard réduit les coûts d'inférence récurrents d'un facteur **x40 à x100** sur des flux continus, transformant une dépense variable (au token) en une capacité de calcul amortissable et prévisible.

---

## 🚀 Exécuter l'UI et l'API (Déploiement AWS CDK)

1. **Construire le front-end** dans le dossier `web/` en pointant la variable d'environnement `VITE_API_URL` vers l'URL exposée par `ApiStack` :

   ```bash
   cd web
   VITE_API_URL="https://<api-id>.execute-api.<region>.amazonaws.com" npm install
   VITE_API_URL="https://<api-id>.execute-api.<region>.amazonaws.com" npm run build
   ```

2. **Déployer les stacks** (le composant `BucketDeployment` de `WebStack` utilisera le dossier `web/dist` fraîchement généré) :

   ```bash
   uv run cdk synth WebStack
   uv run cdk deploy ApiStack WebStack
   ```

3. **Tester** : Ouvrez le domaine CloudFront généré (sortie `WebDistributionDomain`). Depuis l'interface, basculez entre les modes Examen et Conduite, téléversez un média, puis consultez les cartes et les scores générés.

> **Option de repli (sans compilation) : `client-test.html`.** 
> Pour tester le flux de bout en bout sans avoir à compiler l'application React, ouvrez simplement le fichier `client-test.html` dans un navigateur. La page permet de sélectionner le mode, demande une signature S3, téléverse le fichier et affiche les résultats JSON bruts retournés par `/query`.

---

## 📡 Flux d'analyse média et Upload S3

Le flux asynchrone recommandé délègue le transfert des fichiers lourds à S3 :
1. Le client appelle `POST /uploads` pour obtenir une URL présignée.
2. Il pousse le fichier directement sur S3.
3. Il déclenche l'analyse via `POST /query` en transmettant la clé S3. 

La Lambda interroge alors le modèle visuel Bedrock pour extraire des faits, récupère le contexte dans la Knowledge Base, et transmet le tout à l'endpoint SageMaker hébergeant Strands Decider. La Lambda inscrit dans CloudWatch l'identifiant de requête et les étapes, mais le contenu des fichiers et le payload SageMaker ne sont **jamais** journalisés.

### Banc de mesure de latence local

Un script d'évaluation est fourni pour mesurer les temps de cycle end-to-end :

```bash
uv run python bench/latency.py --api <url> --image <path>
```
Le script effectue automatiquement la séquence complète sur `N` itérations, relève le temps horloge (client) et le temps de traitement serveur, calcule les centiles (min/p50/p95), et simule une comparaison de latence.
[![Regarder la vidéo](https://img.youtube.com/vi/1kB_0ua-gbY/maxresdefault.jpg)](https://www.youtube.com/watch?v=1kB_0ua-gbY)
