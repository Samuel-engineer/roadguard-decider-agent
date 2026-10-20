import { useRef, useState } from "react";
import { ACCEPT_ATTR } from "../constants";

interface UploaderProps {
  file: File | null;
  previewUrl: string | null;
  disabled?: boolean;
  onSelect: (file: File | null) => void;
}

function UploadGlyph() {
  return (
    <svg
      className="dropzone-glyph"
      width="40"
      height="40"
      viewBox="0 0 40 40"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path
        d="M20 26 V10 M14 16 L20 10 L26 16"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M9 24 V28 A2 2 0 0 0 11 30 H29 A2 2 0 0 0 31 28 V24"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function Uploader({
  file,
  previewUrl,
  disabled,
  onSelect,
}: UploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const isVideo = file?.type.startsWith("video/");

  function handleDragEnter(event: React.DragEvent) {
    if (disabled) return;
    event.preventDefault();
    setIsDragging(true);
  }

  function handleDragOver(event: React.DragEvent) {
    if (disabled) return;
    event.preventDefault();
    setIsDragging(true);
  }

  function handleDragLeave(event: React.DragEvent) {
    if (disabled) return;
    event.preventDefault();
    setIsDragging(false);
  }

  function handleDrop(event: React.DragEvent) {
    if (disabled) return;
    event.preventDefault();
    setIsDragging(false);
    const dropped = event.dataTransfer.files?.[0];
    onSelect(dropped ?? null);
  }

  return (
    <div className="uploader">
      <label htmlFor="media-file" className="uploader-label">
        Image ou vidéo
      </label>

      {file ? (
        <div className="dropzone-file" data-disabled={disabled ? "true" : "false"}>
          <span className="dropzone-filename">{file.name}</span>
          <label htmlFor="media-file" className="dropzone-change">
            Changer
          </label>
        </div>
      ) : (
        <div
          className="dropzone"
          data-dragging={isDragging ? "true" : "false"}
          data-disabled={disabled ? "true" : "false"}
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !disabled && inputRef.current?.click()}
        >
          <UploadGlyph />
          <p className="dropzone-primary">Glissez une image ou une vidéo ici</p>
          <p className="dropzone-secondary">ou cliquez pour parcourir</p>
        </div>
      )}

      <input
        id="media-file"
        ref={inputRef}
        className="visually-hidden"
        type="file"
        accept={ACCEPT_ATTR}
        disabled={disabled}
        onChange={(event) => onSelect(event.target.files?.[0] ?? null)}
      />

      <span className="visually-hidden" aria-live="polite">
        {isDragging ? "Fichier prêt à être déposé" : ""}
      </span>

      <p className="hint">
        Images : 4 Mio maximum. Vidéos : 100 Mio maximum. Types acceptés :
        JPEG, PNG, GIF, WebP, MP4, MPEG, MOV, WebM et MKV.
      </p>

      {previewUrl ? (
        <div className="preview">
          {isVideo ? (
            <video src={previewUrl} controls aria-label="Aperçu de la vidéo" />
          ) : (
            <img src={previewUrl} alt="Aperçu du fichier sélectionné" />
          )}
        </div>
      ) : null}
    </div>
  );
}
