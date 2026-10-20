// src/components/Logo.tsx — ORIGINAL mark, no trademarks.
// A rounded shield (safety) whose interior negative space forms a forward
// chevron / road vanishing point (guidance). The shield stroke uses the neutral
// system accent; the road/chevron uses the active mode accent so the mark
// recolors amber <-> teal with the mode.
interface LogoProps {
  size?: number;
}

export function Logo({ size = 28 }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      role="img"
      aria-label="Logo RoadGuard"
      focusable="false"
    >
      {/* shield outline */}
      <path
        d="M16 2.5 L27 6.2 V15 C27 23 21.5 27.8 16 29.5 C10.5 27.8 5 23 5 15 V6.2 Z"
        fill="none"
        stroke="var(--accent-system)"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      {/* road: two converging edges toward a vanishing point */}
      <path
        d="M11 24 L14.6 13 H17.4 L21 24"
        fill="none"
        stroke="var(--accent)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* center dashes */}
      <line
        x1="16"
        y1="22"
        x2="16"
        y2="20"
        stroke="var(--accent)"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <line
        x1="16"
        y1="17.5"
        x2="16"
        y2="15.5"
        stroke="var(--accent)"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default Logo;
