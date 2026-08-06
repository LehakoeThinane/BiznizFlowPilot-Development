"use client";

import { useState } from "react";

import { EMAIL_BACKGROUNDS, backgroundGradient, borderClass, closeButtonClass, panelClass, textClass, type EmailTheme } from "./emailTheme";

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

  return (
    <>
      <button
        type="button"
        aria-label="Display settings"
        onClick={() => setOpen(true)}
        className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors ${
          theme === "dark" ? "text-slate-400 hover:bg-white/10 hover:text-white" : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"
        }`}
      >
        <span className="material-symbols-outlined text-[20px]">palette</span>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          onClick={() => setOpen(false)}
        >
          <div
            className={`w-full max-w-sm overflow-hidden rounded-2xl border shadow-2xl ${panelClass(theme)} ${borderClass(theme)}`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className={`flex items-center justify-between border-b px-5 py-4 ${borderClass(theme)}`}>
              <h2 className={`text-base font-semibold ${textClass(theme)}`}>Display settings</h2>
              <button type="button" aria-label="Close" onClick={() => setOpen(false)} className={closeButtonClass(theme)}>×</button>
            </div>

            <div className="space-y-5 px-5 py-5">
              <div>
                <p className={`mb-2 text-xs font-semibold uppercase tracking-wide ${textClass(theme)}`}>Theme</p>
                <div className="flex gap-2">
                  {(["dark", "light"] as EmailTheme[]).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => onSave(t, background)}
                      className={`flex-1 rounded-lg border px-3 py-2 text-sm capitalize transition-colors ${
                        theme === t
                          ? "border-brand bg-brand/20 font-medium text-brand"
                          : `${borderClass(theme)} ${textClass(theme)}`
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <p className={`mb-2 text-xs font-semibold uppercase tracking-wide ${textClass(theme)}`}>Background</p>
                <div className="grid grid-cols-4 gap-2.5">
                  <button
                    type="button"
                    aria-label="No background"
                    onClick={() => onSave(theme, null)}
                    className={`h-12 rounded-lg border-2 ${
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
                      className={`h-12 rounded-lg border-2 ${background === b.key ? "border-brand" : "border-transparent"}`}
                      style={{ background: backgroundGradient(b.key) }}
                    />
                  ))}
                </div>
              </div>
            </div>

            <div className={`flex justify-end border-t px-5 py-4 ${borderClass(theme)}`}>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-md bg-brand px-5 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
