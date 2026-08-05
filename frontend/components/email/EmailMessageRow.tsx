"use client";

import type { EmailMessageSummary } from "@/types/api";

function formatDate(date: string | null) {
  if (!date) return "";
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) return date;
  return parsed.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });
}

export function EmailMessageRow({
  message,
  selected,
  onSelect,
  onToggleStar,
  onArchive,
  onDelete,
}: {
  message: EmailMessageSummary;
  selected: boolean;
  onSelect: (uid: string) => void;
  onToggleStar: (uid: string, starred: boolean) => void;
  onArchive: (uid: string) => void;
  onDelete: (uid: string) => void;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      className={`group relative flex w-full cursor-pointer flex-col border-b border-outline-variant/50 px-3 py-2.5 text-left hover:bg-white/5 ${
        selected ? "bg-white/10" : ""
      }`}
      onClick={() => onSelect(message.uid)}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") onSelect(message.uid); }}
    >
      <div className="flex items-center gap-2">
        <button
          type="button"
          aria-label={message.is_starred ? "Unstar" : "Star"}
          onClick={(e) => { e.stopPropagation(); onToggleStar(message.uid, !message.is_starred); }}
          className={`material-symbols-outlined shrink-0 text-[16px] ${
            message.is_starred ? "text-amber-400" : "text-slate-600 hover:text-slate-300"
          }`}
          style={{ fontVariationSettings: message.is_starred ? "'FILL' 1" : "'FILL' 0" }}
        >
          star
        </button>
        <p className={`min-w-0 flex-1 truncate text-sm ${message.is_read ? "text-slate-300" : "font-semibold text-white"}`}>
          {message.from_address}
        </p>
        <span className="shrink-0 text-[11px] text-slate-500 group-hover:hidden">{formatDate(message.date)}</span>
        <span className="hidden shrink-0 items-center gap-1 group-hover:flex">
          <button
            type="button"
            aria-label="Archive"
            onClick={(e) => { e.stopPropagation(); onArchive(message.uid); }}
            className="material-symbols-outlined text-[16px] text-slate-500 hover:text-white"
          >
            archive
          </button>
          <button
            type="button"
            aria-label="Delete"
            onClick={(e) => { e.stopPropagation(); onDelete(message.uid); }}
            className="material-symbols-outlined text-[16px] text-slate-500 hover:text-rose-400"
          >
            delete
          </button>
        </span>
      </div>
      <p className={`mt-0.5 truncate pl-6 text-xs ${message.is_read ? "text-slate-500" : "text-slate-300"}`}>
        {message.subject || "(no subject)"}
      </p>
    </div>
  );
}
