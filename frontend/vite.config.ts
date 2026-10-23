import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  build: {
    outDir: "../blood_response/web",
    emptyOutDir: false,
    cssCodeSplit: false,
    assetsInlineLimit: 1000000,
    // Keep the existing Python server's two-file static asset contract.
    chunkSizeWarningLimit: 700,
    rolldownOptions: {
      output: {
        entryFileNames: "app.js",
        assetFileNames: "style.[ext]",
        codeSplitting: false,
      },
    },
  },
});
