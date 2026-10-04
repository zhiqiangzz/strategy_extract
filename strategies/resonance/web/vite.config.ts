import { defineConfig } from "vitest/config";
import vue from "@vitejs/plugin-vue";
import UnoCSS from "unocss/vite";

// Same toolchain as third_party/quant_trading/web/frontend (Vite + Vue SFC + UnoCSS),
// so the components under src/views/resonance can be copied there unchanged.
export default defineConfig({
  // Relative asset base: the build works under any path prefix.
  base: "./",
  plugins: [UnoCSS(), vue()],
  build: {
    outDir: "dist",
    emptyOutDir: true
  },
  server: {
    // `pixi run web-dev` reads flow data from `cli web` (strategies.resonance.serve).
    proxy: {
      "/runs": "http://127.0.0.1:8770"
    }
  },
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"]
  }
});
