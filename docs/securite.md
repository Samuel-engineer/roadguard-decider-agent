# Sécurité — RoadGuard double mode

Note de sécurité pour le prototype et les points à durcir avant une mise en
production.

## Token Hugging Face (Decider)

Le conteneur SageMaker du Decider charge le modèle via `huggingface_hub`, qui lit le
token depuis la variable d'environnement `HF_TOKEN` du processus.

- **Révoquer le token exposé.** Tout token Hugging Face ayant pu être exposé doit être
  **révoqué** sur Hugging Face et remplacé par un token neuf. Un token révoqué ne doit
  plus jamais servir.
- **Ne jamais committer le token.** Aucun littéral de token ne doit figurer dans le
  code suivi. Le token se fournit via un fichier `.env` local (non suivi) ou, mieux,
  via **AWS Secrets Manager** injecté dans l'environnement du conteneur.
- **Lecture par l'environnement.** `stacks/code/serve.py` lit `HF_TOKEN` via
  `os.getenv("HF_TOKEN")` et `stacks/config.py` via
  `field(default_factory=lambda: os.getenv("HF_TOKEN", ""))`. La valeur n'est jamais
  journalisée ni émise dans un `CfnOutput`.
- **Ne jamais journaliser le token.** `serve.py` ne doit pas écrire le token dans les
  logs (`logger.info` / `print`).

## CORS

`ApiStack` conserve `allow_origins=['*']` pour le hackathon, afin de simplifier le
développement. **Avant la production**, restreindre `allow_origins` au domaine exact de
la distribution CloudFront (`https://<distribution>.cloudfront.net`). Fixer l'origine
au moment du déploiement crée une dépendance circulaire (l'URL de l'API est nécessaire
au build front) ; c'est une limitation assumée du prototype, à résoudre une fois le
domaine connu.

## Authentification et abus

Les routes `/query` et `/uploads` n'ont **pas encore** d'authentification. Avant la
production :

- ajouter une authentification (par exemple un autorisateur JWT / Cognito sur l'API) ;
- ajouter des protections contre l'abus (limitation de débit, quotas).

## URL présignées

Une URL présignée S3 est un **jeton porteur temporaire** (valable 5 minutes, type MIME
et taille imposés). Elle ne doit jamais être journalisée ni partagée. La Lambda
journalise le `request_id` et l'étape courante, mais ni le contenu du fichier ni l'URL
présignée.

## Journalisation

L'appel SageMaker journalise sa durée, la taille du JSON et le nombre de questions,
sans écrire le contenu de la réponse (le dump complet de la réponse Decider a été
retiré). Aucun secret ni contenu média ne doit apparaître dans les logs.
