import { useRef } from "react";
import { ACCEPT_ATTR } from "../constants";

interface UploaderProps {
  file: File | null;
  previewUrl: string | null;
  disabled?: boolean;
  onSelect: (file: File | null) => void;
}

export default function Uploader({
  file,
  previewUrl,
  disabled,
  onSelect,
}: UploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const isVideo = file?.type.startsWith("video/");

  return (
    <div className="uploader">
      <label htmlFor="media-file" className="uploader-label">
        Image ou vidéo
      </label>
      <input
        id="media-file"
        ref={inputRef}
        type="file"
        accept={ACCEPT_ATTR}
        disabled={disabled}
        onChange={(event) => onSelect(event.target.files?.[0] ?? null)}
      />
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
