"use client";

interface Props {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function DashboardError({ error, reset }: Props) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
      <span className="material-symbols-outlined text-rose-400" style={{ fontSize: 48 }}>
        error
      </span>
      <p className="text-h3 text-on-surface">Something went wrong</p>
      <p className="max-w-sm text-body-sm text-muted">
        {error.message || "An unexpected error occurred. Your data has not been affected."}
      </p>
      <button
        type="button"
        onClick={reset}
        className="mt-2 rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-on-primary transition-colors hover:bg-brand-hover"
      >
        Try again
      </button>
    </div>
  );
}
