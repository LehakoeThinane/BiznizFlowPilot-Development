"use client";

import Link from "next/link";

export default function CheckoutSuccessPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#0a0a0a] px-4">
      <section className="w-full max-w-md rounded-xl border border-[#222] bg-[#141414] p-8 text-center shadow-sm">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-600/20 text-2xl text-emerald-500">
          ✓
        </div>
        <h1 className="text-xl font-semibold text-white">Payment received</h1>
        <p className="mt-3 text-sm text-[#888]">
          We&apos;re setting up your account now. Check your email for an invite link to finish creating your
          owner account — it should arrive within a couple of minutes.
        </p>
        <p className="mt-6 text-sm text-muted">
          Already have the invite?{" "}
          <Link href="/login" className="font-medium text-brand hover:underline">
            Sign in
          </Link>
        </p>
      </section>
    </main>
  );
}
