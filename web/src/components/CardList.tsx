import type { Card as CardModel, KnowledgeReference } from "../types";
import Card from "./Card";

interface CardListProps {
  cards: CardModel[];
  mode: string;
  references: KnowledgeReference[];
}

export default function CardList({ cards, mode, references }: CardListProps) {
  if (cards.length === 0) {
    return null;
  }
  return (
    <section className="card-list" aria-label="Résultats de l'analyse">
      {cards.map((card, index) => {
        const kbExcerpt =
          mode === "situation" ? references[index]?.text : undefined;
        return (
          <Card
            key={card.id}
            card={card}
            kbExcerpt={kbExcerpt}
            cardIndex={index}
          />
        );
      })}
    </section>
  );
}
