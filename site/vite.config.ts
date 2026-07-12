import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "./" makes every built asset path relative, so the same dist works both on the GitHub
// Pages repo subpath (https://<owner>.github.io/<repo>/) and on Render's domain root. Client-side
// routing uses HashRouter, so no server rewrites are needed either way.
export default defineConfig({
  plugins: [react()],
  base: "./",
});
