import type { Mode } from "../types";

interface ModeToggleProps {
  mode: Mode;
  disabled?: boolean;
  onChange: (mode: Mode) => void;
}

const OPTIONS: { value: Mode; label: string }[] = [
  { value: "exam", label: "Examen" },
  { value: "situation", label: "Conduite" },
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
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
