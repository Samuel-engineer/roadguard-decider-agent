# RoadGuard : une politique en forme fermée pour juger la conduite

## Le pitch

RoadGuard analyse une scène routière (photo ou vidéo) et dit, intention par
intention, ce qui est conforme au Code de la route. L'application a deux modes qui
partagent un même cerveau :

- **Examen** — un QCM du Code de la route, extrait de l'image, est tranché par le
  Decider.
- **Conduite** — au vu de la scène, le modèle de vision propose 3 intentions
  plausibles du conducteur ; le Decider juge chacune.

## Le pattern déclaré : Policy

Le pattern de soumission déclaré est **Policy**. L'idée : plutôt que de laisser le
modèle décider librement, on fait classer la scène perçue par un **Decider**
déterministe, sur un jeu de questions fermé (oui/non ou choix). Le verdict est donc
reproductible, auditable, et indépendant de la formulation libre du modèle.

Le modèle de vision (Nova Lite) ne juge jamais : il **décrit** la scène et **propose**
des intentions. C'est le Decider qui tranche la conformité. Cette séparation
perception / verdict est le cœur du pattern.

La politique est packagée dans `patterns/closed-form-policy/`, avec deux variantes
(`choice` pour l'examen, `noul` pour la situation) qui partagent un unique
`ClosedFormPolicyHandler`. Le même `decide(...)` sert les deux modes : c'est le même
cerveau.

Le handler est la même décision Policy en forme fermée posée dans le chemin d'outil de
l'agent, comme un garde — mais cela reste **un seul pattern Policy**, pas un pattern
Guardrails distinct : nous ne cochons pas Guardrails comme pattern de soumission et ne
créons pas de `patterns/guardrails/`.

## En production : pas de boucle d'agent

En production, la Lambda appelle `decide(facts, references)` **directement**, sans
boucle d'agent : perception (Nova) → récupération Knowledge Base → Decider →
réponse unifiée. L'intégration à un agent Strands est démontrée séparément et de
façon réellement exécutable dans `examples/strands_agent.py` ; `strands-agents` reste
une dépendance de développement et n'entre jamais dans le bundle Lambda.

## Mesures

Les mesures de latence sont tenues à part dans [`metrics.md`](metrics.md), afin de
ne pas recopier de chiffres dans cet article. Le banc `bench/latency.py` compare
explicitement **Decider en forme fermée vs Nova décide tout** : d'un côté le chemin
mesuré (Decider déterministe + RAG), de l'autre la baseline mono-appel VLM « Nova
décide tout », qui n'est pas mesurée par ce banc et reste donc `n/a`.

`metrics.md` présente un tableau **par mode** (`exam` et `situation`) avec les
colonnes `min`, `p50`, `p95`, `mean`, `max` en millisecondes, ainsi que des
placeholders `<à remplir après un run live>` tant qu'aucun run réel contre une API
déployée n'a été effectué. On s'y réfère pour les chiffres plutôt que de les
dupliquer ici.

## Cas limites / faible confiance

Le traitement des cas de faible confiance est entièrement déterministe et ancré dans
`functions/core/decider.py::_select_decider_options` :

- **Questions binaires (`noul`).** Le seuil est fixe à **0.5** : si la probabilité
  renvoyée est `>= 0.5`, l'option « vraie » est retenue (verdict autorisé / `true`),
  sinon l'option « fausse ». Le seuil utilisé est écrit dans `answer['threshold']` et
  l'option retenue dans `answer['selected_options']`.
- **QCM à réponses multiples (`multiple_choice`).** Le seuil est dynamique, égal à
  **`1 / nombre d'options`** : toute option dont la probabilité atteint ce seuil est
  ajoutée à `answer['selected_options']`, et le seuil retenu est exposé dans
  `answer['threshold']`.

Autrement dit, le seuil appliqué et les options sélectionnées sont systématiquement
surfacés dans la réponse. Le code ne fait **pas** d'abstention ni de « je ne sais
pas » : il applique le seuil et reporte le résultat tel quel.

## Limites assumées du prototype

- **CORS `*`.** L'API autorise toutes les origines pour faciliter le développement ;
  à restreindre au domaine CloudFront avant la production.
- **Pas d'authentification.** Les routes `/query` et `/uploads` ne sont pas encore
  protégées.

Détails techniques : [`architecture.md`](architecture.md),
[`decisions.md`](decisions.md) et [`securite.md`](securite.md).
