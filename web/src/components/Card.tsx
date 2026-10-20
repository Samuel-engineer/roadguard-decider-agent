import type { Card as CardModel } from "../types";

interface CardProps {
  card: CardModel;
  kbExcerpt?: string;
}

function kindLabel(kind: CardModel["kind"]): string {
  return kind === "allow_deny" ? "Intention" : "Question";
}

function percent(score: number): number {
  return Math.round(score * 100);
}

export default function Card({ card, kbExcerpt }: CardProps) {
  return (
    <article className="card">
      <header className="card-header">
        <h3 className="card-title">{card.title}</h3>
        <span className="card-badge">{kindLabel(card.kind)}</span>
      </header>
      <ul className="card-options">
        {card.options.map((option) => (
          <li
            key={option.label}
            className={option.selected ? "option selected" : "option"}
          >
            <div className="option-head">
              <span className="option-label">{option.label}</span>
              <span className="option-score">{percent(option.score)}%</span>
            </div>
            <div
              className="score-bar"
              role="img"
              aria-label={`${option.label} : ${percent(option.score)}%`}
            >
              <div
                className="score-bar-fill"
                style={{ width: `${percent(option.score)}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
      {kbExcerpt ? (
        <p className="card-excerpt">
          <span className="card-excerpt-label">Référence Code de la route :</span>{" "}
          {kbExcerpt}
        </p>
      ) : null}
    </article>
  );
}
