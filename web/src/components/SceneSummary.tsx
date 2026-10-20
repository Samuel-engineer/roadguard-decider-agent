interface SceneSummaryProps {
  summary: string;
}

export default function SceneSummary({ summary }: SceneSummaryProps) {
  if (!summary) {
    return null;
  }
  return (
    <section className="scene-summary" aria-label="Résumé de la scène">
      <h2>Scène observée</h2>
      <p>{summary}</p>
    </section>
  );
}
