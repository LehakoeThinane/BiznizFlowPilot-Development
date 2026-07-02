interface MetricsCardProps {
  label: string;
  value: number | string;
}

export function MetricsCard({ label, value }: MetricsCardProps) {
  return (
    <article className="erp-panel p-4">
      <p className="text-[11px] uppercase tracking-wider text-on-surface-variant">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-surface-bright">{value}</p>
    </article>
  );
}
