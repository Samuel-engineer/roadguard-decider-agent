# Architecture — RoadGuard double mode

RoadGuard ajoute un second circuit, `situation`, à côté du circuit `exam` (QCM du
Code de la route) existant. Les deux circuits empruntent **un seul backbone Lambda
scripté** : il n'y a pas de boucle d'agent en production.

## Le double circuit sur un backbone unique

```
POST /query
   │
   ▼
extract_facts_from_media   (Bedrock Nova Lite — perception visuelle)
   │   selon le mode : schéma/outil exam  OU  schéma/outil situation
   ▼
_retrieve_knowledge        (Bedrock Knowledge Base — retrieve)
   │   selon le mode : requête exam (QCM)  OU  requête situation (scène + intentions)
   ▼
decide(facts, references)  (endpoint SageMaker temps réel — le Decider)
   │   un seul invoke_endpoint, quel que soit le mode
   ▼
build_response(...)        (projection unifiée {mode, cards, scene_summary, debug})
```

Le **seul point de branchement** est le champ `mode` de la requête (`exam` par
défaut, ou `situation`). Il sélectionne quatre choses et rien d'autre :

1. le schéma et le prompt du VLM (`circuits/exam.py` ou `circuits/situation.py`) ;
2. la construction de la requête Knowledge Base (`knowledge.py`) ;
3. le constructeur de questions du Decider (`_build_decider_questions` pour l'examen,
   `_build_situation_questions` pour la situation) ;
4. la projection de la réponse (`circuits/present.py`).

Tout le reste du backbone est identique entre les deux modes.

## Mode examen (`exam`)

Le VLM extrait un QCM structuré depuis le média (outil `extract_road_data`). La
Knowledge Base est interrogée avec les énoncés et les libellés de choix. Le Decider
reçoit des questions de type `choice` (choix simple ou multiple) et `noul`
(binaire oui/non), et renvoie des probabilités par option.

## Mode situation (`situation`)

Le VLM **décrit** la scène sans jamais la juger (outil `analyze_driving_situation`) :
`scene_summary`, `keywords`, `signals`, `road_users`, et surtout **exactement 3
intentions plausibles du conducteur**, générées librement par Nova au vu de la scène
(texte français libre, pas de liste fermée). Chaque intention devient une question
`noul` adressée au Decider dans un **unique** appel. Le Decider tranche la conformité
au Code de la route ; RoadGuard rend chaque verdict sous la forme de deux options,
`Autorisé` (score = probabilité `noul`) et `Interdit` (score = `1 - noul`).

## Le même cerveau pour les deux modes

Les deux modes appellent la **même** fonction `decide(facts, references,
runtime_client, *, mode=...)`. Le Decider SageMaker est donc le cerveau commun : seule
la forme des questions qu'on lui envoie change. C'est ce que montre la démo (« même
cerveau »).

## Pattern déclaré : Policy

Le pattern de soumission déclaré est **Policy** (voir
[`decisions.md`](decisions.md) et l'article Builder Center). La politique en forme
fermée est packagée dans `patterns/closed-form-policy/` avec deux variantes (`choice`
et `noul`) qui partagent un seul `ClosedFormPolicyHandler`. En production, la Lambda
appelle `decide(...)` directement, **sans** boucle d'agent ; l'intégration à un agent
Strands est démontrée séparément dans `examples/strands_agent.py`.

## Réponse unifiée

`build_response` produit toujours la même forme, quel que soit le mode :

```jsonc
{
  "mode": "exam" | "situation",
  "cards": [ { "id", "title", "kind", "options": [ { "label", "score", "selected" } ] } ],
  "scene_summary": "...",
  "debug": { "visual_facts", "knowledge_references", "media_key", "elapsed_ms" }
}
```

Les anciennes clés de haut niveau (`decision`, `visual_facts`, `knowledge_references`,
`media_key`) sont supprimées ; leur contenu brut survit sous `debug`.

## Transport

Le transport est **API Gateway HTTP API v2 uniquement** (routes `POST /query` et
`POST /uploads`). Aucune Lambda Function URL n'est construite. L'intégration est
plafonnée à 29 s ; un banc de latence (`bench/latency.py`) garde ce plafond. La
Function URL (60 s) reste une option documentée, non construite.
