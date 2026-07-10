"use client";

export default function CheckoutCancelledPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <section className="w-full max-w-md rounded-xl border border-border bg-surface p-8 text-center shadow-sm">
        <h1 className="text-h1 text-foreground">Checkout cancelled</h1>
        <p className="text-body-base mt-3 text-muted">
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
