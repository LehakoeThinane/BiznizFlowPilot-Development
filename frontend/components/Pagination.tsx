interface Props {
  page: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPrev: () => void;
  onNext: () => void;
}

export function Pagination({ page, totalPages, totalItems, pageSize, onPrev, onNext }: Props) {
  const from = Math.min((page - 1) * pageSize + 1, totalItems);
  const to   = Math.min(page * pageSize, totalItems);

  if (totalItems === 0) return null;

  return (
    <div className="flex items-center justify-between border-t border-outline-variant/80 px-5 py-3">
      <p className="text-xs text-on-surface-variant">
        Showing <span className="font-medium text-on-surface">{from}–{to}</span> of{" "}
        <span className="font-medium text-on-surface">{totalItems}</span>
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onPrev}
          disabled={page <= 1}
          className="rounded-lg border border-outline-variant bg-[#0c172b] px-3 py-1 text-xs text-on-surface-variant transition-colors hover:bg-surface-container-high disabled:cursor-not-allowed disabled:opacity-40"
        >
          Previous
        </button>
        <span className="rounded-md border border-outline-variant/80 bg-[#0c172b] px-2 py-1 text-xs text-on-surface-variant">
          {page} / {totalPages}
        </span>
        <button
          type="button"
          onClick={onNext}
          disabled={page >= totalPages}
          className="rounded-lg border border-outline-variant bg-[#0c172b] px-3 py-1 text-xs text-on-surface-variant transition-colors hover:bg-surface-container-high disabled:cursor-not-allowed disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </div>
  );
}
