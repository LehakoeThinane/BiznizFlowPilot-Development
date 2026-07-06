import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-[#0a0a0a] px-4 text-center">
      <div className="mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-600 text-2xl font-bold text-white">
        B
      </div>
      <h1 className="max-w-xl text-4xl font-semibold text-white">
        Run your business operations from one place
      </h1>
      <p className="mt-4 max-w-md text-sm text-[#888]">
        CRM, inventory, invoicing, HR, and workflow automation — for teams who'd rather run the
        business than run the spreadsheets.
      </p>
      <div className="mt-8 flex gap-4">
        <Link
          href="/pricing"
          className="rounded-md bg-brand px-5 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90"
        >
          View pricing
        </Link>
        <Link
          href="/login"
          className="rounded-md border border-[#333] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:border-[#555]"
        >
          Sign in
        </Link>
      </div>
    </main>
  );
}
