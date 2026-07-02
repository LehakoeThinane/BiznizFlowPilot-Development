"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import { getStoredToken } from "@/lib/auth";
import { useUser } from "@/contexts/UserContext";
import type { Conversation, ConversationListResponse, DirectMessage, MessageListResponse } from "@/types/api";

interface OrgUser { id: string; email: string; first_name: string; last_name: string }
interface OrgUserListResp { items: OrgUser[]; total: number }

function initials(name: string) {
  return name.split(" ").map((p) => p[0]).join("").toUpperCase().slice(0, 2);
}

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

export default function MessagesPage() {
  const { user } = useUser();
  const token = getStoredToken();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const [messages, setMessages] = useState<DirectMessage[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);

  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  const [showNewMessage, setShowNewMessage] = useState(false);
  const [orgUsers, setOrgUsers] = useState<OrgUser[]>([]);
  const [startingWith, setStartingWith] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastMessageTimeRef = useRef<string | null>(null);

  const selected = conversations.find((c) => c.id === selectedId) ?? null;

  const loadConversations = useCallback(() => {
    return apiRequest<ConversationListResponse>("/api/v1/messaging/conversations", { authToken: token })
      .then((d) => setConversations(d.items ?? []))
      .catch(console.error);
  }, [token]);

  useEffect(() => {
    setLoadingConversations(true);
    loadConversations().finally(() => setLoadingConversations(false));
    const interval = setInterval(loadConversations, 10_000);
    return () => clearInterval(interval);
  }, [loadConversations]);

  const loadMessages = useCallback(
    (conversationId: string, since?: string) => {
      const qs = since ? `?since=${encodeURIComponent(since)}` : "";
      return apiRequest<MessageListResponse>(`/api/v1/messaging/conversations/${conversationId}/messages${qs}`, { authToken: token })
        .then((d) => {
          const incoming = d.items ?? [];
          if (incoming.length === 0) return incoming;
          setMessages((prev) => (since ? [...prev, ...incoming] : incoming));
          lastMessageTimeRef.current = incoming[incoming.length - 1].created_at;
          return incoming;
        });
    },
    [token],
  );

  // Load full history when a conversation is selected, then poll for new messages
  useEffect(() => {
    if (!selectedId) return;
    setLoadingMessages(true);
    setMessages([]);
    lastMessageTimeRef.current = null;
    loadMessages(selectedId)
      .then(() => apiRequest(`/api/v1/messaging/conversations/${selectedId}/read`, { method: "POST", authToken: token }).catch(() => {}))
      .finally(() => setLoadingMessages(false));

    const interval = setInterval(() => {
      loadMessages(selectedId, lastMessageTimeRef.current ?? undefined).then((incoming) => {
        if (incoming.length > 0) {
          apiRequest(`/api/v1/messaging/conversations/${selectedId}/read`, { method: "POST", authToken: token }).catch(() => {});
          void loadConversations();
        }
      });
    }, 4_000);
    return () => clearInterval(interval);
  }, [selectedId, loadMessages, loadConversations, token]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function openNewMessage() {
    setShowNewMessage(true);
    apiRequest<OrgUserListResp>("/api/v1/users", { authToken: token })
      .then((d) => setOrgUsers((d.items ?? []).filter((u) => u.id !== user?.user_id)))
      .catch(console.error);
  }

  async function startConversation(otherUserId: string) {
    setStartingWith(otherUserId);
    try {
      const convo = await apiRequest<Conversation>("/api/v1/messaging/conversations", {
        method: "POST", authToken: token, body: { user_id: otherUserId },
      });
      setShowNewMessage(false);
      await loadConversations();
      setSelectedId(convo.id);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to start conversation.");
    } finally {
      setStartingWith(null);
    }
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || !selectedId || sending) return;
    setSending(true);
    setInput("");
    try {
      const msg = await apiRequest<DirectMessage>(`/api/v1/messaging/conversations/${selectedId}/messages`, {
        method: "POST", authToken: token, body: { content: text },
      });
      setMessages((prev) => [...prev, msg]);
      lastMessageTimeRef.current = msg.created_at;
      void loadConversations();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to send message.");
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex h-[calc(100vh-6.5rem)] gap-4 p-6">
      {/* ── Conversation list ─────────────────────────────────────────────── */}
      <div className="flex w-80 shrink-0 flex-col overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33]">
        <div className="flex items-center justify-between border-b border-outline-variant px-4 py-3.5">
          <p className="text-sm font-semibold text-white">Messages</p>
          <button
            type="button"
            onClick={openNewMessage}
            className="rounded-md bg-white/10 px-2 py-1 text-xs font-medium text-white hover:bg-white/20 transition-colors"
          >
            + New
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {loadingConversations ? (
            <div className="px-4 py-8 text-center text-xs text-slate-500">Loading…</div>
          ) : conversations.length === 0 ? (
            <div className="px-4 py-10 text-center text-xs text-slate-500">
              No conversations yet. Click <strong className="text-white">+ New</strong> to message a colleague.
            </div>
          ) : (
            conversations.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => setSelectedId(c.id)}
                className={`flex w-full items-center gap-3 border-b border-outline-variant/60 px-4 py-3 text-left transition-colors hover:bg-white/5 ${
                  selectedId === c.id ? "bg-white/8" : ""
                }`}
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white">
                  {initials(c.other_user.full_name)}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-white">{c.other_user.full_name}</p>
                  <p className="truncate text-xs text-slate-500">
                    {c.last_message ? c.last_message.content : "No messages yet"}
                  </p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  {c.last_message && <span className="text-[10px] text-slate-500">{timeAgo(c.last_message.created_at)}</span>}
                  {c.unread_count > 0 && (
                    <span className="flex h-4.5 min-w-[1.125rem] items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white">
                      {c.unread_count > 9 ? "9+" : c.unread_count}
                    </span>
                  )}
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* ── Thread ───────────────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33]">
        {!selected ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-sm text-slate-500">
            <span className="material-symbols-outlined text-4xl opacity-30">chat</span>
            <p>Select a conversation, or start a new one.</p>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-3 border-b border-outline-variant px-5 py-3.5">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white">
                {initials(selected.other_user.full_name)}
              </div>
              <div>
                <p className="text-sm font-semibold text-white">{selected.other_user.full_name}</p>
                <p className="text-xs text-slate-500">{selected.other_user.email}</p>
              </div>
            </div>

            <div className="flex-1 space-y-3 overflow-y-auto p-4">
              {loadingMessages ? (
                <div className="py-8 text-center text-xs text-slate-500">Loading…</div>
              ) : messages.length === 0 ? (
                <div className="py-8 text-center text-xs text-slate-500">
                  No messages yet. Say hello to {selected.other_user.full_name.split(" ")[0]}.
                </div>
              ) : (
                messages.map((m) => {
                  const isMine = m.sender_id === user?.user_id;
                  return (
                    <div key={m.id} className={`flex flex-col ${isMine ? "items-end" : "items-start"} gap-1`}>
                      <div
                        className={`max-w-[75%] whitespace-pre-wrap break-words rounded-2xl px-3 py-2 text-sm ${
                          isMine
                            ? "rounded-tr-sm bg-blue-600 text-white"
                            : "rounded-tl-sm bg-white/10 text-slate-100"
                        }`}
                      >
                        {m.content}
                      </div>
                      <span className="px-1 text-[10px] text-slate-500">{formatTime(m.created_at)}</span>
                    </div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="border-t border-outline-variant p-3">
              <div className="flex items-end gap-2">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={2}
                  placeholder="Message… (Enter to send, Shift+Enter for newline)"
                  className="erp-input flex-1 resize-none px-3 py-2 text-sm"
                />
                <button
                  type="button"
                  onClick={handleSend}
                  disabled={!input.trim() || sending}
                  className="erp-button-primary flex h-9 w-9 shrink-0 items-center justify-center rounded-xl p-0 disabled:opacity-40 transition-colors"
                  aria-label="Send"
                >
                  <svg className="h-4 w-4 rotate-90" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                  </svg>
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* ── New Message Modal ─────────────────────────────────────────────── */}
      {showNewMessage && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
            <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
              <h2 className="text-base font-semibold text-white">New Message</h2>
              <button
                type="button"
                aria-label="Close"
                onClick={() => setShowNewMessage(false)}
                className="text-slate-400 hover:text-white"
              >
                ×
              </button>
            </div>
            <div className="max-h-80 overflow-y-auto py-2">
              {orgUsers.length === 0 ? (
                <p className="px-6 py-4 text-sm text-slate-500">No other colleagues in this business yet.</p>
              ) : (
                orgUsers.map((u) => (
                  <button
                    key={u.id}
                    type="button"
                    disabled={startingWith === u.id}
                    onClick={() => startConversation(u.id)}
                    className="flex w-full items-center gap-3 px-6 py-2.5 text-left transition-colors hover:bg-white/5 disabled:opacity-50"
                  >
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-600 text-xs font-semibold text-white">
                      {initials(`${u.first_name} ${u.last_name}`)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-white">{u.first_name} {u.last_name}</p>
                      <p className="truncate text-xs text-slate-500">{u.email}</p>
                    </div>
                    {startingWith === u.id && <span className="text-xs text-slate-500">…</span>}
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
