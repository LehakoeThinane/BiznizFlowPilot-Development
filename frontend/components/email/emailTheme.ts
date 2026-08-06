export type EmailTheme = "light" | "dark";

export interface EmailBackgroundPreset {
  key: string;
  label: string;
  gradient: string;
}

// CSS gradients, not photographs - no image assets to source/license, zero
// loading cost, and each already reads fine against both themes.
export const EMAIL_BACKGROUNDS: EmailBackgroundPreset[] = [
  { key: "aurora", label: "Aurora", gradient: "linear-gradient(135deg, #0ea5e9, #8b5cf6, #ec4899)" },
  { key: "sunset", label: "Sunset", gradient: "linear-gradient(135deg, #f97316, #ec4899, #a855f7)" },
  { key: "forest", label: "Forest", gradient: "linear-gradient(135deg, #14532d, #15803d, #4ade80)" },
  { key: "ocean", label: "Ocean", gradient: "linear-gradient(135deg, #082f49, #0369a1, #38bdf8)" },
  { key: "midnight", label: "Midnight", gradient: "linear-gradient(135deg, #020617, #1e293b, #475569)" },
  { key: "dawn", label: "Dawn", gradient: "linear-gradient(135deg, #fef3c7, #fca5a5, #f472b6)" },
];

export function backgroundGradient(key: string | null): string | undefined {
  return EMAIL_BACKGROUNDS.find((b) => b.key === key)?.gradient;
}

// Small theme-aware class helpers, shared by the Email page and its
// components - kept as plain functions (not a CSS-variable/token system),
// matching this app's existing convention of literal Tailwind classes.
export function panelClass(theme: EmailTheme): string {
  return theme === "dark"
    ? "erp-panel"
    : "rounded-2xl border border-slate-200/70 bg-white/85 shadow-lg backdrop-blur-2xl";
}

export function textClass(theme: EmailTheme): string {
  return theme === "dark" ? "text-white" : "text-slate-900";
}

export function mutedClass(theme: EmailTheme): string {
  return theme === "dark" ? "text-slate-400" : "text-slate-500";
}

export function subtleTextClass(theme: EmailTheme): string {
  return theme === "dark" ? "text-slate-500" : "text-slate-400";
}

export function borderClass(theme: EmailTheme): string {
  return theme === "dark" ? "border-outline-variant" : "border-slate-200";
}

// Full literal strings (not built via concatenation at the call site) so
// Tailwind's static scanner can actually see and generate them.
export function rowBorderClass(theme: EmailTheme): string {
  return theme === "dark" ? "border-outline-variant/50" : "border-slate-200/50";
}

export function archiveHoverClass(theme: EmailTheme): string {
  return theme === "dark" ? "hover:text-white" : "hover:text-slate-900";
}

export function floatingPanelClass(theme: EmailTheme): string {
  return theme === "dark"
    ? "border-outline-variant bg-[#0f1c33]"
    : "border-slate-200 bg-white";
}

export function floatingPanelHoverClass(theme: EmailTheme): string {
  return theme === "dark" ? "hover:bg-[#132038]" : "hover:bg-slate-50";
}

export function closeButtonClass(theme: EmailTheme): string {
  return theme === "dark" ? "text-slate-400 hover:text-white" : "text-slate-500 hover:text-slate-900";
}

export function hoverBgClass(theme: EmailTheme): string {
  return theme === "dark" ? "hover:bg-white/5" : "hover:bg-slate-100";
}

export function selectedBgClass(theme: EmailTheme): string {
  return theme === "dark" ? "bg-white/10" : "bg-slate-100";
}

export function inputClass(theme: EmailTheme): string {
  return theme === "dark"
    ? "erp-input w-full px-3 py-2 text-sm"
    : "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 outline-none focus:ring-2 focus:ring-brand/50";
}
