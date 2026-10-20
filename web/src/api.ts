import type { Mode, UnifiedResponse, UploadAuth } from "./types";

const API_URL: string = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "");

function apiBase(): string {
  if (!API_URL) {
    throw new Error("VITE_API_URL n'est pas configurée.");
  }
  return API_URL;
}

export class ApiError extends Error {
  operation: string;
  status: number | null;
  payload: unknown;

  constructor(
    message: string,
    operation: string,
    status: number | null = null,
    payload: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.operation = operation;
    this.status = status;
    this.payload = payload;
  }
}

async function readJsonResponse<T>(
  response: Response,
  operation: string,
): Promise<T> {
  const text = await response.text();
  let payload: unknown;
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    throw new ApiError(
      `Réponse JSON invalide (HTTP ${response.status}).`,
      operation,
      response.status,
    );
  }
  if (!response.ok) {
    const message =
      (payload as { error?: string })?.error ??
      `Erreur HTTP ${response.status}.`;
    throw new ApiError(message, operation, response.status, payload);
  }
  return payload as T;
}

export async function getUploadAuth(contentType: string): Promise<UploadAuth> {
  const response = await fetch(`${apiBase()}/uploads`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content_type: contentType }),
  });
  const auth = await readJsonResponse<UploadAuth>(
    response,
    "Demande d'autorisation",
  );
  if (!auth.upload_url || !auth.fields || !auth.s3_key) {
    throw new ApiError(
      "La réponse de /uploads est incomplète.",
      "Demande d'autorisation",
    );
  }
  return auth;
}

export async function uploadToS3(auth: UploadAuth, file: File): Promise<void> {
  const form = new FormData();
  for (const [key, value] of Object.entries(auth.fields)) {
    form.append(key, value);
  }
  form.append("file", file);
  const response = await fetch(auth.upload_url, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    const details = await response.text();
    throw new ApiError(
      `Échec HTTP ${response.status}. ${details}`,
      "Téléversement S3",
      response.status,
    );
  }
}

export async function query(
  mode: Mode,
  s3Key: string,
  contentType: string,
): Promise<UnifiedResponse> {
  const response = await fetch(`${apiBase()}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode,
      content_type: contentType,
      s3_key: s3Key,
    }),
  });
  return readJsonResponse<UnifiedResponse>(response, "Analyse");
}
