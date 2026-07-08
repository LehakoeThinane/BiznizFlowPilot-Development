"use client";

export default function CheckoutCancelledPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#0a0a0a] px-4">
      <section className="w-full max-w-md rounded-xl border border-[#222] bg-[#141414] p-8 text-center shadow-sm">
        <h1 className="text-xl font-semibold text-white">Checkout cancelled</h1>
        <p className="mt-3 text-sm text-[#888]">
          No payment was made and no account was created. You can pick a plan again whenever you&apos;re ready.
        </p>
        <p className="mt-6 text-sm text-muted">
          <a href="https://mmnexus.co.za/biznizflowpilot#pricing" className="font-medium text-brand hover:underline">
            Back to pricing
          </a>
        </p>
      </section>
    </main>
  );
}
