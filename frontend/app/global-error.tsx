"use client";

interface Props {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ reset }: Props) {
  return (
    <html lang="en">
      <body className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[#0a0a0a] text-center">
        <p className="text-lg font-bold text-white">Application error</p>
        <p className="text-sm text-[#888]">Please refresh the page or try again.</p>
        <button
          type="button"
          onClick={reset}
          className="rounded-lg bg-[#1e40af] px-5 py-2 text-sm font-semibold text-white"
        >
          Reload
        </button>
      </body>
    </html>
  );
}
