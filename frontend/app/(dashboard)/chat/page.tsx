"use client";

import { useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import { ActionCard } from "@/components/chat/ActionCard";
import type {
  ChatAction,
  ChatConversation,
  ChatConversationDetail,
  ChatMessage,
  MentionSearchResult,
  ResolvedMention,
  SendMessageResponse,
} from "@/types/api";

const MENTION_TYPES = ["client", "lead", "task", "user", "product", "supplier"];

function MentionBadge({ mention }: { mention: ResolvedMention }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
        mention.found ? "bg-brand/10 text-brand" : "bg-red-950 text-red-400"
      }`}
    >
      @{mention.type}:{mention.display_name}
      {!mention.found && " ✗"}
    </span>
  );
}

function MessageBubble({
  msg,
  onActionUpdate,
}: {
  msg: ChatMessage;
  onActionUpdate: (messageId: string, updated: ChatAction) => void;
}) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex flex-col ${isUser ? "items-end" : "items-start"} gap-1 max-w-2xl ${isUser ? "ml-auto" : "mr-auto"}`}>
      {msg.mentions_data?.length > 0 && isUser && (
        <div className="flex flex-wrap gap-1 justify-end">
          {msg.mentions_data.map((m, i) => (
            <MentionBadge key={i} mention={m} />
          ))}
        </div>
      )}
      <div
        className={`rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap break-words ${
          isUser
            ? "bg-brand text-white rounded-tr-sm"
            : "bg-[#1f1f1f] border border-[#333] text-white rounded-tl-sm shadow-sm"
        }`}
      >
        {msg.content}
      </div>
      {!isUser && msg.actions_data?.length > 0 && (
        <div className="w-full">
          {msg.actions_data.map((action) => (
            <ActionCard
              key={action.id}
              messageId={msg.id}
              action={action}
              onUpdate={(updated) => onActionUpdate(msg.id, updated)}
            />
          ))}
        </div>
      )}
      <span className="text-xs text-[#555]">
        {new Date(msg.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false })}
      </span>
    </div>
  );
}

