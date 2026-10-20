// Dev-only visual preview harness — NOT part of the production entry.
// Mounted from main.tsx only when `import.meta.env.DEV && VITE_PREVIEW === "1"`,
// so Vite tree-shakes it out of the production build.
//
// Run it with:  VITE_PREVIEW=1 npm run dev
//
// It renders every visual state without a live backend so the redesign can be
// exercised in a browser: both modes, the Autorisé/Interdit verdict treatment,
// exam score bars + selection, the perception->règlement->Decider stepper with
// the active stage lit, the Uploader drag/has-file states, an error alert, the
// latence Decider chip, and the debug panel.
import { useState } from "react";
import type { Mode } from "../types";
import Logo from "../components/Logo";
import ModeToggle from "../components/ModeToggle";
import Uploader from "../components/Uploader";
import SceneSummary from "../components/SceneSummary";
import CardList from "../components/CardList";
import DebugPanel from "../components/DebugPanel";
import {
  examResponse,
  situationResponse,
  situationDenyResponse,
  mockErrorMessages,
} from "../test/mockResponses";

const STAGES = [
  { key: "authorizing", label: "perception" },
  { key: "uploading", label: "règlement" },
  { key: "analyzing", label: "Decider" },
];

function Stepper({ active }: { active: string }) {
  const order = ["authorizing", "uploading", "analyzing"];
  const activeIndex = order.indexOf(active);
  return (
    <ol className="progress" aria-label="Progression de l'analyse">
      {STAGES.map((stage) => {
        const i = order.indexOf(stage.key);
        const cls =
          i < activeIndex
            ? "progress-step complete"
            : i === activeIndex
              ? "progress-step active"
              : "progress-step";
        return (
          <li key={stage.key} className={cls}>
            <span className="progress-dot" aria-hidden="true" />
            <span className="progress-label">{stage.label}</span>
          </li>
        );
      })}
    </ol>
  );
}

function ResultBlock({
  mode,
  data,
}: {
  mode: Mode;
  data: typeof examResponse;
}) {
  return (
    <div className="app" data-mode={mode}>
      <main className="app-main">
        <h2 style={{ color: "var(--text-muted)", marginTop: 0 }}>
          {mode === "exam" ? "Mode Examen" : "Mode Conduite"}
        </h2>
        <div className="results">
          <div className="results-topline">
            <SceneSummary summary={data.scene_summary} />
            <span className="latency-chip" title="Temps de décision Strands Decider 2B">
              <span className="latency-dot" aria-hidden="true" />
              latence Decider&nbsp;<b>{data.debug.elapsed_ms}&nbsp;ms</b>
            </span>
          </div>
          <CardList
            cards={data.cards}
            mode={data.mode}
            references={data.debug.knowledge_references}
          />
          <DebugPanel debug={data.debug} />
        </div>
      </main>
    </div>
  );
}

export default function Preview() {
  const [mode, setMode] = useState<Mode>("exam");
  const [hasFile, setHasFile] = useState(false);

  const fakeFile = hasFile
    ? ({ name: "panneau-demo.jpg", type: "image/jpeg" } as File)
    : null;

  return (
    <div>
      <div className="app">
        <main className="app-main">
          <header className="app-header">
            <div className="brand">
              <Logo size={30} />
              <h1 className="wordmark">
                <span className="wm-road">Road</span>
                <span className="wm-guard">Guard</span>
              </h1>
            </div>
            <p className="tagline">Le copilote qui décide, règle en main.</p>
          </header>

          <p className="app-intro">
            Aperçu développeur — tous les états visuels (aucun backend requis).
          </p>

          <span className="field-label">Mode d'analyse</span>
          <ModeToggle mode={mode} onChange={setMode} />

          <Uploader
            file={fakeFile}
            previewUrl={null}
            onSelect={(f) => setHasFile(Boolean(f))}
          />
          <button
            type="button"
            className="submit-button"
            onClick={() => setHasFile((v) => !v)}
          >
            Basculer l'état du fichier
          </button>

          <Stepper active="uploading" />

          <div className="status" role="status" aria-live="polite" data-state="error">
            {mockErrorMessages.network}
          </div>
        </main>
      </div>

      <ResultBlock mode="exam" data={examResponse} />
      <ResultBlock mode="situation" data={situationResponse} />
      <ResultBlock mode="situation" data={situationDenyResponse} />
    </div>
  );
}
