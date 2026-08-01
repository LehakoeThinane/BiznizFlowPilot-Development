"""In-app rich-text document editor.

Deliberately reuses the existing upload/checkout/check-in machinery
unmodified (see app/services/document.py, app/services/document_checkout.py)
rather than a parallel content model:

- compose() creates a normal Document via DocumentService.upload() (an
  empty text/html "file"), then locks it to its creator via the existing
  checkout service - same row, same version/checkout columns as any
  uploaded file.
- save_draft() is the autosave target: it writes to a short-lived,
  deterministic R2 key (not the document's own storage_key), so frequent
  autosaves never touch Document.version or create DocumentVersion rows.
- finish() reads that draft back and folds it into a real version by
  calling the existing, unmodified DocumentCheckoutService.check_in() -
  the one point per editing session where history actually advances.
"""

from __future__ import annotations

from uuid import UUID

import bleach
from bleach.css_sanitizer import CSSSanitizer

from app.integrations import object_storage
from app.integrations.object_storage import ObjectStorageError
from app.models.document import Document
from app.repositories.document import DocumentRepository
from app.schemas.auth import CurrentUser
from app.services.document import DocumentService
from app.services.document_checkout import DocumentCheckoutService

_HEADING_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6"]
# table, colgroup, col, tbody, tr, td, th - Tiptap's Table extension always
# renders a full table/colgroup/col structure (one <col style="..."> per
# column, unconditionally, not just when a column has been manually
# resized), so all of these are load-bearing even for a plain inserted
# table - confirmed by reading the extension's actual renderHTML output
# rather than assuming.
_TABLE_TAGS = ["table", "colgroup", "col", "tbody", "tr", "td", "th"]
_ALLOWED_TAGS = [
    "p", "br", "strong", "em", "s", "u",
    *_HEADING_TAGS,
    "ul", "ol", "li", "blockquote", "code", "pre", "a", "hr",
    # span (text color/font) and mark (highlight) - both TipTap marks render
    # via an inline style attribute rather than a dedicated element/attribute
    # pair, hence the CSS allowlist below rather than a plain attribute one.
    "span", "mark",
    *_TABLE_TAGS,
]
_ALLOWED_ATTRS = {
    "a": ["href", "target", "rel"],
    "span": ["style"],
    "mark": ["style", "data-color"],
    # Paragraph/heading alignment (TextAlign) and indent level (our own
    # Indent extension) both render as `style` on the block element itself.
    **{tag: ["style"] for tag in ("p", *_HEADING_TAGS)},
    "table": ["style"],
    "col": ["style"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
}
# Deliberately narrow: only cosmetic text/table-layout properties Tiptap's
# toolbar actually emits, never anything that could reposition, hide, or
# layer content (no position, display, z-index, etc.). width/min-width are
# here only because Tiptap's table extension always sets one of them on
# <table>/<col> even with column resizing disabled in the editor UI - on a
# <p>/<span> they're cosmetic at worst (can't achieve overlay/clickjacking
# without `position` too, which is deliberately not on this list).
_CSS_SANITIZER = CSSSanitizer(
    allowed_css_properties=[
        "color", "background-color", "text-align", "margin-left",
        "font-family", "font-size", "width", "min-width",
    ],
)


def _sanitize(content_html: str) -> str:
    return bleach.clean(
        content_html, tags=_ALLOWED_TAGS, attributes=_ALLOWED_ATTRS, css_sanitizer=_CSS_SANITIZER, strip=True,
    )


def sanitize_document_html(content_html: str) -> str:
    """Public entry point for callers outside this module (e.g. emailing the
    document's live, possibly-unsaved editor content) that need the exact
    same allowlist as compose/save-draft/finish."""
    return _sanitize(content_html)


def _draft_key(document_id: UUID) -> str:
    return f"drafts/{document_id}.html"


class DocumentEditorService:
    def __init__(self, db):
        self.db = db
        self.repo = DocumentRepository(db)
        self.document_service = DocumentService(db)
        self.checkout_service = DocumentCheckoutService(db)

    def compose(
        self, business_id: UUID, current_user: CurrentUser, entity_type: str, entity_id: UUID, title: str
    ) -> Document:
        """Create a new, empty in-app document and immediately check it out
        to its creator - the editor opens straight into an editable state."""
        filename = f"{title.strip() or 'Untitled Document'}.html"
        doc = self.document_service.upload(
            business_id=business_id,
            current_user=current_user,
            entity_type=entity_type,
            entity_id=entity_id,
            filename=filename,
            content=b"<p></p>",
            content_type="text/html",
        )
        checked_out = self.checkout_service.check_out(business_id, current_user, doc.id)
        return checked_out if checked_out is not None else doc

    def save_draft(self, business_id: UUID, current_user: CurrentUser, document_id: UUID, content_html: str) -> None:
        """Autosave target - overwrites a scratch buffer, never the
        document's own storage_key/version. Restricted to the checkout
        holder specifically (unlike check_in, which also allows an owner/
        manager to override): there's no reasonable case for saving draft
        keystrokes on someone else's behalf."""
        doc = self.repo.get(business_id=business_id, entity_id=document_id)
        if not doc:
            raise LookupError("Document not found")
        if doc.checked_out_by is None or str(doc.checked_out_by) != str(current_user.user_id):
            raise PermissionError("You need to have this document checked out to save changes")

        object_storage.upload_at_key(_draft_key(document_id), _sanitize(content_html).encode("utf-8"), "text/html")

    def finish(self, business_id: UUID, current_user: CurrentUser, document_id: UUID) -> Document | None:
        """End an editing session: fold the autosaved draft (if any) into a
        real version via the existing check_in(), then clear the draft
        buffer. If nothing was ever autosaved (e.g. Done clicked immediately
        after composing), just releases the checkout with no new version."""
        doc = self.repo.get(business_id=business_id, entity_id=document_id)
        if not doc:
            return None

        try:
            draft_bytes = object_storage.get(_draft_key(document_id))
        except ObjectStorageError:
            return self.checkout_service.cancel_checkout(business_id, current_user, document_id)

        updated = self.checkout_service.check_in(
            business_id=business_id,
            current_user=current_user,
            document_id=document_id,
            filename=doc.filename,
            content=_sanitize(draft_bytes.decode("utf-8")).encode("utf-8"),
            content_type="text/html",
        )
        object_storage.delete(_draft_key(document_id))
        return updated