export default function ChatPage() {
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isLoadingConvs, setIsLoadingConvs] = useState(true);

  const [mention, setMention] = useState<{
    active: boolean; type: string | null; query: string; startIndex: number;
  }>({ active: false, type: null, query: "", startIndex: 0 });
  const [suggestions, setSuggestions] = useState<MentionSearchResult[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function loadConversations() {
    setIsLoadingConvs(true);
    try {
      const convs = await apiRequest<ChatConversation[]>("/api/v1/chat/conversations");
      setConversations(convs);
    } catch {
      // silently fail
    } finally {
      setIsLoadingConvs(false);
    }
  }

  async function openConversation(id: string) {
    setActiveConvId(id);
    try {
      const detail = await apiRequest<ChatConversationDetail>(`/api/v1/chat/conversations/${id}`);
      setMessages(detail.messages);
    } catch {
      setMessages([]);
    }
  }

  function newConversation() {
    setActiveConvId(null);
    setMessages([]);
  }

  function updateMessageAction(messageId: string, updated: ChatAction) {
    setMessages((prev) =>
      prev.map((m) =>
        m.id !== messageId
          ? m
          : { ...m, actions_data: m.actions_data.map((a) => (a.id === updated.id ? updated : a)) },
      ),
    );
  }

  // ── @mention handling ─────────────────────────────────────────────────────

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
    const fragment = before.slice(atIdx + 1);
    const colonIdx = fragment.indexOf(":");
    if (colonIdx === -1) {
      setMention({ active: true, type: null, query: fragment, startIndex: atIdx });
      setSuggestions([]);
    } else {
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
        `/api/v1/chat/mentions/search?type=${encodeURIComponent(type)}&q=${encodeURIComponent(q)}`
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
    setInput(`${before}@${mType}:${after}`);
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
    setInput(`${before}@${mention.type}:${slug}${after} `);
    setMention({ active: false, type: null, query: "", startIndex: 0 });
    setSuggestions([]);
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  function dismissMention() {
    setMention({ active: false, type: null, query: "", startIndex: 0 });
    setSuggestions([]);
  }

  // ── Send ──────────────────────────────────────────────────────────────────

  async function handleSend() {
    const text = input.trim();
    if (!text || isSending) return;

    const optimistic: ChatMessage = {
      id: `opt-${Date.now()}`,
      conversation_id: activeConvId ?? "",
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
        body: { message: text, conversation_id: activeConvId ?? undefined },
      });

      if (!activeConvId) {
        setActiveConvId(resp.conversation_id);
        loadConversations();
      }

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
        actions_data: resp.actions,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== optimistic.id),
        userMsg,
        assistantMsg,
      ]);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Failed to send";
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== optimistic.id),
        {
          id: `err-${Date.now()}`,
          conversation_id: activeConvId ?? "",
          role: "assistant",
          content: `Error: ${errMsg}`,
          mentions_data: [],
          actions_data: [],
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsSending(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") { dismissMention(); return; }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (mention.active) return;
      handleSend();
    }
  }

  const filteredTypes = MENTION_TYPES.filter((t) =>
    t.startsWith(mention.query.toLowerCase())
  );

  return (
    <div className="flex h-[calc(100vh-6rem)] overflow-hidden rounded-xl border border-[#222] bg-[#141414] shadow-sm">
      {/* Sidebar — conversation list */}
      <aside className="w-64 flex-shrink-0 border-r border-[#222] flex flex-col">
        <div className="flex items-center justify-between border-b border-[#222] px-4 py-3">
          <h2 className="text-sm font-semibold text-white">Conversations</h2>
          <button
            onClick={newConversation}
            className="rounded-md bg-brand px-2 py-1 text-xs font-medium text-white hover:bg-brand/90"
          >
            + New
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {isLoadingConvs ? (
            <p className="px-4 py-3 text-xs text-[#555]">Loading…</p>
          ) : conversations.length === 0 ? (
            <p className="px-4 py-6 text-center text-xs text-[#555]">No conversations yet.</p>
          ) : (
            conversations.map((c) => (
              <button
                key={c.id}
                onClick={() => openConversation(c.id)}
                className={`w-full px-4 py-3 text-left hover:bg-[#1f1f1f] transition-colors border-b border-[#222] ${
                  activeConvId === c.id ? "bg-brand/5 border-l-2 border-l-brand" : ""
                }`}
              >
                <p className="text-xs font-medium text-white truncate">
                  {c.title || "Conversation"}
                </p>
                <p className="text-xs text-[#555] mt-0.5">
                  {new Date(c.updated_at).toLocaleDateString()}
                </p>
              </button>
            ))
          )}
        </div>
      </aside>

      {/* Main chat area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header */}
        <div className="border-b border-[#222] bg-[#0f0f0f] px-6 py-3">
          <h1 className="text-sm font-semibold text-white">AI Assistant</h1>
          <p className="text-xs text-[#666]">
            Use <span className="font-mono bg-[#222] px-1 rounded">@client:Name</span>,{" "}
            <span className="font-mono bg-[#222] px-1 rounded">@lead:...</span>,{" "}
            <span className="font-mono bg-[#222] px-1 rounded">@task:...</span> to reference your data.
          </p>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto space-y-4 p-6">
          {messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center text-center gap-3">
              <div className="rounded-full bg-brand/10 p-4">
                <svg className="h-8 w-8 text-brand" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                </svg>
              </div>
              <div>
                <p className="font-medium text-white">How can I help you today?</p>
                <p className="mt-1 text-sm text-[#666]">
                  Ask about your business data or use @mentions to pull in context.
                </p>
              </div>
              <div className="mt-2 flex flex-wrap justify-center gap-2">
                {[
                  "Summarize my open leads",
                  "What tasks are overdue?",
                  "Show me recent suppliers",
                ].map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => { setInput(prompt); inputRef.current?.focus(); }}
                    className="rounded-full border border-[#333] px-3 py-1.5 text-xs text-[#aaa] hover:bg-[#222] transition-colors"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} onActionUpdate={updateMessageAction} />
          ))}
          {isSending && (
            <div className="flex items-start mr-auto max-w-2xl">
              <div className="rounded-2xl rounded-tl-sm border border-[#333] bg-[#1f1f1f] px-4 py-3 text-sm shadow-sm">
                <span className="inline-flex gap-1 text-[#555]">
                  <span className="animate-bounce">·</span>
                  <span className="animate-bounce" style={{ animationDelay: "0.15s" }}>·</span>
                  <span className="animate-bounce" style={{ animationDelay: "0.3s" }}>·</span>
                </span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* @mention autocomplete */}
        {mention.active && (
          <div className="border-t border-[#222] bg-[#141414] px-4 py-2">
            {mention.type === null ? (
              <div>
                <p className="mb-1.5 text-xs font-medium text-[#666] uppercase tracking-wide">Reference a…</p>
                <div className="flex flex-wrap gap-1.5">
                  {filteredTypes.map((t) => (
                    <button
                      key={t}
                      onMouseDown={(e) => { e.preventDefault(); selectMentionType(t); }}
                      className="rounded-full bg-[#222] px-3 py-1 text-xs font-medium text-[#aaa] hover:bg-brand/10 hover:text-brand transition-colors"
                    >
                      @{t}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div>
                <p className="mb-1 text-xs font-medium text-[#666] uppercase tracking-wide">
                  @{mention.type} {loadingSuggestions ? "— searching…" : ""}
                </p>
                {suggestions.length === 0 && !loadingSuggestions ? (
                  <p className="text-xs text-[#555] italic">No matches — keep typing</p>
                ) : (
                  <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
                    {suggestions.map((s) => (
                      <button
                        key={s.id}
                        onMouseDown={(e) => { e.preventDefault(); selectMentionEntity(s); }}
                        className="flex items-center gap-1.5 rounded-full border border-[#333] bg-[#1f1f1f] px-3 py-1 text-xs hover:border-brand/40 hover:bg-brand/5 transition-colors"
                      >
                        <span className="font-medium text-white">{s.label}</span>
                        {s.sub && <span className="text-[#666]">{s.sub}</span>}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Input */}
        <div className="border-t border-[#222] p-4">
          <div className="flex items-end gap-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              rows={3}
              placeholder="Ask anything… type @ to reference your data (Enter to send, Shift+Enter for newline)"
              className="flex-1 resize-none rounded-xl border border-[#333] bg-[#0f0f0f] px-4 py-3 text-sm text-white placeholder:text-[#555] focus:outline-none focus:ring-2 focus:ring-brand/40"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isSending}
              className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-brand text-white hover:bg-brand/90 disabled:opacity-40 transition-colors"
            >
              <svg className="h-5 w-5 rotate-90" viewBox="0 0 24 24" fill="currentColor">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
