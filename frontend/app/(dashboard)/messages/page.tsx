"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import EmojiPicker, { EmojiStyle, Theme } from "emoji-picker-react";
import { apiRequest } from "@/lib/api";
import { getStoredToken } from "@/lib/auth";
import { playNotificationSound, unlockNotificationSound } from "@/lib/notification-sound";
import { useUser } from "@/contexts/UserContext";
import type { BusinessUser, Conversation, ConversationListResponse, Customer, DirectMessage, MeetingCallType, MessageListResponse, OtherUser, Poll } from "@/types/api";
import { Avatar } from "@/components/Avatar";
import { AttachmentMenu, type AttachmentAction } from "@/components/messages/AttachmentMenu";
import { AudioAttachModal } from "@/components/messages/AudioAttachModal";
import { CameraCaptureModal } from "@/components/messages/CameraCaptureModal";
import { ContactPickerModal } from "@/components/messages/ContactPickerModal";
import { EventComposerModal } from "@/components/messages/EventComposerModal";
import { MessageBubble } from "@/components/messages/MessageBubble";
import { PollComposerModal } from "@/components/messages/PollComposerModal";
import { StickerPickerModal } from "@/components/messages/StickerPickerModal";

type ModalAction = Exclude<AttachmentAction, "document" | "media">;

interface OrgUserListResp { items: BusinessUser[]; total: number }

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
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });
}

