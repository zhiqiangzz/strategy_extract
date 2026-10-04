// @unocss-include
// (UnoCSS does not scan plain .ts files by default; the line above makes it pick up the class names below.)
import type { FlowStep, Role, Side } from "../../types";

// 多方 = up (red), 空方 = down (green): the same convention as the rest of the trading UI.
export const ROLE_BG: Record<Role, string> = {
  long: "bg-up",
  short: "bg-down",
  mod: "bg-warning",
  mgr: "bg-primary"
};

export const ROLE_NAME: Record<Role, string> = {
  long: "多方",
  short: "空方",
  mod: "主持人",
  mgr: "Manager"
};

export const SIDE_CHAR: Record<Side, string> = { long: "多", short: "空" };

export const LANES: Role[] = ["long", "short", "mod", "mgr"];

export const VERDICT_MARK: Record<string, string> = { 成立: "✓", 被削弱: "◐", 被驳倒: "✕" };

// Clickable non-button elements: pointer, no text selection, a visible keyboard focus ring.
export const CLICKABLE =
  "cursor-pointer select-none focus:outline-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary";

/** "08:45" from a second of the day (wraps past midnight). */
export function clock(secondOfDay: number): string {
  const s = ((Math.floor(secondOfDay) % 86400) + 86400) % 86400;
  return String(Math.floor(s / 3600)).padStart(2, "0") + ":" + String(Math.floor((s % 3600) / 60)).padStart(2, "0");
}

export function money(value: number | null): string {
  return value == null ? "—" : "$" + value.toFixed(2);
}

export function seconds(value: number | null): string {
  return value == null ? "—" : value + " 秒";
}

/** "第 2 轮 · 空方反驳" when the debate had more than one round, else just the label. */
export function stepTitle(step: FlowStep, rounds: number): string {
  return rounds > 1 && step.round > 0 ? `第 ${step.round} 轮 · ${step.label}` : step.label;
}

/** Enter or Space on a role="button" element acts like a click. */
export function onActivate(event: KeyboardEvent, action: () => void): void {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    action();
  }
}
