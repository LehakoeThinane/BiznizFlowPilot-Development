"use client";

import { STICKERS } from "@/lib/stickers";

export function StickerPickerModal({ onSelect, onClose }: { onSelect: (stickerKey: string) => void; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
        <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
          <h2 className="text-base font-semibold text-white">Send a sticker</h2>
          <button type="button" aria-label="Close" onClick={onClose} className="text-slate-400 hover:text-white">×</button>
        </div>
        <div className="grid grid-cols-6 gap-1 p-4">
          {STICKERS.map((s) => (
            <button
              key={s.key}
              type="button"
              title={s.label}
              onClick={() => {
                onSelect(s.key);
                onClose();
              }}
              className="flex aspect-square items-center justify-center rounded-lg text-3xl transition-colors hover:bg-white/10"
            >
              {s.emoji}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
