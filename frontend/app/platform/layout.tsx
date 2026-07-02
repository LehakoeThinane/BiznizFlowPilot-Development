export const metadata = {
  title: "BiznizFlowPilot — Platform Console",
};

// Deliberately not nested under (dashboard) or (auth) - the platform console
// is a fully separate auth boundary (vendor staff, cross-tenant) and must be
// visually distinct so vendor staff can never mistake it for a tenant view.
export default function PlatformLayout({ children }: { children: React.ReactNode }) {
  return <div className="min-h-screen bg-[#0a0a12]">{children}</div>;
}
