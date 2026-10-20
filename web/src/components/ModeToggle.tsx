import type { Mode } from "../types";

interface ModeToggleProps {
  mode: Mode;
  disabled?: boolean;
  onChange: (mode: Mode) => void;
}

// Decorative inline-SVG glyphs. aria-hidden so the text label stays the
// accessible name of each radio.
function ExamGlyph() {
  return (
    <svg
      className="mode-glyph"
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <rect
        x="3"
        y="2"
        width="10"
        height="12"
        rx="1.5"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <line x1="5.5" y1="5.5" x2="10.5" y2="5.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <line x1="5.5" y1="8" x2="10.5" y2="8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <line x1="5.5" y1="10.5" x2="8.5" y2="10.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

function DriveGlyph() {
  return (
    <svg
      className="mode-glyph"
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.4" />
      <circle cx="8" cy="8" r="1.6" fill="currentColor" />
      <line x1="8" y1="2.6" x2="8" y2="6.4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <line x1="3.3" y1="10.5" x2="6.6" y2="8.6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      <line x1="12.7" y1="10.5" x2="9.4" y2="8.6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

const OPTIONS: { value: Mode; label: string; Glyph: () => JSX.Element }[] = [
  { value: "exam", label: "Examen", Glyph: ExamGlyph },
  { value: "situation", label: "Conduite", Glyph: DriveGlyph },
];

export default function ModeToggle({
  mode,
  disabled,
  onChange,
}: ModeToggleProps) {
  return (
    <div
      className="mode-toggle"
      role="radiogroup"
      aria-label="Mode d'analyse"
    >
      {OPTIONS.map((option) => {
        const active = option.value === mode;
        const { Glyph } = option;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            className={active ? "mode-option active" : "mode-option"}
            disabled={disabled}
            onClick={() => onChange(option.value)}
          >
            <Glyph />
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
