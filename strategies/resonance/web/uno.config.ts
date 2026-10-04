import { defineConfig, presetWind3 } from "unocss";

// Same theme as third_party/quant_trading/web/frontend/uno.config.ts: the design
// tokens (CSS custom properties in src/style.css) are mapped into the theme, so a
// component written here looks the same once it is moved into that frontend.
// CN market convention: up = red (涨 / 多方), down = green (跌 / 空方).
export default defineConfig({
  presets: [presetWind3()],
  theme: {
    colors: {
      bg: "var(--bg)",
      surface: "var(--surface)",
      border: "var(--border)",
      text: "var(--text)",
      muted: "var(--muted)",
      primary: "var(--primary)",
      danger: "var(--danger)",
      warning: "var(--warning)",
      success: "var(--success)",
      up: "var(--danger)", // 涨 = 红
      down: "var(--success)" // 跌 = 绿
    }
  }
});
