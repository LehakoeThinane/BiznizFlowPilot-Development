"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { TextStyleKit } from "@tiptap/extension-text-style";
import { Highlight } from "@tiptap/extension-highlight";
import { TextAlign } from "@tiptap/extension-text-align";
import { TableKit } from "@tiptap/extension-table";
import DOMPurify from "dompurify";

import { apiRequest, ApiError } from "@/lib/api";
import { getStoredToken } from "@/lib/auth";
import { Indent } from "@/lib/tiptap-indent";
import type { BusinessDocument, DocumentContentResponse } from "@/types/api";

const AUTOSAVE_IDLE_MS = 3000;

type SaveState = "idle" | "saving" | "saved" | "error";

const FONT_FAMILIES = [
  { label: "Default", value: "" },
  { label: "Arial", value: "Arial, sans-serif" },
  { label: "Georgia", value: "Georgia, serif" },
  { label: "Times New Roman", value: '"Times New Roman", serif' },
  { label: "Courier New", value: '"Courier New", monospace' },
  { label: "Verdana", value: "Verdana, sans-serif" },
  { label: "Trebuchet MS", value: '"Trebuchet MS", sans-serif' },
];

const FONT_SIZES = ["10px", "11px", "12px", "14px", "16px", "18px", "20px", "24px", "28px", "32px", "36px"];

function ToolbarDivider() {
  return <div className="mx-1 h-5 w-px shrink-0 self-stretch bg-outline-variant" />;
}

