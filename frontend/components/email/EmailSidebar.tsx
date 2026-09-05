"use client";

import { DisplaySettingsPopover } from "./DisplaySettingsPopover";
import { borderClass, hoverBgClass, mutedClass, panelClass, textClass, type EmailTheme } from "./emailTheme";

export interface EmailFolder {
  key: string;
  label: string;
  icon: string;
  count?: number;
  disabled?: boolean;
}

export function EmailSidebar({
  folders,
  activeFolder,
  onSelectFolder,
  onCompose,
  onDisconnect,
  theme,
  background,
  onSaveDisplayPrefs,
}: {
  folders: EmailFolder[];
  activeFolder: string;
  onSelectFolder: (key: string) => void;
  onCompose: () => void;
  onDisconnect: () => void;
  theme: EmailTheme;
  background: string | null;
  onSaveDisplayPrefs: (theme: EmailTheme, background: string | null) => void;
}) {
  return (
    <div className={`flex max-h-44 w-full shrink-0 flex-col overflow-hidden ${panelClass(theme)} md:max-h-none md:w-64`}>
      <div className={`flex items-center gap-2 border-b p-3 ${borderClass(theme)}`}>
        <button
          type="button"
          onClick={onCompose}
          className="flex flex-1 items-center justify-center gap-2 rounded-full bg-brand px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-opacity hover:opacity-90"
        >
          <span className="material-symbols-outlined text-[18px]">edit</span>
          Compose
        </button>
        <DisplaySettingsPopover theme={theme} background={background} onSave={onSaveDisplayPrefs} />
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-2">
        {folders.map((folder) => (
          <button
            key={folder.key}
            type="button"
            disabled={folder.disabled}
            onClick={() => onSelectFolder(folder.key)}
            className={`mb-0.5 flex w-full items-center gap-3 rounded-full px-4 py-2 text-sm transition-colors ${folder.disabled
                ? "cursor-not-allowed text-slate-500"
                : activeFolder === folder.key
                  ? "bg-brand/20 font-medium text-brand"
                  : `${mutedClass(theme)} ${hoverBgClass(theme)}`
              }`}
          >
            <span className="material-symbols-outlined text-[18px]">{folder.icon}</span>
            <span className="flex-1 truncate text-left">{folder.label}</span>
            {typeof folder.count === "number" && folder.count > 0 && (
              <span className={`shrink-0 text-xs font-semibold ${textClass(theme)}`}>{folder.count}</span>
            )}
            {folder.disabled && (
              <span className="shrink-0 rounded-full bg-white/5 px-2 py-0.5 text-[10px] font-medium text-slate-500">
                Soon
              </span>
            )}
          </button>
        ))}
      </nav>

      <div className={`border-t px-4 py-3 ${borderClass(theme)}`}>
        <button type="button" onClick={onDisconnect} className="text-xs text-rose-400 hover:text-rose-300">
          Disconnect mailbox
        </button>
      </div>
    </div>
  );
}
