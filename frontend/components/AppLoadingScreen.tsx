interface AppLoadingScreenProps {
  label?: string;
}

export function AppLoadingScreen({ label = "Loading…" }: AppLoadingScreenProps) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-[#0a0a0a]">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/logo-icon.png" alt="BiznizFlowPilot" width={77} height={77} className="logo-breathe" />
      <p className="text-sm text-[#777]">{label}</p>
    </div>
  );
}