function ToolbarIconButton({
  onClick,
  active,
  disabled,
  icon,
  label,
}: {
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  icon: string;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition-colors disabled:cursor-not-allowed disabled:opacity-30 ${
        active
          ? "bg-tertiary-fixed-dim text-[#04211d]"
          : "text-on-surface-variant hover:bg-surface-container-high hover:text-white"
      }`}
    >
      <span className="material-symbols-outlined text-[19px]">{icon}</span>
    </button>
  );
}

function ToolbarSelect({
  value,
  onChange,
  options,
  label,
  className = "",
}: {
  value: string;
  onChange: (value: string) => void;
  options: { label: string; value: string }[];
  label: string;
  className?: string;
}) {
  return (
    <select
      aria-label={label}
      title={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`erp-input h-8 shrink-0 px-2 text-xs ${className}`}
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}

function ToolbarTextButton({ onClick, disabled, children }: { onClick: () => void; disabled?: boolean; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="shrink-0 rounded-md px-2 py-1 text-xs font-medium text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-white disabled:cursor-not-allowed disabled:opacity-30"
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
  // Toolbar active/disabled state (isActive, can().*) depends on the
  // editor's current selection, which changes on every click/keystroke
  // without necessarily firing React's own re-render - without this,
  // buttons visually lag a step behind the actual editor state.
  const [, setSelectionTick] = useState(0);

  const editor = useEditor({
    extensions: [
      StarterKit,
      TextStyleKit.configure({ backgroundColor: false, lineHeight: false }),
      Highlight.configure({ multicolor: true }),
      TextAlign.configure({ types: ["paragraph", "heading"] }),
      Indent,
      // renderWrapper: false - the default is actually true in practice
      // (confirmed by inspecting real editor output, not just the
      // extension's declared option default); without this the saved HTML
      // wraps every table in <div class="tableWrapper">, which the backend
      // sanitizer would otherwise need to special-case just for this one
      // generic, semantically-empty wrapper element.
      TableKit.configure({ table: { resizable: false, renderWrapper: false } }),
    ],
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
    onSelectionUpdate: () => setSelectionTick((t) => t + 1),
    onTransaction: () => setSelectionTick((t) => t + 1),
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

  function handleSetLink() {
    if (!editor) return;
    if (editor.isActive("link")) {
      editor.chain().focus().unsetLink().run();
      return;
    }
    const url = window.prompt("Link URL:", "https://");
    if (!url) return;
    editor.chain().focus().setLink({ href: url, target: "_blank", rel: "noopener noreferrer" }).run();
  }

  function handleInsertTable() {
    if (!editor) return;
    const size = window.prompt("Table size (rows x columns):", "3x3");
    if (!size) return;
    const match = size.trim().match(/^(\d+)\s*[xX×]\s*(\d+)$/);
    if (!match) {
      window.alert('Enter a size like "3x3".');
      return;
    }
    const rows = Math.min(20, Math.max(1, parseInt(match[1], 10)));
    const cols = Math.min(12, Math.max(1, parseInt(match[2], 10)));
    editor.chain().focus().insertTable({ rows, cols, withHeaderRow: true }).run();
  }

  function currentParagraphStyle(): string {
    if (!editor) return "paragraph";
    for (const level of [1, 2, 3] as const) {
      if (editor.isActive("heading", { level })) return `h${level}`;
    }
    return "paragraph";
  }

  function handleParagraphStyleChange(value: string) {
    if (!editor) return;
    if (value === "paragraph") {
      editor.chain().focus().setParagraph().run();
    } else {
      const level = Number(value.replace("h", "")) as 1 | 2 | 3;
      editor.chain().focus().toggleHeading({ level }).run();
    }
  }

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

  const inTable = editor?.isActive("table") ?? false;

  return (
    <div className="-m-6 flex min-h-[calc(100vh-3rem)] flex-col">
      <div className="flex items-center justify-between border-b border-outline-variant bg-[#0d1628]/90 px-6 py-3 backdrop-blur">
        <Link href="/documents" className="text-sm text-on-surface-variant hover:text-white">
          &larr; Back to Documents
        </Link>
        <div className="flex items-center gap-4">
          <span className="text-xs text-on-surface-variant">
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
        <div className="border-b border-outline-variant bg-[#0d1628]/60">
          <div className="flex flex-wrap items-center gap-1 px-6 py-2">
            <ToolbarIconButton icon="undo" label="Undo" onClick={() => editor.chain().focus().undo().run()} disabled={!editor.can().undo()} />
            <ToolbarIconButton icon="redo" label="Redo" onClick={() => editor.chain().focus().redo().run()} disabled={!editor.can().redo()} />

            <ToolbarDivider />

            <ToolbarSelect
              label="Paragraph style"
              value={currentParagraphStyle()}
              onChange={handleParagraphStyleChange}
              className="w-32"
              options={[
                { label: "Normal text", value: "paragraph" },
                { label: "Heading 1", value: "h1" },
                { label: "Heading 2", value: "h2" },
                { label: "Heading 3", value: "h3" },
              ]}
            />
            <ToolbarSelect
              label="Font family"
              value={editor.getAttributes("textStyle").fontFamily ?? ""}
              onChange={(v) => (v ? editor.chain().focus().setFontFamily(v).run() : editor.chain().focus().unsetFontFamily().run())}
              className="w-32"
              options={FONT_FAMILIES}
            />
            <ToolbarSelect
              label="Font size"
              value={editor.getAttributes("textStyle").fontSize ?? ""}
              onChange={(v) => (v ? editor.chain().focus().setFontSize(v).run() : editor.chain().focus().unsetFontSize().run())}
              className="w-20"
              options={[{ label: "Size", value: "" }, ...FONT_SIZES.map((s) => ({ label: s.replace("px", ""), value: s }))]}
            />

            <ToolbarDivider />

            <ToolbarIconButton icon="format_bold" label="Bold" active={editor.isActive("bold")} onClick={() => editor.chain().focus().toggleBold().run()} />
            <ToolbarIconButton icon="format_italic" label="Italic" active={editor.isActive("italic")} onClick={() => editor.chain().focus().toggleItalic().run()} />
            <ToolbarIconButton icon="format_underlined" label="Underline" active={editor.isActive("underline")} onClick={() => editor.chain().focus().toggleUnderline().run()} />

            <label
              className="flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-md text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-white"
              title="Text color"
            >
              <span className="material-symbols-outlined text-[19px]">format_color_text</span>
              <input
                type="color"
                aria-label="Text color"
                className="sr-only"
                value={editor.getAttributes("textStyle").color ?? "#ffffff"}
                onChange={(e) => editor.chain().focus().setColor(e.target.value).run()}
              />
            </label>
            <label
              className="flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-md text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-white"
              title="Highlight color"
            >
              <span className="material-symbols-outlined text-[19px]">ink_highlighter</span>
              <input
                type="color"
                aria-label="Highlight color"
                className="sr-only"
                value={editor.getAttributes("highlight").color ?? "#fef08a"}
                onChange={(e) => editor.chain().focus().setHighlight({ color: e.target.value }).run()}
              />
            </label>

            <ToolbarDivider />

            <ToolbarIconButton icon="format_align_left" label="Align left" active={editor.isActive({ textAlign: "left" })} onClick={() => editor.chain().focus().setTextAlign("left").run()} />
            <ToolbarIconButton icon="format_align_center" label="Align center" active={editor.isActive({ textAlign: "center" })} onClick={() => editor.chain().focus().setTextAlign("center").run()} />
            <ToolbarIconButton icon="format_align_right" label="Align right" active={editor.isActive({ textAlign: "right" })} onClick={() => editor.chain().focus().setTextAlign("right").run()} />
            <ToolbarIconButton icon="format_align_justify" label="Justify" active={editor.isActive({ textAlign: "justify" })} onClick={() => editor.chain().focus().setTextAlign("justify").run()} />
            <ToolbarIconButton icon="format_indent_decrease" label="Outdent" onClick={() => editor.chain().focus().outdent().run()} />
            <ToolbarIconButton icon="format_indent_increase" label="Indent" onClick={() => editor.chain().focus().indent().run()} />

            <ToolbarDivider />

            <ToolbarIconButton icon="format_list_bulleted" label="Bullet list" active={editor.isActive("bulletList")} onClick={() => editor.chain().focus().toggleBulletList().run()} />
            <ToolbarIconButton icon="format_list_numbered" label="Numbered list" active={editor.isActive("orderedList")} onClick={() => editor.chain().focus().toggleOrderedList().run()} />
            <ToolbarIconButton icon="format_quote" label="Quote" active={editor.isActive("blockquote")} onClick={() => editor.chain().focus().toggleBlockquote().run()} />
            <ToolbarIconButton icon="link" label="Link" active={editor.isActive("link")} onClick={handleSetLink} />
            <ToolbarIconButton icon="table" label="Insert table" onClick={handleInsertTable} />

            <ToolbarDivider />

            <ToolbarIconButton icon="format_clear" label="Clear formatting" onClick={() => editor.chain().focus().unsetAllMarks().clearNodes().run()} />
          </div>

          {inTable && (
            <div className="flex flex-wrap items-center gap-1 border-t border-outline-variant/60 px-6 py-1.5">
              <span className="mr-1 text-[10px] font-semibold uppercase tracking-wide text-on-surface-variant">Table</span>
              <ToolbarTextButton onClick={() => editor.chain().focus().addRowBefore().run()}>Row above</ToolbarTextButton>
              <ToolbarTextButton onClick={() => editor.chain().focus().addRowAfter().run()}>Row below</ToolbarTextButton>
              <ToolbarTextButton onClick={() => editor.chain().focus().addColumnBefore().run()}>Col left</ToolbarTextButton>
              <ToolbarTextButton onClick={() => editor.chain().focus().addColumnAfter().run()}>Col right</ToolbarTextButton>
              <ToolbarTextButton onClick={() => editor.chain().focus().toggleHeaderRow().run()}>Toggle header row</ToolbarTextButton>
              <ToolbarDivider />
              <ToolbarTextButton onClick={() => editor.chain().focus().deleteRow().run()}>Delete row</ToolbarTextButton>
              <ToolbarTextButton onClick={() => editor.chain().focus().deleteColumn().run()}>Delete column</ToolbarTextButton>
              <ToolbarTextButton onClick={() => editor.chain().focus().deleteTable().run()}>Delete table</ToolbarTextButton>
            </div>
          )}
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
