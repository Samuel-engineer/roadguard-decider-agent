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
