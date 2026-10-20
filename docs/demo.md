# Script de démonstration — RoadGuard double mode

Ce document décrit le déroulé d'une démonstration interactive de l'application (UI
React + API). Pour le script de la vidéo de soumission (moins de 3 minutes), voir
[`demo-script.md`](demo-script.md).

## Préparation

1. Déployer l'API (`ApiStack`) et récupérer l'URL `/query` (sortie `ApiEndpointUrl`).
2. Construire et déployer le front (`web/` puis `WebStack`), ou ouvrir le repli
   `client-test.html`. Voir le README racine pour la procédure complète.
3. Avoir sous la main une photo de scène routière (intersection, piéton, panneau) et,
   éventuellement, une image de question d'examen.

## Déroulé

### 1. Basculer le mode

Dans l'UI, utiliser le sélecteur Examen / Conduite. Le défaut est **Examen**.
Montrer que le même écran sert les deux circuits ; seul le mode change.

### 2. Téléverser une photo

Déposer ou capturer une image. L'UI enchaîne automatiquement :

- **perception** — demande d'autorisation `/uploads`, envoi direct vers S3 ;
- **règlement** — appel `/query`, extraction des faits (Nova) puis récupération
  Knowledge Base ;
- **Decider** — classement en forme fermée.

Les états de progression sont affichés (`perception → règlement → Decider`).

### 3. Lire les cartes et les scores

- **Mode Conduite (`situation`)** : 3 cartes d'intention, chacune avec deux options
  `Autorisé` / `Interdit`, leur probabilité (barre de score) et la sélection mise en
  évidence. Un extrait de la Knowledge Base justifie le contexte.
- **Mode Examen (`exam`)** : une carte par sous-question, avec les options du QCM,
  leur score, et les options retenues surlignées.

Le résumé de scène (`scene_summary`) s'affiche au-dessus des cartes. L'UI ne montre
jamais le JSON brut comme vue principale.

### 4. Montrer le panneau debug et `elapsed_ms`

Déplier le panneau debug (replié par défaut). Il expose les internes bruts :

- `visual_facts` — la sortie complète du VLM ;
- `knowledge_references` — les passages récupérés de la Knowledge Base ;
- `media_key` — la clé S3 de la requête ;
- `elapsed_ms` — la durée mesurée côté serveur pour l'appel Decider.

C'est le moment de souligner le « même cerveau » : les deux modes passent par le même
`decide(...)` ; seule la forme des questions change.
