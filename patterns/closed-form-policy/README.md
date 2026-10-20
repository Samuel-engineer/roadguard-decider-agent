# Politique déclarée en forme fermée (Closed-Form Policy)

Ce dossier décrit un *pattern* réutilisable : une **politique déclarée en forme
fermée** branchée sur un agent [Strands](https://pypi.org/project/strands-agents/).
Le principe : au lieu de laisser le modèle décider librement, on fait classer la
scène perçue par un **Decider** déterministe (un ensemble fermé de questions),
puis on autorise ou refuse l'action de l'agent selon le verdict.

## Pourquoi « en forme fermée » ?

Le modèle de perception (VLM) ne juge rien : il décrit ce qu'il voit et propose
des intentions. C'est le Decider qui tranche, sur un **jeu de questions fermé**
(oui/non ou choix). Le verdict est donc reproductible, auditable, et indépendant
de la formulation libre du modèle.

## Les deux variantes

Un **seul** handler, `ClosedFormPolicyHandler`, sert les deux variantes. Elles
ne diffèrent que par le `mode` transmis au `decide` partagé :

| Variante | Mode       | Questions                              | Cartes émises                                   |
|----------|------------|----------------------------------------|-------------------------------------------------|
| `choice` | `exam`     | QCM (choix simple ou multiple)         | `kind=choice`, une par sous-question            |
| `noul`   | `situation`| un oui/non par intention proposée      | `kind=allow_deny` (`Autorisé` / `Interdit`)     |

- `variants/choice.yaml` — examen du Code de la route.
- `variants/noul.yaml` — situation de conduite, 3 intentions libres.

La métadonnée déclarative est dans `recipe.yaml` ; le cœur est dans
`handler.py`.

## Architecture : un cœur neutre, un adaptateur mince

`handler.py` est volontairement découpé en deux couches :

1. **Cœur neutre** — `evaluate_policy(facts, references, runtime, *, mode, decide)`
   renvoie un `PolicyOutcome(allow, reason, cards, decision)`. Il n'importe
   JAMAIS `strands` et ne crée aucun client AWS (le `decide` et le client sont
   injectés). C'est ce cœur qui produit la classification en forme fermée.

2. **Adaptateur mince** — `ClosedFormPolicyHandler` est la seule couche qui
   connaît `strands`. Surface confirmée contre **strands-agents 1.61.1** :
   - classe de base : `strands.interventions.InterventionHandler` ;
   - méthode surchargée : `before_tool_call(self, event, **kwargs)` ;
   - actions de retour : `strands.interventions.Proceed` / `Deny`.

   Si l'API de Strands évolue, **seule cette classe change** : `evaluate_policy`
   et `decide` restent intacts.

## Réutiliser le handler dans VOTRE agent Strands (sans RoadGuard)

Le handler n'a besoin que d'un `decide` injecté et d'un client « runtime » (le
transport vers votre moteur de décision). Rien n'oblige à utiliser le reste de
RoadGuard.

```python
from strands import Agent

import sys
sys.path.insert(0, "patterns/closed-form-policy")
from handler import ClosedFormPolicyHandler  # noqa: E402


def my_decide(facts, references, runtime, *, request_id=None, mode="exam"):
    """Votre propre moteur de décision.

    Doit renvoyer un tuple ``(decision, elapsed_ms)`` où ``decision`` contient
    un objet ``answers`` indexé par clé de question (voir variants/*.yaml).
    """
    ...
    return decision, elapsed_ms


handler = ClosedFormPolicyHandler(
    variant="noul",            # ou "choice"
    decide=my_decide,
    runtime=my_runtime_client,  # votre transport (peut être un stub en test)
)

agent = Agent(
    model=my_model,
    tools=[my_tool],
    interventions=[handler],
)

agent("Analyse la scène et propose une action")
# Après le tour, les cartes de la décision sont disponibles :
print(handler.last_outcome.cards)
```

Vous pouvez aussi classer une scène **sans** passer par un tour d'agent, en
appelant directement `handler.evaluate(facts)` (utile pour les tests et les
traitements batch).

Un exemple complet et exécutable hors-ligne (modèle et client factices) est
fourni dans [`examples/strands_agent.py`](../../examples/strands_agent.py).

> `strands-agents` est une dépendance **du groupe `dev` uniquement** : elle
> n'est jamais embarquée dans le bundle Lambda `functions/`.
