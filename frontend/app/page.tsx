import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="flex min-h-screen flex-col items-center bg-background px-4 text-center">
      <div className="sticky top-0 z-10 -mx-4 flex w-[calc(100%+2rem)] flex-wrap items-center justify-center gap-2 bg-brand px-4 py-2.5 text-sm font-medium text-on-primary">
        <span>🎉 Try BiznizFlowPilot free for 14 days — no credit card required.</span>
        <Link
          href="/signup"
          className="rounded-md bg-on-primary/15 px-3 py-1 text-xs font-semibold transition-colors hover:bg-on-primary/25"
        >
          Start free trial
        </Link>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center">
      <div className="glow-badge mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand text-2xl font-bold text-on-primary">
        B
      </div>
      <p className="text-label-caps text-tertiary-fixed-dim">BiznizFlowPilot</p>
      <h1 className="text-display mt-3 max-w-xl text-balance text-foreground">
        Run your business operations from one place
      </h1>
      <p className="text-body-base mt-4 max-w-md text-muted">
        CRM, inventory, invoicing, HR, and workflow automation — for teams who&apos;d rather run
        the business than run the spreadsheets.
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-4">
        <Link
          href="/signup"
          className="erp-button-primary rounded-lg px-5 py-2.5 text-sm font-semibold transition-opacity hover:opacity-90"
        >
          Start free trial
        </Link>
        <a
          href="https://mmnexus.co.za/biznizflowpilot#pricing"
          className="rounded-lg border border-border px-5 py-2.5 text-sm font-semibold text-foreground transition-colors hover:border-brand/60"
        >
          View pricing
        </a>
        <Link
          href="/login"
          className="rounded-lg border border-border px-5 py-2.5 text-sm font-semibold text-foreground transition-colors hover:border-brand/60"
        >
          Sign in
        </Link>
      </div>
      <Link href="/download" className="mt-6 text-xs text-muted hover:text-foreground hover:underline">
        Already a customer? Download the desktop app →
      </Link>
      </div>
    </main>
  );
}
