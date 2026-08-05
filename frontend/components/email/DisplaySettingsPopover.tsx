"use client";

import { useEffect, useRef, useState } from "react";

import { EMAIL_BACKGROUNDS, backgroundGradient, borderClass, panelClass, textClass, type EmailTheme } from "./emailTheme";

export function DisplaySettingsPopover({
  theme,
  background,
  onSave,
}: {
  theme: EmailTheme;
  background: string | null;
  onSave: (theme: EmailTheme, background: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label="Display settings"
        onClick={() => setOpen((o) => !o)}
        className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors ${
          theme === "dark" ? "text-slate-400 hover:bg-white/10 hover:text-white" : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"
        }`}
      >
        <span className="material-symbols-outlined text-[20px]">palette</span>
      </button>

      {open && (
        <div
          className={`absolute right-0 top-full z-50 mt-2 w-72 overflow-hidden rounded-xl border p-4 shadow-2xl ${panelClass(theme)} ${borderClass(theme)}`}
        >
          <p className={`mb-2 text-xs font-semibold uppercase tracking-wide ${textClass(theme)}`}>Theme</p>
          <div className="mb-4 flex gap-2">
            {(["dark", "light"] as EmailTheme[]).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => onSave(t, background)}
                className={`flex-1 rounded-lg border px-3 py-1.5 text-sm capitalize transition-colors ${
                  theme === t
                    ? "border-brand bg-brand/20 font-medium text-brand"
                    : `${borderClass(theme)} ${textClass(theme)}`
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          <p className={`mb-2 text-xs font-semibold uppercase tracking-wide ${textClass(theme)}`}>Background</p>
          <div className="grid grid-cols-4 gap-2">
            <button
              type="button"
              aria-label="No background"
              onClick={() => onSave(theme, null)}
              className={`h-10 rounded-md border-2 ${
                background === null ? "border-brand" : "border-transparent"
              } bg-slate-500/20 text-[10px] ${textClass(theme)}`}
            >
              None
            </button>
            {EMAIL_BACKGROUNDS.map((b) => (
              <button
                key={b.key}
                type="button"
                aria-label={b.label}
                title={b.label}
                onClick={() => onSave(theme, b.key)}
                className={`h-10 rounded-md border-2 ${background === b.key ? "border-brand" : "border-transparent"}`}
                style={{ background: backgroundGradient(b.key) }}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
