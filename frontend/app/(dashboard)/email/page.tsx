"use client";

import DOMPurify from "dompurify";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { apiRequest } from "@/lib/api";
import { ComposeDraft, ComposePanel } from "@/components/email/ComposePanel";
import { EmailFolder, EmailSidebar } from "@/components/email/EmailSidebar";
import { EmailMessageRow } from "@/components/email/EmailMessageRow";
import type {
  EmailFolderListResponse,
  EmailListResponse,
  EmailMessageDetail,
  EmailMessageSummary,
  UserEmailAccount,
} from "@/types/api";

const EMPTY_DRAFT: ComposeDraft = { to: "", subject: "", body: "" };

const ROLE_DISPLAY: Record<string, { label: string; icon: string }> = {
  sent: { label: "Sent", icon: "send" },
  drafts: { label: "Drafts", icon: "draft" },
  trash: { label: "Trash", icon: "delete" },
};

const INPUT = "erp-input w-full px-3 py-2 text-sm";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="erp-panel p-6">
      <h2 className="mb-5 text-base font-semibold text-white">{title}</h2>
      {children}
    </div>
  );
}

function Field({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-400">{label}</label>
      {children}
    </div>
  );
}

function Alert({ ok, text }: { ok: boolean; text: string }) {
  return (
    <p className={`rounded-md border px-3 py-2 text-sm ${
      ok ? "border-emerald-900/40 bg-emerald-950/30 text-emerald-400"
         : "border-red-900/40 bg-red-950/30 text-red-400"
    }`}>
      {text}
    </p>
  );
}

function formatDate(date: string | null) {
  if (!date) return "";
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) return date;
  return parsed.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });
}

