import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "@fontsource-variable/space-grotesk";
import "@fontsource-variable/inter";
import "./styles.css";

// Dev-only visual preview harness. Ships NOTHING to production: the branch is
// gated on `import.meta.env.DEV` so Vite tree-shakes it out of the build.
// Run it with: VITE_PREVIEW=1 npm run dev
const usePreview =
  import.meta.env.DEV && import.meta.env.VITE_PREVIEW === "1";

async function bootstrap() {
  const root = ReactDOM.createRoot(document.getElementById("root")!);
  if (usePreview) {
    const { default: Preview } = await import("./dev/Preview");
    root.render(
      <React.StrictMode>
        <Preview />
      </React.StrictMode>,
    );
    return;
  }
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}

void bootstrap();
