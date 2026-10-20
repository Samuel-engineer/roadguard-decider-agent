# Décisions arrêtées — RoadGuard double mode

Ce journal recense les décisions verrouillées (S1 à S7) et leur justification. Elles
font autorité : toute implémentation s'y conforme.

## S1 — Les intentions de situation sont générées librement

Le VLM génère **exactement 3** intentions plausibles du conducteur, sous forme de
libellés français libres, au vu de la scène. Elles ne sont **pas** contraintes à une
liste fixe (pas d'énumération `stop`/`proceed`/`turn_left`).

*Justification :* une liste fermée ne couvrirait pas la diversité des situations
réelles ; laisser Nova proposer les intentions au vu de la scène rend le mode ouvert
et réaliste. Le nombre est fixé à 3 pour garder une lecture claire et un seul appel
Decider.

## S2 — Nova ne juge jamais la légalité

Le prompt du VLM interdit explicitement tout jugement de type « autorisé / interdit »,
« légal / illégal », « obligatoire », « a le droit ». Nova **perçoit** et **propose** ;
c'est le **Decider** qui juge la conformité au Code de la route.

*Justification :* séparer perception et verdict rend la décision reproductible,
auditable, et indépendante de la formulation libre du modèle de vision. C'est le cœur
du pattern Policy en forme fermée.

## S3 — Un seul appel Decider

Les 3 intentions partent en questions `noul` dans un **unique** appel
`invoke_endpoint`, réutilisant le contrat de fil existant du Decider.

*Justification :* un appel groupé limite la latence (plafond API Gateway à 29 s) et le
coût, et garde la même sémantique que le mode examen.

## S4 — La réponse unifiée remplace les anciennes clés

`decision`, `visual_facts`, `knowledge_references`, `media_key` sont retirées du
niveau supérieur ; les données brutes survivent sous `debug`.

*Justification :* l'UI a besoin d'une forme stable et orientée affichage (`cards`,
`scene_summary`) ; les internes restent disponibles pour le débogage sans polluer la
vue principale.

## S5 — Le pattern déclaré est Policy uniquement

Un seul recipe, `patterns/closed-form-policy/`, avec deux variantes d'instanciation
(`choice` pour l'examen, `noul` pour la situation) partageant le même
`InterventionHandler`. On ne crée **pas** `patterns/guardrails/`.

*Justification :* la soumission déclare un seul pattern pour rester lisible et honnête.
Le handler se place dans le chemin d'outil de l'agent, comme un garde, mais il reste la
**même décision Policy en forme fermée** — ce n'est donc pas un second pattern
Guardrails.

## S6 — Pas de boucle d'agent en production

La Lambda appelle directement une fonction partagée `decide(facts, references)`.
`examples/strands_agent.py` doit être réellement exécutable et est le **seul** endroit
qui importe `strands-agents`. `strands-agents` est une dépendance optionnelle / de
développement et ne doit jamais entrer dans le bundle Lambda (`functions/`).

*Justification :* la production reste simple, rapide et déterministe (pas de boucle de
raisonnement) ; l'intégration agent est démontrée à part pour prouver que le même
`decide` sert de politique dans un agent Strands.

## S7 — Le transport est API Gateway uniquement

Aucune Lambda Function URL n'est construite. Un banc de latence garde le plafond de
29 s de l'intégration HTTP API. La Function URL (60 s) est documentée comme une
**option** seulement.

*Justification :* API Gateway suffit pour le prototype et garde CORS et le routage au
même endroit. La Function URL n'est envisagée que si le banc montre un p95 proche du
plafond — c'est une piste, pas une implémentation.

---

## Limites assumées du prototype

- **CORS `*`.** `ApiStack` conserve `allow_origins=['*']` pour faciliter le
  développement et le hackathon. À durcir avant la production (voir
  [`securite.md`](securite.md)).
- **Pas d'authentification.** Les routes `/query` et `/uploads` n'ont pas encore
  d'authentification ni de protection contre l'abus.
- **Token Hugging Face.** Le token du Decider doit être révoqué et fourni via
  l'environnement / Secrets Manager (voir [`securite.md`](securite.md)).
