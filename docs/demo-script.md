# Script vidéo — RoadGuard (moins de 3 minutes)

Objectif : montrer les deux modes et le « même cerveau ». Répartition visée :
~70 % sur le flux Conduite, ~20 s sur le QCM, le reste en intro/conclusion.

---

## 0:00 – 0:20 · Intro (≈ 20 s)

- Une phrase de pitch : « RoadGuard regarde une scène routière et dit, intention par
  intention, ce qui est conforme au Code de la route. »
- Montrer l'écran avec le sélecteur **Examen / Conduite**.
- Annoncer le pattern : une **politique en forme fermée** (Policy) ; le modèle décrit,
  le Decider tranche.

## 0:20 – 2:05 · Flux Conduite (≈ 105 s, le cœur de la démo)

- Basculer sur **Conduite**.
- Téléverser une photo de scène routière (intersection avec piéton et panneau).
- Commenter les états de progression en direct : **perception → règlement → Decider**.
- À l'affichage :
  - lire le **résumé de scène** ;
  - montrer les **3 cartes d'intention** générées librement par le modèle au vu de la
    scène (pas une liste figée) ;
  - sur chaque carte, montrer `Autorisé` / `Interdit`, la **barre de score**
    (probabilité) et la sélection mise en évidence ;
  - pointer l'extrait de Knowledge Base qui justifie le contexte.
- Déplier le **panneau debug** : `visual_facts`, `knowledge_references`, `media_key`,
  et surtout **`elapsed_ms`** (durée serveur de l'appel Decider).

## 2:05 – 2:25 · QCM / Examen (≈ 20 s) — « même cerveau »

- Basculer sur **Examen**, téléverser une image de question.
- Montrer les cartes de QCM et les options retenues.
- Insister : c'est le **même cerveau** (le même `decide(...)` et le même endpoint
  Decider) ; seule la forme des questions change entre les deux modes.

## 2:25 – 2:50 · Conclusion (≈ 25 s)

- Rappeler le pattern **Policy** : perception sans jugement + Decider déterministe =
  verdict reproductible et auditable.
- Mentionner les limites assumées du prototype (CORS `*`, pas d'auth) et le durcissement
  prévu avant la production.
- Fin.

> Astuce tournage : préparer à l'avance les deux médias (scène de conduite + question
> d'examen) et une API déjà déployée pour éviter les temps morts pendant les appels.
