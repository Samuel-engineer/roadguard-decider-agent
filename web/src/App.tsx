import { useEffect, useState } from "react";
import Logo from "./components/Logo";
import ModeToggle from "./components/ModeToggle";
import Uploader from "./components/Uploader";
import SceneSummary from "./components/SceneSummary";
import CardList from "./components/CardList";
import DebugPanel from "./components/DebugPanel";
import { ApiError, getUploadAuth, query, uploadToS3 } from "./api";
import { MAX_IMAGE_BYTES, MAX_UPLOAD_BYTES, SUPPORTED_TYPES } from "./constants";
import type { Mode, UnifiedResponse } from "./types";

type Status =
  | "idle"
  | "authorizing"
  | "uploading"
  | "analyzing"
  | "done"
  | "error";

const STAGES: { key: Status; label: string }[] = [
  { key: "authorizing", label: "perception" },
  { key: "uploading", label: "règlement" },
  { key: "analyzing", label: "Decider" },
];

const STATUS_MESSAGES: Record<Status, string> = {
  idle: "",
  authorizing: "Étape 1/3 : demande d'autorisation à l'API…",
  uploading: "Étape 2/3 : envoi direct du fichier vers S3…",
  analyzing: "Étape 3/3 : analyse du fichier…",
  done: "Analyse terminée.",
  error: "",
};

function validateFile(file: File): string | null {
  if (!SUPPORTED_TYPES.has(file.type)) {
    return `Type de fichier non pris en charge : ${file.type || "inconnu"}.`;
  }
  const limit = file.type.startsWith("image/")
    ? MAX_IMAGE_BYTES
    : MAX_UPLOAD_BYTES;
  if (file.size > limit) {
    return file.type.startsWith("image/")
      ? "Cette image dépasse la limite d'analyse de 4 Mio."
      : "Cette vidéo dépasse la limite de téléversement de 100 Mio.";
  }
  return null;
}

function stageState(stage: Status, current: Status): string {
  const order = ["authorizing", "uploading", "analyzing"];
  const stageIndex = order.indexOf(stage);
  const currentIndex = order.indexOf(current);
  if (current === "done") {
    return "progress-step complete";
  }
  if (currentIndex === stageIndex) {
    return "progress-step active";
  }
  if (currentIndex > stageIndex) {
    return "progress-step complete";
  }
  return "progress-step";
}

export default function App() {
  const [mode, setMode] = useState<Mode>("exam");
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [result, setResult] = useState<UnifiedResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const apiUrl = import.meta.env.VITE_API_URL ?? "";
  const busy =
    status === "authorizing" ||
    status === "uploading" ||
    status === "analyzing";

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function handleSelect(next: File | null) {
    setFile(next);
    setResult(null);
    setError(null);
    setStatus("idle");
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setResult(null);
    setError(null);

    if (!file) {
      setStatus("error");
      setError("Sélectionnez un fichier.");
      return;
    }
    const validationError = validateFile(file);
    if (validationError) {
      setStatus("error");
      setError(validationError);
      return;
    }

    try {
      setStatus("authorizing");
      const auth = await getUploadAuth(file.type);

      setStatus("uploading");
      await uploadToS3(auth, file);

      setStatus("analyzing");
      const analysis = await query(mode, auth.s3_key, auth.content_type);

      setResult(analysis);
      setStatus("done");
    } catch (err) {
      setStatus("error");
      if (err instanceof ApiError) {
        const requestId = (err.payload as { request_id?: string })?.request_id;
        const statusPart = err.status ? ` (HTTP ${err.status})` : "";
        const ref = requestId ? ` Référence : ${requestId}.` : "";
        setError(`${err.operation} : ${err.message}${statusPart}${ref}`);
      } else if (err instanceof TypeError) {
        setError(
          "Erreur réseau. Vérifiez votre connexion et la configuration CORS de l'API/S3.",
        );
      } else {
        setError(err instanceof Error ? err.message : String(err));
      }
    }
  }

  const statusMessage =
    status === "error" && error ? error : STATUS_MESSAGES[status];

  return (
    <div className="app" data-mode={mode}>
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
          Sélectionnez une image ou une vidéo, choisissez le mode, puis lancez
          l'analyse.
        </p>

        {!apiUrl ? (
          <p className="status" data-state="error">
            VITE_API_URL n'est pas configurée.
          </p>
        ) : null}

        <form onSubmit={handleSubmit}>
          <span className="field-label">Mode d'analyse</span>
          <ModeToggle mode={mode} disabled={busy} onChange={setMode} />

          <Uploader
            file={file}
            previewUrl={previewUrl}
            disabled={busy}
            onSelect={handleSelect}
          />

          <button className="submit-button" type="submit" disabled={busy}>
            Téléverser et analyser
          </button>
        </form>

        {busy ? (
          <ol className="progress" aria-label="Progression de l'analyse">
            {STAGES.map((stage) => (
              <li key={stage.key} className={stageState(stage.key, status)}>
                <span className="progress-dot" aria-hidden="true" />
                <span className="progress-label">{stage.label}</span>
              </li>
            ))}
          </ol>
        ) : null}

        <div
          className="status"
          role="status"
          aria-live="polite"
          data-state={status}
        >
          {statusMessage}
        </div>

        {result ? (
          <div className="results">
            <div className="results-topline">
              <SceneSummary summary={result.scene_summary} />
              <span
                className="latency-chip"
                title="Temps de décision Strands Decider 2B"
              >
                <span className="latency-dot" aria-hidden="true" />
                latence Decider&nbsp;<b>{result.debug.elapsed_ms}&nbsp;ms</b>
              </span>
            </div>
            <CardList
              cards={result.cards}
              mode={result.mode}
              references={result.debug.knowledge_references}
            />
            <DebugPanel debug={result.debug} />
          </div>
        ) : null}

        <footer className="app-footer">
          Propulsé par Amazon Bedrock (Nova) + Strands Decider 2B
        </footer>
      </main>
    </div>
  );
}
