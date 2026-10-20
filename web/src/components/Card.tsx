import type { Card as CardModel } from "../types";

interface CardProps {
  card: CardModel;
  kbExcerpt?: string;
  cardIndex?: number;
}

function kindLabel(kind: CardModel["kind"]): string {
  return kind === "allow_deny" ? "Intention" : "Question";
}

function percent(score: number): number {
  return Math.round(score * 100);
}

// Decorative check glyph for the selected option (aria-hidden).
function CheckGlyph() {
  return (
    <svg
      className="option-check"
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M3.5 8.5 L6.5 11.5 L12.5 4.5"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// Hero verdict icon — allow = check-in-circle, deny = slash-in-circle
// (aria-hidden; the verdict word is conveyed by the gauge aria-label + option).
function VerdictIcon({ verdict }: { verdict: "allow" | "deny" }) {
  return (
    <svg
      className="verdict-icon"
      width="44"
      height="44"
      viewBox="0 0 44 44"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="22" cy="22" r="18" stroke="currentColor" strokeWidth="3" />
      {verdict === "allow" ? (
        <path
          d="M13 22.5 L19 28.5 L31 15.5"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ) : (
        <line
          x1="14"
          y1="14"
          x2="30"
          y2="30"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
        />
      )}
    </svg>
  );
}

// Circular probability gauge. The ring sweep animates via stroke-dashoffset
// (CSS reads --ring-circ / --ring-offset).
function VerdictGauge({
  verdict,
  verdictLabel,
  verdictPct,
}: {
  verdict: "allow" | "deny";
  verdictLabel: string;
  verdictPct: number;
}) {
  const radius = 38;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - verdictPct / 100);
  const ringStyle = {
    "--ring-circ": `${circumference}`,
    "--ring-offset": `${offset}`,
  } as React.CSSProperties;

  return (
    <div className="verdict-gauge" data-verdict={verdict}>
      <svg
        viewBox="0 0 100 100"
        role="img"
        aria-label={`Probabilité ${verdictLabel} : ${verdictPct}%`}
      >
        <circle
          className="verdict-gauge-track"
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          strokeWidth="9"
        />
        <circle
          className="verdict-gauge-fill"
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          strokeWidth="9"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={ringStyle}
        />
      </svg>
      <span className="verdict-gauge-value">{verdictPct}%</span>
    </div>
  );
}

export default function Card({ card, kbExcerpt, cardIndex = 0 }: CardProps) {
  const isVerdict = card.kind === "allow_deny";

  // Verdict derivation (presentation only — no data change).
  const selected =
    card.options.find((o) => o.selected) ??
    [...card.options].sort((a, b) => b.score - a.score)[0];
  const verdictLabel = selected?.label ?? "";
  const verdictPct = selected ? percent(selected.score) : 0;
  const verdict: "allow" | "deny" =
    verdictLabel === "Autorisé" ? "allow" : "deny";

  const articleStyle = {
    "--card-index": cardIndex,
  } as React.CSSProperties;

  return (
    <article
      className="card"
      style={articleStyle}
      {...(isVerdict ? { "data-verdict": verdict } : {})}
    >
      <header className="card-header">
        <h3 className="card-title">{card.title}</h3>
        <span className="card-badge">{kindLabel(card.kind)}</span>
      </header>

      {isVerdict && selected ? (
        <div className="verdict-hero">
          <VerdictIcon verdict={verdict} />
          <VerdictGauge
            verdict={verdict}
            verdictLabel={verdictLabel}
            verdictPct={verdictPct}
          />
        </div>
      ) : null}

      <ul className="card-options">
        {card.options.map((option) => {
          const fillStyle = {
            "--fill": `${percent(option.score)}%`,
          } as React.CSSProperties;
          return (
            <li
              key={option.label}
              className={option.selected ? "option selected" : "option"}
            >
              <div className="option-head">
                <span className="option-label">
                  {option.selected ? <CheckGlyph /> : null}
                  {option.label}
                </span>
                <span className="option-score">{percent(option.score)}%</span>
              </div>
              <div
                className="score-bar"
                role="img"
                aria-label={`${option.label} : ${percent(option.score)}%`}
              >
                <div className="score-bar-fill" style={fillStyle} />
              </div>
            </li>
          );
        })}
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
