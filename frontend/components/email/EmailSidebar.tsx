"use client";

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
}: {
  folders: EmailFolder[];
  activeFolder: string;
  onSelectFolder: (key: string) => void;
  onCompose: () => void;
  onDisconnect: () => void;
}) {
  return (
    <div className="flex w-64 shrink-0 flex-col overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33]">
      <div className="p-3">
        <button
          type="button"
          onClick={onCompose}
          className="flex w-full items-center justify-center gap-2 rounded-full bg-brand px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-opacity hover:opacity-90"
        >
          <span className="material-symbols-outlined text-[18px]">edit</span>
          Compose
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto px-2">
        {folders.map((folder) => (
          <button
            key={folder.key}
            type="button"
            disabled={folder.disabled}
            onClick={() => onSelectFolder(folder.key)}
            className={`mb-0.5 flex w-full items-center gap-3 rounded-full px-4 py-2 text-sm transition-colors ${
              folder.disabled
                ? "cursor-not-allowed text-slate-600"
                : activeFolder === folder.key
                  ? "bg-brand/20 font-medium text-white"
                  : "text-slate-300 hover:bg-white/5"
            }`}
          >
            <span className="material-symbols-outlined text-[18px]">{folder.icon}</span>
            <span className="flex-1 truncate text-left">{folder.label}</span>
            {typeof folder.count === "number" && folder.count > 0 && (
              <span className="shrink-0 text-xs font-semibold">{folder.count}</span>
            )}
            {folder.disabled && (
              <span className="shrink-0 rounded-full bg-white/5 px-2 py-0.5 text-[10px] font-medium text-slate-500">
                Soon
              </span>
            )}
          </button>
        ))}
      </nav>

      <div className="border-t border-outline-variant px-4 py-3">
        <button type="button" onClick={onDisconnect} className="text-xs text-rose-400 hover:text-rose-300">
          Disconnect mailbox
        </button>
      </div>
    </div>
  );
}
