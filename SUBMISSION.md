# Dossier de soumission — Strands Decider Agent Hackathon

Point d'entrée unique pour finaliser la soumission. Tout le volet **code** est prêt ;
ce document liste le volet **non-code** restant et fournit le texte à coller.

> Date limite : **23 octobre 2026, 23 h 59 PT**. Prix : 5 000 $ de crédits AWS + swag.

---

## 1. Les 3 livrables obligatoires (PASS/FAIL)

Une soumission à laquelle il manque l'un des trois n'est pas jugée, quelle que soit sa qualité.

| # | Livrable | État | Action |
|---|----------|------|--------|
| 1 | Article publié sur **AWS Builder Center** | ⏳ Rédigé, à publier | Copier `docs/builder-center-article.md` sur Builder Center |
| 2 | **Repo public** + code + pattern réutilisable + licence OSI | ⏳ Licence OK, repo à rendre public | Rendre le dépôt public (licence Apache-2.0 déjà présente) |
| 3 | **Vidéo** < 3 min montrant l'agent et sa décision Decider | ⏳ Script prêt, à tourner | Suivre `docs/demo-script.md`, uploader sur YouTube/Vimeo |

Tags requis sur la soumission : **`#strands-decider-2b`** + **`#policy`**.

---

## 2. Checklist de finalisation (dans l'ordre)

### A. Déploiement propre (ordre important)
L'ID de l'API Gateway change à chaque recréation de stack. Pour éviter que le front pointe
vers un endpoint mort, respecter cet ordre :

1. `uv run cdk deploy --all` (ou au minimum `ApiStack`, `KnowledgeBaseStack`, `WebStack`).
2. Relever la sortie `ApiEndpointUrl` du déploiement.
3. Mettre à jour `web/.env` → `VITE_API_URL = <nouvelle URL>` si elle a changé.
4. Réingestion KB (voir `docs/rag-reingestion.md`) : `aws bedrock-agent start-ingestion-job …`.
5. `cd web; npm run build` puis `uv run cdk deploy WebStack` pour pousser le build à jour.
6. Vérifier le front live et un flux conduite de bout en bout.

### B. Sécurité (à faire absolument)
- [ ] **Révoquer / régénérer le token Hugging Face** exposé précédemment dans l'arbre de
      travail (compte HF → Access Tokens). Il n'est plus dans le code, mais a été exposé.
- [ ] Confirmer que `.env` n'est pas suivi par git (déjà `.gitignore`).

### C. Mesures (bonus de notation — recommandé)
- [ ] Lancer `uv run python bench/latency.py` en **live** et coller les chiffres dans
      `docs/metrics.md` (remplacer `<à remplir après un run live>`).
- [ ] Lancer `uv run python bench/quality_eval.py` en **live** sur `samples/` et remplir
      `docs/quality-eval.md`.
- [ ] Reporter dans l'article le comparatif latence Decider vs « Nova décide tout » et la
      gestion des cas à faible confiance (déjà décrite dans l'article).

### D. Publication
- [ ] Publier l'article (`docs/builder-center-article.md`) sur Builder Center.
- [ ] Rendre le repo public.
- [ ] Tourner + uploader la vidéo (`docs/demo-script.md`).
- [ ] Renseigner les liens dans `README.md` (`<lien à ajouter>`) et dans le formulaire.
- [ ] Ajouter les tags `#strands-decider-2b` et `#policy`.

---

## 3. Résumé prêt à coller (formulaire / article)

**Nom :** RoadGuard

**Pitch :** RoadGuard regarde une scène routière (photo ou vidéo) et dit, intention par
intention, ce qui est conforme au Code de la route. Deux modes partagent un même cerveau :
*Examen* (QCM tranché par le Decider) et *Conduite* (le modèle de vision propose 3 intentions
libres, le Decider juge la conformité de chacune).

**Décision confiée à Strands Decider 2B :** une **classification en forme fermée** (Policy).
Le modèle de vision (Bedrock Nova Lite) décrit la scène et propose des intentions mais ne juge
jamais la légalité ; le Decider 2B tranche chaque intention sur un jeu de questions fermé
(`noul` allow/deny en conduite, `choice` en examen). Verdict reproductible et auditable.

**Partie générative (Bedrock) :** Nova Lite pour la perception visuelle + Knowledge Base
(Code de la route) pour le contexte réglementaire.

**Pattern réutilisable :** `patterns/closed-form-policy/` — question(s) typée(s) + jeu
d'options, câblage `ClosedFormPolicyHandler` qui place la décision dans le chemin d'outil d'un
agent Strands, README d'utilisation. Exemple exécutable : `examples/strands_agent.py`.

**Pattern déclaré :** Policy. **Tags :** `#strands-decider-2b` `#policy`.

**Dépôt :** `<lien repo public à ajouter>`
**Article Builder Center :** `<lien à ajouter>`
**Vidéo :** `<lien à ajouter>`

---

## 4. Où est quoi dans le dépôt

| Élément | Chemin |
|---------|--------|
| Backbone Lambda (perception → KB → decide → présentation) | `functions/` |
| Pattern réutilisable Policy | `patterns/closed-form-policy/` |
| Exemple agent Strands exécutable | `examples/strands_agent.py` |
| UI Vite/React | `web/` |
| Infra CDK (API, KB, SageMaker, S3/CloudFront) | `stacks/`, `app.py` |
| Article Builder Center | `docs/builder-center-article.md` |
| Script vidéo | `docs/demo-script.md` |
| Procédure de réingestion KB | `docs/rag-reingestion.md` |
| Bancs de mesure (latence, qualité) | `bench/latency.py`, `bench/quality_eval.py` |
| Images de démonstration | `samples/` |
