"use client";

import type { EmailMessageSummary } from "@/types/api";
import { archiveHoverClass, hoverBgClass, rowBorderClass, selectedBgClass, textClass, type EmailTheme } from "./emailTheme";

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
  theme,
}: {
  message: EmailMessageSummary;
  selected: boolean;
  onSelect: (uid: string) => void;
  onToggleStar: (uid: string, starred: boolean) => void;
  onArchive: (uid: string) => void;
  onDelete: (uid: string) => void;
  theme: EmailTheme;
}) {
  const readClass = theme === "dark" ? "text-slate-300" : "text-slate-600";
  const subjectReadClass = theme === "dark" ? "text-slate-500" : "text-slate-500";
  const subjectUnreadClass = theme === "dark" ? "text-slate-300" : "text-slate-700";

  return (
    <div
      role="button"
      tabIndex={0}
      className={`group relative flex w-full cursor-pointer flex-col border-b px-3 py-2.5 text-left ${rowBorderClass(theme)} ${hoverBgClass(theme)} ${
        selected ? selectedBgClass(theme) : ""
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
            message.is_starred ? "text-amber-400" : "text-slate-500 hover:text-slate-400"
          }`}
          style={{ fontVariationSettings: message.is_starred ? "'FILL' 1" : "'FILL' 0" }}
        >
          star
        </button>
        <p className={`min-w-0 flex-1 truncate text-sm ${message.is_read ? readClass : `font-semibold ${textClass(theme)}`}`}>
          {message.from_address}
        </p>
        <span className="shrink-0 text-[11px] text-slate-500 group-hover:hidden">{formatDate(message.date)}</span>
        <span className="hidden shrink-0 items-center gap-1 group-hover:flex">
          <button
            type="button"
            aria-label="Archive"
            onClick={(e) => { e.stopPropagation(); onArchive(message.uid); }}
            className={`material-symbols-outlined text-[16px] text-slate-500 ${archiveHoverClass(theme)}`}
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
      <p className={`mt-0.5 truncate pl-6 text-xs ${message.is_read ? subjectReadClass : subjectUnreadClass}`}>
        {message.subject || "(no subject)"}
      </p>
    </div>
  );
}
