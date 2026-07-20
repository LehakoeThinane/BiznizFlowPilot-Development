"use client";

import { useEffect, useRef } from "react";

export type AttachmentAction = "document" | "media" | "camera" | "audio" | "contact" | "poll" | "event" | "sticker";

interface MenuItem {
  action: AttachmentAction;
  label: string;
  icon: string;
  badgeClass: string;
}

const ITEMS: MenuItem[] = [
  { action: "document", label: "Document", icon: "description", badgeClass: "bg-violet-600" },
  { action: "media", label: "Photos & videos", icon: "photo_library", badgeClass: "bg-blue-600" },
  { action: "camera", label: "Camera", icon: "photo_camera", badgeClass: "bg-rose-600" },
  { action: "audio", label: "Audio", icon: "mic", badgeClass: "bg-orange-600" },
  { action: "contact", label: "Contact", icon: "person", badgeClass: "bg-sky-600" },
  { action: "poll", label: "Poll", icon: "poll", badgeClass: "bg-amber-600" },
  { action: "event", label: "Event", icon: "event", badgeClass: "bg-red-600" },
  { action: "sticker", label: "New sticker", icon: "mood", badgeClass: "bg-emerald-600" },
];

export function AttachmentMenu({ onSelect, onClose }: { onSelect: (action: AttachmentAction) => void; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onClose]);

  return (
    <div
      ref={ref}
      className="absolute bottom-full left-0 z-40 mb-2 w-64 overflow-hidden rounded-2xl border border-outline-variant bg-[#182642] py-2 shadow-2xl"
    >
      {ITEMS.map((item) => (
        <button
          key={item.action}
          type="button"
          onClick={() => {
            onSelect(item.action);
            onClose();
          }}
          className="flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-white/5"
        >
          <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-white ${item.badgeClass}`}>
            <span className="material-symbols-outlined text-[20px]">{item.icon}</span>
          </span>
          <span className="text-sm text-white">{item.label}</span>
        </button>
      ))}
    </div>
  );
}
