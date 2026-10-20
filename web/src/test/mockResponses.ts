import type { UnifiedResponse } from "../types";

export const examResponse: UnifiedResponse = {
  mode: "exam",
  cards: [
    {
      id: "1",
      title: "Que devez-vous faire à l'approche de ce panneau ?",
      kind: "choice",
      options: [
        { label: "Ralentir", score: 0.72, selected: true },
        { label: "Accélérer", score: 0.1, selected: false },
        { label: "Maintenir l'allure", score: 0.18, selected: false },
      ],
    },
  ],
  scene_summary: "Un panneau de limitation de vitesse sur une route de campagne.",
  debug: {
    visual_facts: { scene_summary: "panneau" },
    knowledge_references: [{ text: "Article R413-1", score: 0.9, location: null }],
    media_key: "uploads/exam.jpg",
    elapsed_ms: 1234,
  },
};

export const situationResponse: UnifiedResponse = {
  mode: "situation",
  cards: [
    {
      id: "1",
      title: "Le conducteur s'engage dans l'intersection.",
      kind: "allow_deny",
      options: [
        { label: "Autorisé", score: 0.8, selected: true },
        { label: "Interdit", score: 0.2, selected: false },
      ],
    },
  ],
  scene_summary: "Une intersection avec un feu tricolore au vert.",
  debug: {
    visual_facts: { scene_summary: "intersection" },
    knowledge_references: [
      { text: "Le feu vert autorise le passage.", score: 0.88, location: null },
    ],
    media_key: "uploads/situation.jpg",
    elapsed_ms: 2048,
  },
};

// Additive dev/preview fixture exercising the DENY verdict hero (Interdit
// selected). Not imported by the existing Card tests.
export const situationDenyResponse: UnifiedResponse = {
  mode: "situation",
  cards: [
    {
      id: "1",
      title: "Le conducteur franchit la ligne continue pour doubler.",
      kind: "allow_deny",
      options: [
        { label: "Interdit", score: 0.91, selected: true },
        { label: "Autorisé", score: 0.09, selected: false },
      ],
    },
    {
      id: "2",
      title: "Le conducteur attend derrière le véhicule lent.",
      kind: "allow_deny",
      options: [
        { label: "Autorisé", score: 0.86, selected: true },
        { label: "Interdit", score: 0.14, selected: false },
      ],
    },
    {
      id: "3",
      title: "Le conducteur accélère à l'approche du virage sans visibilité.",
      kind: "allow_deny",
      options: [
        { label: "Interdit", score: 0.77, selected: true },
        { label: "Autorisé", score: 0.23, selected: false },
      ],
    },
  ],
  scene_summary:
    "Route de montagne à double sens, ligne continue, visibilité réduite.",
  debug: {
    visual_facts: { scene_summary: "ligne continue, virage" },
    knowledge_references: [
      {
        text: "Il est interdit de franchir une ligne continue pour dépasser.",
        score: 0.93,
        location: null,
      },
      {
        text: "Maintenir une distance de sécurité derrière le véhicule qui précède.",
        score: 0.81,
        location: null,
      },
      {
        text: "Adapter sa vitesse à la visibilité et à la configuration de la route.",
        score: 0.79,
        location: null,
      },
    ],
    media_key: "uploads/situation-deny.jpg",
    elapsed_ms: 1620,
  },
};

// Exact error strings App can surface (reused verbatim — no new copy).
export const mockErrorMessages = {
  network:
    "Erreur réseau. Vérifiez votre connexion et la configuration CORS de l'API/S3.",
  http404: "Erreur HTTP 404.",
} as const;
