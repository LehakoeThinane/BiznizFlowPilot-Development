"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import DOMPurify from "dompurify";

import { apiRequest, ApiError } from "@/lib/api";
import { getStoredToken } from "@/lib/auth";
import type { BusinessDocument, DocumentContentResponse } from "@/types/api";

const AUTOSAVE_IDLE_MS = 3000;

type SaveState = "idle" | "saving" | "saved" | "error";

function ToolbarButton({
  onClick,
  active,
  children,
  label,
}: {
  onClick: () => void;
  active?: boolean;
  children: React.ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      className={`rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors ${
        active ? "bg-tertiary-fixed-dim text-black" : "text-[#ccc] hover:bg-white/10"
      }`}
    >
      {children}
    </button>
  );
}

export default function DocumentEditPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: documentId } = use(params);
  const router = useRouter();
  const token = getStoredToken();

  const [doc, setDoc] = useState<BusinessDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [lockError, setLockError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [finishing, setFinishing] = useState(false);
  const autosaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const editor = useEditor({
    extensions: [StarterKit],
    content: "",
    immediatelyRender: false,
    editorProps: {
      attributes: {
        class: "prose-doc min-h-[60vh] focus:outline-none",
      },
    },
    onUpdate: () => {
      if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
      autosaveTimer.current = setTimeout(() => void saveDraft(), AUTOSAVE_IDLE_MS);
    },
  });

  const saveDraft = useCallback(async () => {
    if (!editor) return;
    setSaveState("saving");
    try {
      const html = DOMPurify.sanitize(editor.getHTML());
      await apiRequest<void>(`/api/v1/documents/${documentId}/draft`, {
        method: "PATCH",
        authToken: token ?? undefined,
        body: { content_html: html },
      });
      setSaveState("saved");
    } catch {
      setSaveState("error");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor, documentId]);

  useEffect(() => {
    let cancelled = false;

    async function open() {
      setLoading(true);
      setLockError(null);
      let checkedOutSuccessfully = false;
      try {
        const checkedOut = await apiRequest<BusinessDocument>(`/api/v1/documents/${documentId}/checkout`, {
          method: "POST",
          authToken: token ?? undefined,
        });
        if (cancelled) return;
        checkedOutSuccessfully = true;
        setDoc(checkedOut);

        const { content: html } = await apiRequest<DocumentContentResponse>(
          `/api/v1/documents/${documentId}/content`,
          { authToken: token ?? undefined },
        );
        if (cancelled) return;
        editor?.commands.setContent(DOMPurify.sanitize(html));
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 409) {
          setLockError("Someone else is already editing this document.");
        } else {
          setLockError(e instanceof Error ? e.message : "Couldn't open this document");
        }
        // Content failed to load after the checkout lock was already
        // acquired - release it, or the document is stuck "checked out"
        // with no way for anyone to retry.
        if (checkedOutSuccessfully) {
          apiRequest(`/api/v1/documents/${documentId}/checkout/cancel`, {
            method: "POST",
            authToken: token ?? undefined,
          }).catch(() => {});
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    if (editor) void open();
    return () => {
      cancelled = true;
    };
  }, [editor, documentId, token]);

  async function handleDone() {
    setFinishing(true);
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    try {
      await saveDraft();
      await apiRequest<BusinessDocument>(`/api/v1/documents/${documentId}/finish`, {
        method: "POST",
        authToken: token ?? undefined,
      });
      router.push("/documents");
    } catch (e) {
      setLockError(e instanceof Error ? e.message : "Couldn't save this document");
      setFinishing(false);
    }
  }

  if (lockError) {
    return (
      <div className="mx-auto max-w-2xl py-16 text-center">
        <p className="text-sm text-red-400">{lockError}</p>
        <Link href="/documents" className="mt-4 inline-block text-sm text-[#8ab4f8] hover:underline">
          &larr; Back to Documents
        </Link>
      </div>
    );
  }

  return (
    <div className="-m-6 flex min-h-[calc(100vh-3rem)] flex-col">
      <div className="flex items-center justify-between border-b border-white/10 px-6 py-3">
        <Link href="/documents" className="text-sm text-muted hover:text-white">
          &larr; Back to Documents
        </Link>
        <div className="flex items-center gap-4">
          <span className="text-xs text-muted">
            {saveState === "saving" && "Saving…"}
            {saveState === "saved" && "Saved"}
            {saveState === "error" && "Couldn't save - retrying…"}
          </span>
          <button
            type="button"
            onClick={() => void handleDone()}
            disabled={finishing || loading}
            className="erp-button-primary px-4 py-2 text-sm font-semibold disabled:opacity-40"
          >
            {finishing ? "Finishing…" : "Done"}
          </button>
        </div>
      </div>

      {editor && (
        <div className="flex items-center gap-1 border-b border-white/10 px-6 py-2">
          <ToolbarButton label="Bold" active={editor.isActive("bold")} onClick={() => editor.chain().focus().toggleBold().run()}>
            B
          </ToolbarButton>
          <ToolbarButton label="Italic" active={editor.isActive("italic")} onClick={() => editor.chain().focus().toggleItalic().run()}>
            I
          </ToolbarButton>
          <ToolbarButton label="Heading" active={editor.isActive("heading", { level: 2 })} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}>
            H2
          </ToolbarButton>
          <ToolbarButton label="Bullet list" active={editor.isActive("bulletList")} onClick={() => editor.chain().focus().toggleBulletList().run()}>
            • List
          </ToolbarButton>
          <ToolbarButton label="Numbered list" active={editor.isActive("orderedList")} onClick={() => editor.chain().focus().toggleOrderedList().run()}>
            1. List
          </ToolbarButton>
          <ToolbarButton label="Quote" active={editor.isActive("blockquote")} onClick={() => editor.chain().focus().toggleBlockquote().run()}>
            &ldquo;&rdquo;
          </ToolbarButton>
        </div>
      )}

      <div className="mx-auto w-full max-w-3xl flex-1 px-6 py-8">
        {loading ? (
          <p className="text-sm text-muted">Loading…</p>
        ) : (
          <>
            <h1 className="mb-4 text-lg font-semibold text-white">{doc?.filename.replace(/\.html$/, "")}</h1>
            <EditorContent editor={editor} />
          </>
        )}
      </div>
    </div>
  );
}
