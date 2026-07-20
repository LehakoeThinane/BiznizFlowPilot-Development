"use client";

import { stickerEmoji } from "@/lib/stickers";
import type { DirectMessage } from "@/types/api";

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatEventRange(start: string, end: string) {
  const s = new Date(start);
  const e = new Date(end);
  const dateOpts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" };
  const timeOpts: Intl.DateTimeFormatOptions = { hour: "numeric", minute: "2-digit" };
  return `${s.toLocaleDateString(undefined, dateOpts)} · ${s.toLocaleTimeString(undefined, timeOpts)} – ${e.toLocaleTimeString(undefined, timeOpts)}`;
}

function initials(name: string) {
  return name.split(" ").map((p) => p[0]).join("").toUpperCase().slice(0, 2);
}

export function MessageBubble({
  message,
  isMine,
  onVote,
}: {
  message: DirectMessage;
  isMine: boolean;
  onVote: (pollId: string, optionIds: string[]) => void;
}) {
  const bubbleClass = `max-w-[75%] whitespace-pre-wrap break-words rounded-2xl px-3 py-2 text-sm ${
    isMine ? "rounded-tr-sm bg-blue-600 text-white" : "rounded-tl-sm bg-white/10 text-slate-100"
  }`;

  if (message.message_type === "sticker" && message.sticker_key) {
    return <div className="text-5xl leading-none">{stickerEmoji(message.sticker_key)}</div>;
  }

  if (message.message_type === "image" && message.attachment) {
    return (
      <div className={`overflow-hidden p-1 ${bubbleClass}`}>
        {message.attachment.download_url && (
          <a href={message.attachment.download_url} target="_blank" rel="noreferrer">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={message.attachment.download_url} alt={message.attachment.filename} className="max-h-72 w-full rounded-xl object-cover" />
          </a>
        )}
        {message.content && <p className="px-2 py-1.5">{message.content}</p>}
      </div>
    );
  }

  if (message.message_type === "video" && message.attachment) {
    return (
      <div className={`overflow-hidden p-1 ${bubbleClass}`}>
        {message.attachment.download_url && (
          <video controls src={message.attachment.download_url} className="max-h-72 w-full rounded-xl" />
        )}
        {message.content && <p className="px-2 py-1.5">{message.content}</p>}
      </div>
    );
  }

  if (message.message_type === "audio" && message.attachment) {
    return (
      <div className={bubbleClass}>
        {message.attachment.download_url && <audio controls src={message.attachment.download_url} className="w-56 max-w-full" />}
        {message.content && <p className="mt-1.5">{message.content}</p>}
      </div>
    );
  }

  if (message.message_type === "document" && message.attachment) {
    return (
      <div className={bubbleClass}>
        <a
          href={message.attachment.download_url ?? "#"}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-2.5 rounded-lg bg-black/10 px-2.5 py-2 hover:bg-black/20"
        >
          <span className="material-symbols-outlined shrink-0 text-2xl">description</span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm">{message.attachment.filename}</span>
            <span className="block text-xs opacity-70">{formatBytes(message.attachment.size_bytes)}</span>
          </span>
        </a>
        {message.content && <p className="mt-1.5">{message.content}</p>}
      </div>
    );
  }

  if (message.message_type === "contact" && message.shared_customer) {
    const c = message.shared_customer;
    return (
      <div className={bubbleClass}>
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sky-500 text-xs font-semibold text-white">
            {initials(c.name)}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{c.name}</p>
            <p className="truncate text-xs opacity-70">{c.phone || c.email || c.company || "Contact"}</p>
          </div>
        </div>
      </div>
    );
  }

  if (message.message_type === "event" && message.shared_meeting) {
    const m = message.shared_meeting;
    return (
      <div className={bubbleClass}>
        <div className="flex items-center gap-2.5">
          <span className="material-symbols-outlined shrink-0 text-2xl text-rose-300">event</span>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{m.title}</p>
            <p className="truncate text-xs opacity-70">{formatEventRange(m.start_time, m.end_time)}</p>
          </div>
        </div>
      </div>
    );
  }

  if (message.message_type === "poll" && message.poll) {
    const poll = message.poll;
    const hasVoted = poll.my_vote_option_ids.length > 0;
    return (
      <div className={`${bubbleClass} min-w-[14rem]`}>
        <p className="mb-2 flex items-center gap-1.5 font-medium">
          <span className="material-symbols-outlined text-base">poll</span>
          {poll.question}
        </p>
        <div className="space-y-1.5">
          {poll.options.map((opt) => {
            const selected = poll.my_vote_option_ids.includes(opt.id);
            const pct = poll.total_votes > 0 ? Math.round((opt.vote_count / poll.total_votes) * 100) : 0;
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => {
                  if (poll.allow_multiple) {
                    const next = selected
                      ? poll.my_vote_option_ids.filter((id) => id !== opt.id)
                      : [...poll.my_vote_option_ids, opt.id];
                    onVote(poll.id, next);
                  } else {
                    onVote(poll.id, [opt.id]);
                  }
                }}
                className="relative block w-full overflow-hidden rounded-lg bg-black/15 px-2.5 py-1.5 text-left text-xs hover:bg-black/25"
              >
                {hasVoted && (
                  <span
                    className="absolute inset-y-0 left-0 bg-white/15"
                    style={{ width: `${pct}%` }}
                  />
                )}
                <span className="relative flex items-center justify-between gap-2">
                  <span className="flex items-center gap-1.5">
                    {selected && <span className="material-symbols-outlined text-sm">check_circle</span>}
                    {opt.text}
                  </span>
                  {hasVoted && <span className="opacity-70">{pct}%</span>}
                </span>
              </button>
            );
          })}
        </div>
        <p className="mt-1.5 text-[10px] opacity-60">
          {poll.total_votes} vote{poll.total_votes === 1 ? "" : "s"}{poll.allow_multiple ? " · multiple answers allowed" : ""}
        </p>
      </div>
    );
  }

  return <div className={bubbleClass}>{message.content}</div>;
}