export default function EmailPage() {
  const [account, setAccount] = useState<UserEmailAccount | null>(null);
  const [loadingAccount, setLoadingAccount] = useState(true);

  const [imapHost, setImapHost] = useState("");
  const [imapPort, setImapPort] = useState("993");
  const [imapUsername, setImapUsername] = useState("");
  const [imapPassword, setImapPassword] = useState("");
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState("587");
  const [smtpUsername, setSmtpUsername] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [smtpFromEmail, setSmtpFromEmail] = useState("");
  const [smtpFromName, setSmtpFromName] = useState("");
  const [savingAccount, setSavingAccount] = useState(false);
  const [accountMsg, setAccountMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const [activeFolder, setActiveFolder] = useState("inbox");
  const [remoteFolders, setRemoteFolders] = useState<EmailFolderListResponse["items"]>([]);
  const [messages, setMessages] = useState<EmailMessageSummary[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [inboxError, setInboxError] = useState<string | null>(null);
  const [selectedUid, setSelectedUid] = useState<string | null>(null);
  const [selectedMessage, setSelectedMessage] = useState<EmailMessageDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [composeState, setComposeState] = useState<"closed" | "open" | "minimized">("closed");
  const [composeDraft, setComposeDraft] = useState<ComposeDraft>(EMPTY_DRAFT);

  const isConnected = !!account?.imap_host;

  const loadAccount = useCallback(() => {
    return apiRequest<UserEmailAccount>("/api/v1/email-account")
      .then((data) => {
        setAccount(data);
        if (data.imap_host) setImapHost(data.imap_host);
        if (data.imap_port) setImapPort(String(data.imap_port));
        if (data.imap_username) setImapUsername(data.imap_username);
        if (data.smtp_host) setSmtpHost(data.smtp_host);
        if (data.smtp_port) setSmtpPort(String(data.smtp_port));
        if (data.smtp_username) setSmtpUsername(data.smtp_username);
        if (data.smtp_from_email) setSmtpFromEmail(data.smtp_from_email);
        if (data.smtp_from_name) setSmtpFromName(data.smtp_from_name);
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    setLoadingAccount(true);
    loadAccount().finally(() => setLoadingAccount(false));
  }, [loadAccount]);

  const loadFolders = useCallback(() => {
    return apiRequest<EmailFolderListResponse>("/api/v1/email-account/folders")
      .then((data) => setRemoteFolders(data.items ?? []))
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (!isConnected) return;
    void loadFolders();
  }, [isConnected, loadFolders]);

  const loadMessages = useCallback(() => {
    return apiRequest<EmailListResponse>(`/api/v1/email-account/messages?folder=${encodeURIComponent(activeFolder)}`)
      .then((data) => {
        setMessages(data.items ?? []);
        setInboxError(null);
      })
      .catch((err) => setInboxError(err instanceof Error ? err.message : "Failed to load inbox."));
  }, [activeFolder]);

  useEffect(() => {
    if (!isConnected) return;
    setLoadingMessages(true);
    loadMessages().finally(() => setLoadingMessages(false));
    const interval = setInterval(loadMessages, 30_000);
    return () => clearInterval(interval);
  }, [isConnected, loadMessages]);

  useEffect(() => {
    if (!selectedUid) return;
    setLoadingDetail(true);
    setSelectedMessage(null);
    apiRequest<EmailMessageDetail>(
      `/api/v1/email-account/messages/${encodeURIComponent(selectedUid)}?folder=${encodeURIComponent(activeFolder)}`
    )
      .then(setSelectedMessage)
      .catch((err) => setInboxError(err instanceof Error ? err.message : "Failed to load message."))
      .finally(() => setLoadingDetail(false));
  }, [selectedUid, activeFolder]);

  function selectFolder(key: string) {
    setActiveFolder(key);
    setSelectedUid(null);
    setSelectedMessage(null);
  }

  async function handleToggleStar(uid: string, starred: boolean) {
    setMessages((prev) => prev.map((m) => (m.uid === uid ? { ...m, is_starred: starred } : m)));
    try {
      await apiRequest(`/api/v1/email-account/messages/${encodeURIComponent(uid)}/flags?folder=${encodeURIComponent(activeFolder)}`, {
        method: "PATCH", body: { is_starred: starred },
      });
    } catch (err) {
      setInboxError(err instanceof Error ? err.message : "Failed to update star.");
      void loadMessages();
    }
  }

  async function handleArchive(uid: string) {
    try {
      await apiRequest(`/api/v1/email-account/messages/${encodeURIComponent(uid)}/archive?folder=${encodeURIComponent(activeFolder)}`, {
        method: "POST",
      });
      setMessages((prev) => prev.filter((m) => m.uid !== uid));
      if (selectedUid === uid) { setSelectedUid(null); setSelectedMessage(null); }
    } catch (err) {
      setInboxError(err instanceof Error ? err.message : "Failed to archive message.");
    }
  }

  async function handleDelete(uid: string) {
    try {
      await apiRequest(`/api/v1/email-account/messages/${encodeURIComponent(uid)}?folder=${encodeURIComponent(activeFolder)}`, {
        method: "DELETE",
      });
      setMessages((prev) => prev.filter((m) => m.uid !== uid));
      if (selectedUid === uid) { setSelectedUid(null); setSelectedMessage(null); }
    } catch (err) {
      setInboxError(err instanceof Error ? err.message : "Failed to delete message.");
    }
  }

  async function handleConnect(e: FormEvent) {
    e.preventDefault();
    setSavingAccount(true);
    setAccountMsg(null);
    try {
      const body: Record<string, unknown> = {
        imap_host: imapHost.trim(),
        imap_port: Number(imapPort),
        imap_username: imapUsername.trim(),
        smtp_host: smtpHost.trim(),
        smtp_port: Number(smtpPort),
        smtp_username: smtpUsername.trim(),
        smtp_from_email: smtpFromEmail.trim(),
        smtp_from_name: smtpFromName.trim(),
      };
      if (imapPassword) body.imap_password = imapPassword;
      if (smtpPassword) body.smtp_password = smtpPassword;

      const updated = await apiRequest<UserEmailAccount>("/api/v1/email-account", { method: "PUT", body });
      setAccount(updated);
      setImapPassword("");
      setSmtpPassword("");
      setAccountMsg({ ok: true, text: "Email account connected." });
    } catch (err) {
      setAccountMsg({ ok: false, text: err instanceof Error ? err.message : "Failed to connect." });
    } finally {
      setSavingAccount(false);
    }
  }

  async function handleDisconnect() {
    try {
      await apiRequest("/api/v1/email-account", { method: "DELETE" });
      setAccount(null);
      setMessages([]);
      setSelectedUid(null);
      setSelectedMessage(null);
      setImapPassword("");
      setSmtpPassword("");
    } catch (err) {
      setAccountMsg({ ok: false, text: err instanceof Error ? err.message : "Failed to disconnect." });
    }
  }

  async function handleSend(to: string, subject: string, body: string) {
    await apiRequest("/api/v1/email-account/send", { method: "POST", body: { to, subject, body } });
  }

  function openCompose() {
    setComposeState("open");
  }

  function closeCompose() {
    setComposeState("closed");
    setComposeDraft(EMPTY_DRAFT);
  }

  function updateComposeDraft(patch: Partial<ComposeDraft>) {
    setComposeDraft((d) => ({ ...d, ...patch }));
  }

  if (loadingAccount) {
    return <div className="p-6 text-sm text-slate-400">Loading…</div>;
  }

  if (!isConnected) {
    return (
      <div className="mx-auto max-w-2xl space-y-6 p-6">
        <div>
          <h1 className="text-2xl font-semibold text-white">Email</h1>
          <p className="mt-1 text-sm text-slate-400">Connect your own work mailbox to read and send email from here.</p>
        </div>

        <form onSubmit={handleConnect} className="space-y-6">
          <Section title="Incoming mail (IMAP)">
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <div className="col-span-2">
                  <Field label="IMAP host" id="e-imap-host">
                    <input id="e-imap-host" required value={imapHost} onChange={(e) => setImapHost(e.target.value)}
                      className={INPUT} placeholder="imap.example.com" />
                  </Field>
                </div>
                <Field label="Port" id="e-imap-port">
                  <input id="e-imap-port" type="number" required value={imapPort} onChange={(e) => setImapPort(e.target.value)}
                    className={INPUT} placeholder="993" />
                </Field>
              </div>
              <Field label="Username" id="e-imap-username">
                <input id="e-imap-username" required value={imapUsername} onChange={(e) => setImapUsername(e.target.value)}
                  className={INPUT} placeholder="you@example.com" />
              </Field>
              <Field label="Password" id="e-imap-password">
                <input id="e-imap-password" type="password" value={imapPassword} onChange={(e) => setImapPassword(e.target.value)}
                  className={INPUT} placeholder="Required to connect" autoComplete="new-password" />
              </Field>
            </div>
          </Section>

          <Section title="Outgoing mail (SMTP)">
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-4">
                <div className="col-span-2">
                  <Field label="SMTP host" id="e-smtp-host">
                    <input id="e-smtp-host" required value={smtpHost} onChange={(e) => setSmtpHost(e.target.value)}
                      className={INPUT} placeholder="smtp.example.com" />
                  </Field>
                </div>
                <Field label="Port" id="e-smtp-port">
                  <input id="e-smtp-port" type="number" required value={smtpPort} onChange={(e) => setSmtpPort(e.target.value)}
                    className={INPUT} placeholder="587" />
                </Field>
              </div>
              <Field label="Username" id="e-smtp-username">
                <input id="e-smtp-username" required value={smtpUsername} onChange={(e) => setSmtpUsername(e.target.value)}
                  className={INPUT} placeholder="you@example.com" />
              </Field>
              <Field label="Password" id="e-smtp-password">
                <input id="e-smtp-password" type="password" value={smtpPassword} onChange={(e) => setSmtpPassword(e.target.value)}
                  className={INPUT} placeholder="Required to connect" autoComplete="new-password" />
              </Field>
              <div className="grid grid-cols-2 gap-4">
                <Field label="From email" id="e-smtp-from-email">
                  <input id="e-smtp-from-email" type="email" required value={smtpFromEmail} onChange={(e) => setSmtpFromEmail(e.target.value)}
                    className={INPUT} placeholder="you@example.com" />
                </Field>
                <Field label="From name" id="e-smtp-from-name">
                  <input id="e-smtp-from-name" required value={smtpFromName} onChange={(e) => setSmtpFromName(e.target.value)}
                    className={INPUT} placeholder="Your name" />
                </Field>
              </div>
            </div>
          </Section>

          {accountMsg && <Alert ok={accountMsg.ok} text={accountMsg.text} />}

          <div className="flex justify-end">
            <button type="submit" disabled={savingAccount}
              className="rounded-md bg-brand px-5 py-2 text-sm font-semibold text-white transition-opacity disabled:opacity-60">
              {savingAccount ? "Connecting…" : "Connect"}
            </button>
          </div>
        </form>
      </div>
    );
  }

  const unreadCount = messages.filter((m) => !m.is_read).length;
  const folders: EmailFolder[] = [
    { key: "inbox", label: "Inbox", icon: "inbox", count: activeFolder === "inbox" ? unreadCount : undefined },
    { key: "starred", label: "Starred", icon: "star" },
    ...Object.entries(ROLE_DISPLAY)
      .filter(([role]) => remoteFolders.some((f) => f.role === role))
      .map(([role, disp]) => ({ key: role, label: disp.label, icon: disp.icon })),
  ];
  const activeLabel = folders.find((f) => f.key === activeFolder)?.label ?? "Inbox";

  return (
    <div className="flex h-[calc(100vh-6.5rem)] gap-4 p-6">
      <EmailSidebar
        folders={folders}
        activeFolder={activeFolder}
        onSelectFolder={selectFolder}
        onCompose={openCompose}
        onDisconnect={handleDisconnect}
      />

      <div className="flex w-80 shrink-0 flex-col overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33]">
        <div className="border-b border-outline-variant px-4 py-3">
          <h2 className="text-sm font-semibold text-white">{activeLabel}</h2>
        </div>
        <div className="flex-1 overflow-y-auto">
          {loadingMessages && messages.length === 0 && (
            <p className="p-4 text-sm text-slate-400">Loading…</p>
          )}
          {!loadingMessages && messages.length === 0 && !inboxError && (
            <p className="p-4 text-sm text-slate-400">No messages.</p>
          )}
          {messages.map((m) => (
            <EmailMessageRow
              key={m.uid}
              message={m}
              selected={selectedUid === m.uid}
              onSelect={setSelectedUid}
              onToggleStar={handleToggleStar}
              onArchive={handleArchive}
              onDelete={handleDelete}
            />
          ))}
        </div>
      </div>

      <div className="flex flex-1 flex-col overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33]">
        {inboxError && (
          <div className="p-4">
            <Alert ok={false} text={inboxError} />
          </div>
        )}
        {!selectedUid && !inboxError && (
          <div className="flex flex-1 items-center justify-center text-sm text-slate-500">
            Select a message to read it.
          </div>
        )}
        {selectedUid && loadingDetail && (
          <div className="flex flex-1 items-center justify-center text-sm text-slate-500">Loading…</div>
        )}
        {selectedUid && selectedMessage && !loadingDetail && (
          <div className="flex-1 overflow-y-auto p-6">
            <h3 className="text-lg font-semibold text-white">{selectedMessage.subject || "(no subject)"}</h3>
            <p className="mt-1 text-sm text-slate-400">From: {selectedMessage.from_address}</p>
            <p className="text-sm text-slate-400">To: {selectedMessage.to_address}</p>
            <p className="text-xs text-slate-500">{formatDate(selectedMessage.date)}</p>
            {selectedMessage.attachments.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {selectedMessage.attachments.map((a, i) => (
                  <span
                    key={i}
                    className="flex items-center gap-1.5 rounded-md border border-outline-variant bg-white/5 px-2.5 py-1 text-xs text-slate-300"
                  >
                    <span className="material-symbols-outlined text-[14px]">attach_file</span>
                    {a.filename}
                    <span className="text-slate-500">({Math.max(1, Math.round(a.size / 1024))} KB)</span>
                  </span>
                ))}
              </div>
            )}
            <div className="mt-4 border-t border-outline-variant/50 pt-4 text-sm text-slate-200">
              {selectedMessage.body_html ? (
                <div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(selectedMessage.body_html) }} />
              ) : (
                <pre className="whitespace-pre-wrap font-sans">{selectedMessage.body_text ?? ""}</pre>
              )}
            </div>
          </div>
        )}
      </div>

      {composeState !== "closed" && (
        <ComposePanel
          state={composeState}
          draft={composeDraft}
          onDraftChange={updateComposeDraft}
          onMinimize={() => setComposeState("minimized")}
          onExpand={() => setComposeState("open")}
          onClose={closeCompose}
          onSend={handleSend}
        />
      )}
    </div>
  );
}
