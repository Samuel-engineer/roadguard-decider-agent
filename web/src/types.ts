export type Mode = "exam" | "situation";

export interface CardOption {
  label: string;
  score: number;
  selected: boolean;
}

export interface Card {
  id: string;
  title: string;
  kind: "choice" | "allow_deny";
  options: CardOption[];
}

export interface KnowledgeReference {
  text: string;
  score?: number | null;
  location?: unknown;
}

export interface DebugInfo {
  visual_facts: Record<string, unknown>;
  knowledge_references: KnowledgeReference[];
  media_key: string;
  elapsed_ms: number;
}

export interface UnifiedResponse {
  mode: Mode;
  cards: Card[];
  scene_summary: string;
  debug: DebugInfo;
}

export interface UploadAuth {
  upload_url: string;
  fields: Record<string, string>;
  s3_key: string;
  content_type: string;
}
