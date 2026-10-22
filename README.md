# RoadGuard — analyse de scène routière en double mode

RoadGuard regarde une scène routière (photo ou vidéo) et dit, intention par
intention, ce qui est conforme au Code de la route. L'application a deux modes qui
partagent un même cerveau :

- **Examen** — un QCM du Code de la route, extrait de l'image, est tranché par le
  Decider.
- **Conduite** — au vu de la scène, le modèle de vision (Nova Lite) propose 3
  intentions plausibles du conducteur ; le Decider juge la conformité de chacune.

Les deux modes empruntent un **unique backbone Lambda** : `POST /query` → perception
Bedrock Nova → récupération Knowledge Base → `decide(...)` sur l'endpoint SageMaker →
réponse unifiée `{mode, cards, scene_summary, debug}`. Le seul point de branchement
est le champ `mode` (`exam` par défaut, ou `situation`).

## Soumission hackathon

> Récapitulatif complet et étapes de finalisation : [`SUBMISSION.md`](SUBMISSION.md).

[![Licence : Apache-2.0](https://img.shields.io/badge/licence-Apache--2.0-blue.svg)](LICENSE)

Licence **Apache-2.0** (OSI) — voir [`LICENSE`](LICENSE).

Pattern déclaré : `#strands-decider-2b` · `#policy`.

- **Article Builder Center :** [https://builder.aws.com/project/3L2oB6g6YzJJ4DopnnHLPdsMlC7/roadguard-from-roads-to-drones-split-second-policy-decisions-with-strands-decider-2b](https://builder.aws.com/project/3L2oB6g6YzJJ4DopnnHLPdsMlC7/roadguard-from-roads-to-drones-split-second-policy-decisions-with-strands-decider-2b)
- **Vidéo démo (< 3 min) :** [https://www.youtube.com/watch?v=1kB_0ua-gbY](https://www.youtube.com/watch?v=1kB_0ua-gbY)

### Pattern réutilisable Strands Decider 2B

> Le pattern réutilisable est packagé dans
> [`patterns/closed-form-policy/`](patterns/closed-form-policy/) : question(s)
> typée(s) et jeu d'options, câblage qui place la décision dans le chemin d'outil de
> l'agent, et une note sur ce qu'il fait et comment le réutiliser.

### Checklist pass/fail

- [X] Article publié sur AWS Builder Center (décrit l'agent et la décision Decider 2B)
- [X] Repo public avec licence OSI (Apache-2.0) + code source de l'agent
- [X] Pattern de décision Strands Decider 2B réutilisable, clairement libellé
- [X] Vidéo démo publique < 3 min montrant l'agent et sa décision Decider 2B
- [X] Tags requis présents : `#strands-decider-2b` et `#policy`

## Pattern déclaré : Policy

Le pattern de soumission est **Policy** : plutôt que de laisser le modèle décider
librement, on fait classer la scène perçue par un **Decider** déterministe, sur un jeu
de questions fermé (oui/non ou choix). Le modèle de vision ne juge jamais — il décrit
et propose ; le Decider tranche. Le verdict est donc reproductible et auditable.

La politique est packagée dans `patterns/closed-form-policy/`, avec deux variantes
(`choice` pour l'examen, `noul` pour la situation) partageant un seul
`ClosedFormPolicyHandler`. En production, la Lambda appelle `decide(...)` directement,
sans boucle d'agent ; l'intégration à un agent Strands est démontrée (et exécutable)
dans `examples/strands_agent.py`. `strands-agents` reste une dépendance de
développement et n'entre jamais dans le bundle Lambda.

Documentation détaillée dans [`docs/`](docs/) : [`architecture.md`](docs/architecture.md),
[`decisions.md`](docs/decisions.md), [`securite.md`](docs/securite.md),
[`demo.md`](docs/demo.md), le [script vidéo](docs/demo-script.md) et
l'[article Builder Center](docs/builder-center-article.md).

## Exécuter l'UI + l'API

1. **Construire le front** dans `web/` en pointant `VITE_API_URL` vers l'URL `/query`
   exposée par `ApiStack` (sortie `ApiEndpointUrl`) :

   ```bash
   cd web
   VITE_API_URL="https://<api-id>.execute-api.<region>.amazonaws.com/query" npm install
   VITE_API_URL="https://<api-id>.execute-api.<region>.amazonaws.com/query" npm run build
   ```

2. **Déployer les stacks** (le `BucketDeployment` de `WebStack` consomme `web/dist`) :

   ```bash
   uv run cdk synth WebStack
   uv run cdk deploy ApiStack WebStack
   ```

3. Ouvrir le domaine CloudFront (sortie `WebDistributionDomain`). Dans l'UI, basculer
   Examen / Conduite, téléverser un média, lire les cartes et les scores.

Côté API, le flux est : `POST /uploads` (autorisation S3 présignée) → envoi direct du
fichier vers S3 → `POST /query` avec `{mode, content_type, s3_key}`. Les détails de la
procédure de déploiement, de CORS et du banc de latence sont dans les sections plus
bas.

> **Repli sans build : `client-test.html`.** Pour tester le flux sans construire le
> front, ouvrir `client-test.html` dans un navigateur : la page sélectionne le mode,
> demande une autorisation, envoie le fichier vers S3 et affiche les cartes, le résumé
> de scène et le panneau debug de `/query`.

---

# Flux d'analyse média

Le flux recommandé utilise `POST /uploads` pour obtenir un formulaire S3 présigné,
téléverse le fichier directement depuis le client vers `media_bucket`, puis appelle
`POST /query` avec la clé S3. Le média ne transite ainsi pas par API Gateway ni par
la Lambda. La Lambda demande ensuite au modèle visuel Bedrock d'en extraire des faits
au format JSON, récupère les passages pertinents de la Knowledge Base puis transmet
l'ensemble au endpoint SageMaker configuré.

## Organisation du code Lambda

`functions/main.py` conserve le handler Lambda et orchestre le flux ainsi que la
conversion des erreurs en réponses HTTP. Les détails sont répartis dans
`functions/core/` : `http.py` traite les requêtes et réponses, `uploads.py` crée les
autorisations S3 présignées, `media.py` valide et analyse les médias, `knowledge.py`
interroge la Knowledge Base, et `decider.py` prépare les questions puis valide les
réponses SageMaker. `aws.py` centralise la création des clients AWS et `errors.py`
définit les erreurs applicatives.

La recherche dans la Knowledge Base utilise tous les énoncés des `sub_questions` et
les libellés des choix non binaires (autres que « oui » et « non »), en plus de la
question et du contexte visuel.
Pour le Decider, chaque `sub_question` devient une entrée de `questions` indexée
par son numéro sous forme de chaîne. Le type `choice` reçoit l'énoncé dans
`instructions` et les libellés dans le dictionnaire `criteria`. Une question
binaire dont les options sont « oui » et « non » utilise le type `noul`.
Pour un QCM à réponses multiples, le Decider renvoie les probabilités `choice`
par option; l'API sélectionne toutes celles dont la probabilité atteint le seuil
dynamique `1 / nombre d’options`. Les options retenues sont ajoutées dans
`selected_options`. La réponse complète du Decider conserve son objet `answers`.

## Téléversement direct avec une URL présignée

Demander une autorisation temporaire en envoyant le MIME type :

```json
{
  "content_type": "video/mp4"
}
```

La réponse de `POST /uploads` contient `upload_url`, `fields` et `s3_key`. Envoyer
ensuite un formulaire `multipart/form-data` à `upload_url`, en y ajoutant chaque
entrée de `fields` puis le fichier sous le champ `file`. Le navigateur doit utiliser
la méthode `POST` et ne doit pas définir lui-même l'en-tête `Content-Type` du
formulaire. L'URL expire après 5 minutes; le formulaire impose le type MIME demandé
et une taille entre 1 octet et 100 Mio. L'analyse des images est toutefois limitée à
4 Mio par image.

Une fois le téléversement S3 réussi, lancer l'analyse :

```json
{
  "content_type": "video/mp4",
  "s3_key": "requests/<clé-retournée-par-uploads>",
  "question": "Décris les événements observés."
}
```

`content_type` doit être l'un des types suivants : `image/jpeg`, `image/png`,
`image/gif`, `image/webp`, `video/mp4`, `video/mpeg`, `video/quicktime`,
`video/webm` ou `video/x-matroska`. Le champ `media_type` (`image` ou `video`) est
facultatif et, s'il est fourni, doit correspondre au type MIME.
Une image de plus de 4 Mio est refusée avec le statut HTTP 413. Si le modèle visuel
renvoie un type de question non pris en charge ou si le Decider renvoie une réponse
non JSON, l'API renvoie le statut HTTP 502.

Pour tester le flux depuis un navigateur, ouvrir `client-test.html`, sélectionner
un fichier puis cliquer sur « Téléverser et analyser ». La page utilise
automatiquement l'URL de l'API configurée dans le champ, demande une autorisation,
envoie le fichier vers S3 et affiche la réponse de `/query`.

La Lambda écrit dans CloudWatch des logs de début et de progression du traitement
avec le `request_id` et l'étape courante, sans journaliser le contenu du fichier ni
l'URL présignée. En cas d'erreur, le client reçoit un message et cet identifiant de
requête pour faciliter le rapprochement avec les logs. Un objet S3 absent renvoie
HTTP 404 avec une indication de vérification de la clé et du téléversement.
L'appel SageMaker journalise également sa durée, la taille du JSON et le nombre
de questions, sans écrire son contenu dans les logs.

`POST /query` exige une `s3_key` obtenue avec `POST /uploads`; l'envoi de média en
base64 n'est pas pris en charge. Pour un dossier d'images, le client doit obtenir
une autorisation et téléverser chaque image séparément, puis appeler `/query` une
fois par image. L'API ne regroupe pas encore les résultats d'un dossier en une seule
analyse.

La Lambda envoie au endpoint SageMaker un JSON de la forme
`{"state": "...", "questions": {"1": {"type": "choice", "instructions": "...", "criteria": {"Option A": "Candidat A", "Option B": "Candidat B"}}}}`.
Le modèle visuel est configuré par `VISION_MODEL_ID` (par défaut
`us.amazon.nova-lite-v1:0`). Le schéma exact de décision renvoyé par le endpoint
dépend de l'image Docker `strands-decider`.

> Les routes API n'ont pas encore d'authentification. La configuration CORS autorise
> actuellement toutes les origines pour faciliter le développement; avant la
> production, restreignez les origines aux domaines de l'application et ajoutez
> l'authentification et les protections contre l'abus. Une URL présignée est un
> jeton porteur temporaire: ne la journalisez pas et ne la partagez pas.

## Hébergement de l'interface React (WebStack) et déploiement

`WebStack` (`stacks/web_stack.py`) sert l'application React depuis un bucket S3
privé (tout accès public bloqué) derrière une distribution CloudFront avec
Origin Access Control. Les erreurs 403/404 sont réécrites vers `/index.html`
(statut 200) pour le routage SPA côté client. Le stack publie le domaine CloudFront
via le `CfnOutput` `WebDistributionDomain`.

Flux de déploiement :

1. Construire le bundle front dans `web/` AVANT la synthèse (le build n'est pas
   lancé pendant `cdk synth` pour garder la synthèse hermétique). `VITE_API_URL`
   doit pointer vers l'URL exposée par `ApiStack` (sortie
   `ApiEndpointUrl`sans `/query`) :

   ```bash
   cd web
   VITE_API_URL="https://<api-id>.execute-api.<region>.amazonaws.com" npm install
   VITE_API_URL="https://<api-id>.execute-api.<region>.amazonaws.com" npm run build
   ```

   `web/dist` doit exister avant `cdk synth WebStack` / `cdk deploy WebStack`
   (c'est la source du `BucketDeployment`).

2. Synthétiser puis déployer :

   ```bash
   uv run cdk synth WebStack
   uv run cdk deploy ApiStack WebStack
   ```

3. Récupérer le domaine CloudFront dans la sortie `WebDistributionDomain` et
   ouvrir l'application dans le navigateur.

### CORS vis-à-vis de l'origine CloudFront (NFR5)

Pour le hackathon, `ApiStack` conserve `allow_origins=['*']`. Restreindre
dynamiquement l'origine au domaine de la distribution CloudFront créerait une
dépendance circulaire au déploiement (`ApiStack` dépendrait du domaine généré par
`WebStack`, alors que l'URL de l'API est elle-même nécessaire au build front).
En production, remplacez `['*']` par le domaine CloudFront exact
(`https://<distribution>.cloudfront.net`) dans la configuration CORS d'`ApiStack`,
une fois ce domaine connu. Il s'agit d'une limitation assumée du prototype.

### Option de repli : Lambda Function URL

Le banc `bench/latency.py` échoue si le p95 horloge atteint le plafond de 29 s de
l'intégration API Gateway. Si la latence s'en approche, une OPTION de repli (non
construite, S7) consiste à exposer la même Lambda via une Function URL (plafond de
60 s) sans changer le code. Ce n'est qu'une piste documentée.

### Banc de latence

```bash
uv run python bench/latency.py --api <url> --image <path>
```

Le script enchaîne `/uploads` -> S3 -> `/query` N fois (5 par défaut) par mode,
relève la durée horloge et la mesure serveur `debug.elapsed_ms`, imprime
min/p50/p95 et un mini tableau comparé à « Nova décide tout », puis sort en code
non nul si le p95 atteint 29 s. Sans `--api`/`--image` (ou si l'image est absente),
il saute proprement. La mesure réelle contre le plafond de 29 s (NFR2) ne peut se
faire que contre une API déployée.
