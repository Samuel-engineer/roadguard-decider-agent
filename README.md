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
`us.amazon.nova-pro-v1:0`). Le schéma exact de décision renvoyé par le endpoint
dépend de l'image Docker `strands-decider`.

> Les routes API n'ont pas encore d'authentification. La configuration CORS autorise
> actuellement toutes les origines pour faciliter le développement; avant la
> production, restreignez les origines aux domaines de l'application et ajoutez
> l'authentification et les protections contre l'abus. Une URL présignée est un
> jeton porteur temporaire: ne la journalisez pas et ne la partagez pas.