import type { DebugInfo } from "../types";

interface DebugPanelProps {
  debug: DebugInfo;
}

export default function DebugPanel({ debug }: DebugPanelProps) {
  return (
    <details className="debug-panel">
      <summary>Détails techniques (debug)</summary>
      <dl className="debug-meta">
        <dt>Clé média</dt>
        <dd>{debug.media_key}</dd>
        <dt>Durée Decider</dt>
        <dd>{debug.elapsed_ms} ms</dd>
      </dl>
      <h4>Faits visuels</h4>
      <pre>{JSON.stringify(debug.visual_facts, null, 2)}</pre>
      <h4>Références Code de la route</h4>
      <pre>{JSON.stringify(debug.knowledge_references, null, 2)}</pre>
    </details>
  );
}