export default function MessagesPage() {
  const { user } = useUser();
  const token = getStoredToken();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [profileUser, setProfileUser] = useState<OtherUser | null>(null);

  const [messages, setMessages] = useState<DirectMessage[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);

  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);

  const [showNewMessage, setShowNewMessage] = useState(false);
  const [orgUsers, setOrgUsers] = useState<BusinessUser[]>([]);
  const [startingWith, setStartingWith] = useState<string | null>(null);

  const [showAttachmentMenu, setShowAttachmentMenu] = useState(false);
  const [activeModal, setActiveModal] = useState<ModalAction | null>(null);
  const [showEmoji, setShowEmoji] = useState(false);
  const documentInputRef = useRef<HTMLInputElement>(null);
  const mediaInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const emojiRef = useRef<HTMLDivElement>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastMessageTimeRef = useRef<string | null>(null);
  const pollingRef = useRef(false);
  const messagesRef = useRef<DirectMessage[]>([]);

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
          setMessages((prev) => {
            if (!since) return incoming;
            const existingIds = new Set(prev.map((m) => m.id));
            const deduped = incoming.filter((m) => !existingIds.has(m.id));
            return deduped.length > 0 ? [...prev, ...deduped] : prev;
          });
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
      .then(() => apiRequest(`/api/v1/messaging/conversations/${selectedId}/read`, { method: "POST", authToken: token }).catch(() => { }))
      .finally(() => setLoadingMessages(false));

    const interval = setInterval(() => {
      if (pollingRef.current) return;
      pollingRef.current = true;
      loadMessages(selectedId, lastMessageTimeRef.current ?? undefined)
        .then((incoming) => {
          if (incoming.length > 0) {
            const newIncoming = incoming.filter((message) => !messagesRef.current.some((existing) => existing.id === message.id));
            if (newIncoming.some((message) => message.sender_id !== user?.user_id)) {
              playNotificationSound();
            }
            apiRequest(`/api/v1/messaging/conversations/${selectedId}/read`, { method: "POST", authToken: token }).catch(() => { });
            void loadConversations();
          }
        })
        .finally(() => {
          pollingRef.current = false;
        });
    }, 4_000);
    return () => clearInterval(interval);
  }, [selectedId, loadMessages, loadConversations, token]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  // Poll-type messages carry live vote tallies that only change via votes, not
  // new messages - the `since`-based fetch above won't refresh them, so poll
  // each currently-visible poll's tally on the same cadence separately.
  useEffect(() => {
    if (!selectedId) return;
    const interval = setInterval(() => {
      const pollIds = Array.from(
        new Set(messagesRef.current.filter((m) => m.message_type === "poll" && m.poll).map((m) => m.poll!.id)),
      );
      if (pollIds.length === 0) return;
      Promise.all(
        pollIds.map((id) => apiRequest<Poll>(`/api/v1/messaging/polls/${id}`, { authToken: token }).catch(() => null)),
      ).then((results) => {
        setMessages((cur) =>
          cur.map((m) => {
            if (m.message_type !== "poll" || !m.poll) return m;
            const updated = results.find((r) => r && r.id === m.poll!.id);
            return updated ? { ...m, poll: updated } : m;
          }),
        );
      });
    }, 4_000);
    return () => clearInterval(interval);
  }, [selectedId, token]);

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
    unlockNotificationSound();
    const text = input.trim();
    if (!text || !selectedId || sending) return;
    setSending(true);
    setInput("");
    try {
      const msg = await apiRequest<DirectMessage>(`/api/v1/messaging/conversations/${selectedId}/messages`, {
        method: "POST", authToken: token, body: { content: text },
      });
      setMessages((prev) => (prev.some((m) => m.id === msg.id) ? prev : [...prev, msg]));
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

  useEffect(() => {
    if (!showEmoji) return;
    function handleClick(e: MouseEvent) {
      if (emojiRef.current && !emojiRef.current.contains(e.target as Node)) setShowEmoji(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showEmoji]);

  function insertEmoji(emoji: string) {
    const el = textareaRef.current;
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

  function appendMessage(msg: DirectMessage) {
    setMessages((prev) => (prev.some((m) => m.id === msg.id) ? prev : [...prev, msg]));
    lastMessageTimeRef.current = msg.created_at;
    void loadConversations();
  }

  function handleAttachmentAction(action: AttachmentAction) {
    if (action === "document") documentInputRef.current?.click();
    else if (action === "media") mediaInputRef.current?.click();
    else setActiveModal(action);
  }

  function handleFileInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) void uploadAttachment(file);
  }

  async function uploadAttachment(file: File) {
    if (!selectedId) return;
    const formData = new FormData();
    formData.append("file", file);
    try {
      const msg = await apiRequest<DirectMessage>(`/api/v1/messaging/conversations/${selectedId}/attachments`, {
        method: "POST", authToken: token, body: formData,
      });
      appendMessage(msg);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to upload attachment.");
    }
  }

  async function handleSelectContact(customer: Customer) {
    if (!selectedId) return;
    try {
      const msg = await apiRequest<DirectMessage>(`/api/v1/messaging/conversations/${selectedId}/contacts`, {
        method: "POST", authToken: token, body: { customer_id: customer.id },
      });
      appendMessage(msg);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to share contact.");
    }
  }

  async function handleSendSticker(stickerKey: string) {
    if (!selectedId) return;
    try {
      const msg = await apiRequest<DirectMessage>(`/api/v1/messaging/conversations/${selectedId}/stickers`, {
        method: "POST", authToken: token, body: { sticker_key: stickerKey },
      });
      appendMessage(msg);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to send sticker.");
    }
  }

  async function handleCreatePoll(question: string, options: string[], allowMultiple: boolean) {
    if (!selectedId) throw new Error("No conversation selected.");
    const msg = await apiRequest<DirectMessage>(`/api/v1/messaging/conversations/${selectedId}/polls`, {
      method: "POST", authToken: token, body: { question, options, allow_multiple: allowMultiple },
    });
    appendMessage(msg);
  }

  async function handleVote(pollId: string, optionIds: string[]) {
    try {
      const poll = await apiRequest<Poll>(`/api/v1/messaging/polls/${pollId}/vote`, {
        method: "POST", authToken: token, body: { option_ids: optionIds },
      });
      setMessages((prev) => prev.map((m) => (m.message_type === "poll" && m.poll?.id === pollId ? { ...m, poll } : m)));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to vote.");
    }
  }

  async function handleShareExistingEvent(meetingId: string) {
    if (!selectedId) throw new Error("No conversation selected.");
    const msg = await apiRequest<DirectMessage>(`/api/v1/messaging/conversations/${selectedId}/events/share`, {
      method: "POST", authToken: token, body: { meeting_id: meetingId },
    });
    appendMessage(msg);
  }

  async function handleScheduleNewEvent(data: { title: string; description: string; start: string; end: string; call_type: MeetingCallType }) {
    if (!selectedId) throw new Error("No conversation selected.");
    const msg = await apiRequest<DirectMessage>(`/api/v1/messaging/conversations/${selectedId}/events/schedule`, {
      method: "POST",
      authToken: token,
      body: {
        title: data.title,
        description: data.description.trim() || null,
        start_time: new Date(data.start).toISOString(),
        end_time: new Date(data.end).toISOString(),
        call_type: data.call_type,
        participant_user_ids: [],
      },
    });
    appendMessage(msg);
  }

  return (
    <div className="flex h-[calc(100vh-6.5rem)] min-h-0 flex-col gap-3 p-3 sm:p-4 md:flex-row md:gap-4 md:p-6">
      {/* ── Conversation list ─────────────────────────────────────────────── */}
      <div className={`${selected ? "hidden md:flex" : "flex"} h-48 min-h-0 w-full shrink-0 flex-col overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] md:h-auto md:w-80`}>
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
                className={`flex w-full items-center gap-3 border-b border-outline-variant/60 px-4 py-3 text-left transition-colors hover:bg-white/5 ${selectedId === c.id ? "bg-white/8" : ""
                  }`}
              >
                <Avatar
                  name={c.other_user.full_name}
                  avatarUrl={c.other_user.avatar_url}
                  presence={c.other_user.presence}
                  onClick={() => setProfileUser(c.other_user)}
                />
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
      <div className={`${selected ? "flex" : "hidden md:flex"} min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33]`}>
        {!selected ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-sm text-slate-500">
            <span className="material-symbols-outlined text-4xl opacity-30">chat</span>
            <p>Select a conversation, or start a new one.</p>
          </div>
        ) : (
          <>
            <div className="flex min-w-0 items-center gap-3 border-b border-outline-variant px-4 py-3.5 sm:px-5">
              <button
                type="button"
                onClick={() => setSelectedId(null)}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-slate-400 transition-colors hover:bg-white/10 hover:text-white md:hidden"
                aria-label="Back to conversations"
              >
                <span className="material-symbols-outlined">arrow_back</span>
              </button>
              <Avatar
                name={selected.other_user.full_name}
                avatarUrl={selected.other_user.avatar_url}
                presence={selected.other_user.presence}
                size="sm"
                onClick={() => setProfileUser(selected.other_user)}
              />
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">{selected.other_user.full_name}</p>
                <p className="truncate text-xs text-slate-500">
                  {selected.other_user.presence.status === "custom" && selected.other_user.presence.status_text
                    ? selected.other_user.presence.status_text
                    : selected.other_user.email}
                </p>
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
                      <MessageBubble message={m} isMine={isMine} onVote={handleVote} />
                      <span className="px-1 text-[10px] text-slate-500">{formatTime(m.created_at)}</span>
                    </div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="border-t border-outline-variant p-3">
              <div className="flex items-end gap-2">
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setShowAttachmentMenu((v) => !v)}
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
                    aria-label="Attach"
                  >
                    <span className="material-symbols-outlined">add</span>
                  </button>
                  {showAttachmentMenu && (
                    <AttachmentMenu
                      onSelect={handleAttachmentAction}
                      onClose={() => setShowAttachmentMenu(false)}
                    />
                  )}
                  <input ref={documentInputRef} type="file" className="hidden" onChange={handleFileInputChange} />
                  <input ref={mediaInputRef} type="file" accept="image/*,video/*" className="hidden" onChange={handleFileInputChange} />
                </div>
                <div className="relative" ref={emojiRef}>
                  <button
                    type="button"
                    onClick={() => setShowEmoji((v) => !v)}
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
                    aria-label="Emoji"
                  >
                    <span className="material-symbols-outlined">mood</span>
                  </button>
                  {showEmoji && (
                    <div className="absolute bottom-full left-0 z-10 mb-2 max-w-[calc(100vw-2rem)] overflow-hidden rounded-xl border border-outline-variant shadow-2xl">
                      <EmojiPicker
                        onEmojiClick={(emojiData) => insertEmoji(emojiData.emoji)}
                        emojiStyle={EmojiStyle.NATIVE}
                        theme={Theme.DARK}
                        width={280}
                        height={380}
                        previewConfig={{ showPreview: false }}
                        lazyLoadEmojis
                      />
                    </div>
                  )}
                </div>
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={2}
                  placeholder="Message… (Enter to send, Shift+Enter for newline)"
                  className="erp-input min-w-0 flex-1 resize-none px-3 py-2 text-sm"
                />
                <button
                  type="button"
                  onClick={handleSend}
                  disabled={!input.trim() || sending}
                  className="erp-button-primary flex h-9 w-9 shrink-0 items-center justify-center rounded-xl p-0 disabled:bg-slate-600 disabled:text-slate-400 disabled:shadow-none transition-colors"
                  aria-label="Send"
                >
                  <span className="material-symbols-outlined text-[20px]">send</span>
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
                    <Avatar name={`${u.first_name} ${u.last_name}`} avatarUrl={u.avatar_url} presence={u.presence} size="sm" />
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

      {profileUser && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-3 sm:items-center sm:p-4" onClick={() => setProfileUser(null)}>
          <div
            className="w-full max-w-sm rounded-2xl border border-outline-variant bg-[#0f1c33] p-5 shadow-2xl"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="profile-dialog-title"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex min-w-0 items-center gap-3">
                <Avatar name={profileUser.full_name} avatarUrl={profileUser.avatar_url} presence={profileUser.presence} size="md" />
                <div className="min-w-0">
                  <h2 id="profile-dialog-title" className="truncate text-base font-semibold text-white">{profileUser.full_name}</h2>
                  <p className="truncate text-xs text-slate-400">{profileUser.email}</p>
                </div>
              </div>
              <button type="button" onClick={() => setProfileUser(null)} className="text-slate-400 hover:text-white" aria-label="Close profile">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <div className="mt-5 rounded-xl border border-outline-variant/70 bg-white/5 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Availability</p>
              <p className="mt-2 text-sm text-white">
                {profileUser.presence.status === "custom" && profileUser.presence.status_text
                  ? profileUser.presence.status_text
                  : profileUser.presence.status}
              </p>
            </div>
            <button type="button" onClick={() => { setProfileUser(null); setSelectedId(profileUser.id); }} className="mt-4 w-full rounded-xl bg-brand px-4 py-2.5 text-sm font-semibold text-white hover:opacity-90">
              Open conversation
            </button>
          </div>
        </div>
      )}

      {activeModal === "camera" && (
        <CameraCaptureModal onSend={uploadAttachment} onClose={() => setActiveModal(null)} />
      )}
      {activeModal === "audio" && (
        <AudioAttachModal onSend={uploadAttachment} onClose={() => setActiveModal(null)} />
      )}
      {activeModal === "contact" && (
        <ContactPickerModal token={token} onSelect={handleSelectContact} onClose={() => setActiveModal(null)} />
      )}
      {activeModal === "poll" && (
        <PollComposerModal onCreate={handleCreatePoll} onClose={() => setActiveModal(null)} />
      )}
      {activeModal === "event" && (
        <EventComposerModal
          token={token}
          onShareExisting={handleShareExistingEvent}
          onScheduleNew={handleScheduleNewEvent}
          onClose={() => setActiveModal(null)}
        />
      )}
      {activeModal === "sticker" && (
        <StickerPickerModal onSelect={handleSendSticker} onClose={() => setActiveModal(null)} />
      )}
    </div>
  );
}
