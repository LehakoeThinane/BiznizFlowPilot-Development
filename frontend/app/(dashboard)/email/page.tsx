"use client";

import DOMPurify from "dompurify";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { apiRequest } from "@/lib/api";
import { ComposeModal } from "@/components/email/ComposeModal";
import type { EmailListResponse, EmailMessageDetail, EmailMessageSummary, UserEmailAccount } from "@/types/api";

const INPUT =
  "w-full rounded-md border border-[#333] bg-[#0f0f0f] px-3 py-2 text-sm text-white outline-none placeholder:text-[#555] focus:ring-2 focus:ring-brand/50";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-[#222] bg-[#141414] p-6">
      <h2 className="mb-5 text-base font-semibold text-white">{title}</h2>
      {children}
    </div>
  );
}

function Field({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-[#aaa]">{label}</label>
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

  const [messages, setMessages] = useState<EmailMessageSummary[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [inboxError, setInboxError] = useState<string | null>(null);
  const [selectedUid, setSelectedUid] = useState<string | null>(null);
  const [selectedMessage, setSelectedMessage] = useState<EmailMessageDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [showCompose, setShowCompose] = useState(false);

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

  const loadMessages = useCallback(() => {
    return apiRequest<EmailListResponse>("/api/v1/email-account/messages")
      .then((data) => {
        setMessages(data.items ?? []);
        setInboxError(null);
      })
      .catch((err) => setInboxError(err instanceof Error ? err.message : "Failed to load inbox."));
  }, []);

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
    apiRequest<EmailMessageDetail>(`/api/v1/email-account/messages/${encodeURIComponent(selectedUid)}`)
      .then(setSelectedMessage)
      .catch((err) => setInboxError(err instanceof Error ? err.message : "Failed to load message."))
      .finally(() => setLoadingDetail(false));
  }, [selectedUid]);

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

  if (loadingAccount) {
    return <div className="p-6 text-sm text-[#888]">Loading…</div>;
  }

  if (!isConnected) {
    return (
      <div className="mx-auto max-w-2xl space-y-6 p-6">
        <div>
          <h1 className="text-2xl font-semibold text-white">Email</h1>
          <p className="mt-1 text-sm text-[#888]">Connect your own work mailbox to read and send email from here.</p>
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

  return (
    <div className="flex h-[calc(100vh-6.5rem)] gap-4 p-6">
      <div className="flex w-80 shrink-0 flex-col overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33]">
        <div className="flex items-center justify-between border-b border-outline-variant px-4 py-3">
          <h2 className="text-sm font-semibold text-white">Inbox</h2>
          <button type="button" onClick={() => setShowCompose(true)}
            className="rounded-md bg-brand px-3 py-1.5 text-xs font-semibold text-white">
            Compose
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {loadingMessages && messages.length === 0 && (
            <p className="p-4 text-sm text-slate-400">Loading…</p>
          )}
          {!loadingMessages && messages.length === 0 && !inboxError && (
            <p className="p-4 text-sm text-slate-400">No messages.</p>
          )}
          {messages.map((m) => (
            <button
              key={m.uid}
              type="button"
              onClick={() => setSelectedUid(m.uid)}
              className={`block w-full border-b border-outline-variant/50 px-4 py-3 text-left hover:bg-white/5 ${
                selectedUid === m.uid ? "bg-white/10" : ""
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <p className={`truncate text-sm ${m.is_read ? "text-slate-300" : "font-semibold text-white"}`}>
                  {m.from_address}
                </p>
                <span className="shrink-0 text-[11px] text-slate-500">{formatDate(m.date)}</span>
              </div>
              <p className={`mt-0.5 truncate text-xs ${m.is_read ? "text-slate-500" : "text-slate-300"}`}>
                {m.subject || "(no subject)"}
              </p>
            </button>
          ))}
        </div>
        <div className="border-t border-outline-variant px-4 py-3">
          <button type="button" onClick={handleDisconnect} className="text-xs text-rose-400 hover:text-rose-300">
            Disconnect mailbox
          </button>
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

      {showCompose && <ComposeModal onSend={handleSend} onClose={() => setShowCompose(false)} />}
    </div>
  );
}
