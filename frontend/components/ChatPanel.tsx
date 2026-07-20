"use client";

import { useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import { STICKERS } from "@/lib/stickers";
import type {
  ChatConversationDetail,
  ChatMessage,
  MentionSearchResult,
  ResolvedMention,
  SendMessageResponse,
} from "@/types/api";

const MENTION_TYPES = ["client", "lead", "task", "user", "product", "supplier"];

interface MentionState {
  active: boolean;
  type: string | null;   // null = picking type, string = picking entity
  query: string;
  startIndex: number;
}

function MentionBadge({ mention }: { mention: ResolvedMention }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
        mention.found
          ? "bg-brand/10 text-brand"
          : "bg-red-50 text-red-600"
      }`}
    >
      @{mention.type}:{mention.display_name}
      {!mention.found && " ✗"}
    </span>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex flex-col ${isUser ? "items-end" : "items-start"} gap-1`}>
      {msg.mentions_data?.length > 0 && isUser && (
        <div className="flex flex-wrap gap-1 justify-end">
          {msg.mentions_data.map((m, i) => (
            <MentionBadge key={i} mention={m} />
          ))}
        </div>
      )}
      <div
        className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap break-words ${
          isUser
            ? "bg-brand text-white rounded-tr-sm"
            : "bg-slate-100 text-slate-900 rounded-tl-sm"
        }`}
      >
        {msg.content}
      </div>
    </div>
  );
}

export function ChatPanel() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [mention, setMention] = useState<MentionState>({
    active: false,
    type: null,
    query: "",
    startIndex: 0,
  });
  const [suggestions, setSuggestions] = useState<MentionSearchResult[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [showEmoji, setShowEmoji] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const emojiRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  useEffect(() => {
    if (!showEmoji) return;
    function handleClick(e: MouseEvent) {
      if (emojiRef.current && !emojiRef.current.contains(e.target as Node)) setShowEmoji(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showEmoji]);

  function insertEmoji(emoji: string) {
    const el = inputRef.current;
    const start = el?.selectionStart ?? input.length;
    const end = el?.selectionEnd ?? input.length;
    const newVal = input.slice(0, start) + emoji + input.slice(end);
    setInput(newVal);
    setShowEmoji(false);
    setTimeout(() => {
      el?.focus();
      const pos = start + emoji.length;
      el?.setSelectionRange(pos, pos);
    }, 0);
  }

  // ── @mention detection ──────────────────────────────────────────────────

  function handleInputChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const val = e.target.value;
    setInput(val);

    const cursor = e.target.selectionStart ?? val.length;
    const before = val.slice(0, cursor);
    const atIdx = before.lastIndexOf("@");

    if (atIdx === -1 || (atIdx > 0 && /\S/.test(val[atIdx - 1]))) {
      setMention({ active: false, type: null, query: "", startIndex: 0 });
      setSuggestions([]);
      return;
    }

    const fragment = before.slice(atIdx + 1); // text after @
    const colonIdx = fragment.indexOf(":");

    if (colonIdx === -1) {
      // Picking mention TYPE
      setMention({ active: true, type: null, query: fragment, startIndex: atIdx });
      setSuggestions([]);
    } else {
      // Picking ENTITY
      const mType = fragment.slice(0, colonIdx);
      const q = fragment.slice(colonIdx + 1);
      setMention({ active: true, type: mType, query: q, startIndex: atIdx });
      fetchSuggestions(mType, q);
    }
  }

  async function fetchSuggestions(type: string, q: string) {
    setLoadingSuggestions(true);
    try {
      const results = await apiRequest<MentionSearchResult[]>(
        `/api/v1/chat/mentions/search?type=${encodeURIComponent(type)}&q=${encodeURIComponent(q)}`,
        { _skipRefresh: true }
      );
      setSuggestions(results);
    } catch {
      setSuggestions([]);
    } finally {
      setLoadingSuggestions(false);
    }
  }

  function selectMentionType(mType: string) {
    const before = input.slice(0, mention.startIndex);
    const after = input.slice(mention.startIndex + 1 + mention.query.length);
    const newVal = `${before}@${mType}:${after}`;
    setInput(newVal);
    setMention({ active: true, type: mType, query: "", startIndex: mention.startIndex });
    setSuggestions([]);
    fetchSuggestions(mType, "");
    setTimeout(() => {
      if (inputRef.current) {
        const pos = before.length + mType.length + 2;
        inputRef.current.setSelectionRange(pos, pos);
        inputRef.current.focus();
      }
    }, 0);
  }

  function selectMentionEntity(item: MentionSearchResult) {
    if (!mention.type) return;
    const slug = item.label.replace(/\s+/g, "_");
    const before = input.slice(0, mention.startIndex);
    const colonPos = mention.startIndex + 1 + mention.type.length + 1;
    const after = input.slice(colonPos + mention.query.length);
    const newVal = `${before}@${mention.type}:${slug}${after} `;
    setInput(newVal);
    setMention({ active: false, type: null, query: "", startIndex: 0 });
    setSuggestions([]);
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  function dismissMention() {
    setMention({ active: false, type: null, query: "", startIndex: 0 });
    setSuggestions([]);
  }

  // ── Send ────────────────────────────────────────────────────────────────

  async function handleSend() {
    const text = input.trim();
    if (!text || isSending) return;

    const optimistic: ChatMessage = {
      id: `opt-${Date.now()}`,
      conversation_id: conversationId ?? "",
      role: "user",
      content: text,
      mentions_data: [],
      actions_data: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);
    setInput("");
    dismissMention();
    setIsSending(true);

    try {
      const resp = await apiRequest<SendMessageResponse>("/api/v1/chat/message", {
        method: "POST",
        body: {
          message: text,
          conversation_id: conversationId ?? undefined,
        },
      });
      setConversationId(resp.conversation_id);

      // Replace optimistic with real user message + add assistant reply
      const userMsg: ChatMessage = {
        id: resp.user_message_id,
        conversation_id: resp.conversation_id,
        role: "user",
        content: text,
        mentions_data: resp.resolved_mentions,
        actions_data: [],
        created_at: new Date().toISOString(),
      };
      const assistantMsg: ChatMessage = {
        id: resp.assistant_message_id,
        conversation_id: resp.conversation_id,
        role: "assistant",
        content: resp.reply,
        mentions_data: [],
        actions_data: [],
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev.filter((m) => m.id !== optimistic.id), userMsg, assistantMsg]);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Failed to send";
      const errBubble: ChatMessage = {
        id: `err-${Date.now()}`,
        conversation_id: conversationId ?? "",
        role: "assistant",
        content: `Error: ${errMsg}`,
        mentions_data: [],
        actions_data: [],
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev.filter((m) => m.id !== optimistic.id), errBubble]);
    } finally {
      setIsSending(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      dismissMention();
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (mention.active) return;
      handleSend();
    }
  }

  function newChat() {
    setConversationId(null);
    setMessages([]);
  }

  // ── Render ──────────────────────────────────────────────────────────────

  const filteredTypes = MENTION_TYPES.filter((t) =>
    t.startsWith(mention.query.toLowerCase())
  );

  return (
    <>
      {/* Floating button */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-brand text-white shadow-lg hover:bg-brand/90 transition-all"
        aria-label="Open AI chat"
      >
        {open ? (
          <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        ) : (
          <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
          </svg>
        )}
      </button>

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-24 right-6 z-50 flex w-96 flex-col rounded-2xl border border-slate-200 bg-white shadow-2xl"
          style={{ height: "520px" }}>

          {/* Header */}
          <div className="flex items-center justify-between rounded-t-2xl border-b border-slate-200 bg-slate-50 px-4 py-3">
            <div>
              <p className="text-sm font-semibold text-slate-900">AI Assistant</p>
              <p className="text-xs text-slate-500">Type @ to reference clients, leads, tasks…</p>
            </div>
            <button
              onClick={newChat}
              className="rounded-md px-2 py-1 text-xs text-slate-500 hover:bg-slate-200 transition-colors"
              title="New conversation"
            >
              New
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto space-y-3 p-4">
            {messages.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center text-center text-sm text-slate-400 gap-2">
                <svg className="h-10 w-10 opacity-30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                </svg>
                <p>Ask anything about your business.</p>
                <p className="text-xs">Use <span className="font-mono bg-slate-100 px-1 rounded">@client:Name</span> to reference data.</p>
              </div>
            )}
            {messages.map((msg) => (
              <MessageBubble key={msg.id} msg={msg} />
            ))}
            {isSending && (
              <div className="flex items-start gap-2">
                <div className="rounded-2xl rounded-tl-sm bg-slate-100 px-3 py-2 text-sm text-slate-500">
                  <span className="inline-flex gap-1">
                    <span className="animate-bounce">·</span>
                    <span className="animate-bounce" style={{ animationDelay: "0.1s" }}>·</span>
                    <span className="animate-bounce" style={{ animationDelay: "0.2s" }}>·</span>
                  </span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* @mention autocomplete */}
          {mention.active && (
            <div className="border-t border-slate-100 bg-white px-3 py-2">
              {mention.type === null ? (
                // Type picker
                <div>
                  <p className="mb-1 text-xs font-medium text-slate-500 uppercase tracking-wide">Reference a…</p>
                  <div className="flex flex-wrap gap-1">
                    {filteredTypes.map((t) => (
                      <button
                        key={t}
                        onMouseDown={(e) => { e.preventDefault(); selectMentionType(t); }}
                        className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 hover:bg-brand/10 hover:text-brand transition-colors"
                      >
                        @{t}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                // Entity picker
                <div>
                  <p className="mb-1 text-xs font-medium text-slate-500 uppercase tracking-wide">
                    @{mention.type} {loadingSuggestions ? "— searching…" : ""}
                  </p>
                  {suggestions.length === 0 && !loadingSuggestions ? (
                    <p className="text-xs text-slate-400 italic">No matches — keep typing</p>
                  ) : (
                    <div className="space-y-0.5 max-h-28 overflow-y-auto">
                      {suggestions.map((s) => (
                        <button
                          key={s.id}
                          onMouseDown={(e) => { e.preventDefault(); selectMentionEntity(s); }}
                          className="flex w-full items-center gap-2 rounded-md px-2 py-1 text-left hover:bg-slate-50 transition-colors"
                        >
                          <span className="text-sm font-medium text-slate-800 truncate">{s.label}</span>
                          {s.sub && <span className="text-xs text-slate-400 truncate">{s.sub}</span>}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Input */}
          <div className="border-t border-slate-200 p-3">
            <div className="flex items-end gap-2">
              <div className="relative" ref={emojiRef}>
                <button
                  type="button"
                  onClick={() => setShowEmoji((v) => !v)}
                  className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl text-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
                  aria-label="Emoji and stickers"
                >
                  🙂
                </button>
                {showEmoji && (
                  <div className="absolute bottom-full left-0 z-10 mb-2 grid max-h-48 w-56 grid-cols-6 gap-1 overflow-y-auto rounded-xl border border-slate-200 bg-white p-2 shadow-xl">
                    {STICKERS.map((s) => (
                      <button
                        key={s.key}
                        type="button"
                        title={s.label}
                        onClick={() => insertEmoji(s.emoji)}
                        className="flex aspect-square items-center justify-center rounded-lg text-xl hover:bg-slate-100 transition-colors"
                      >
                        {s.emoji}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <textarea
                ref={inputRef}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                rows={2}
                placeholder="Message… (Enter to send, Shift+Enter for newline)"
                className="flex-1 resize-none rounded-xl border border-slate-300 bg-slate-50 px-3 py-2 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand/40"
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || isSending}
                aria-label="Send"
                className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl bg-brand text-white hover:bg-brand/90 disabled:bg-slate-200 disabled:text-slate-400 transition-colors"
              >
                <span className="material-symbols-outlined text-[20px]">send</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
