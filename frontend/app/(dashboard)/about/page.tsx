function MarkLogo() {
  // eslint-disable-next-line @next/next/no-img-element
  return <img src="/logo-icon.png" alt="" width={20} height={20} />;
}

const STACK_LAYERS = [
  { label: "FRONTEND", name: "Next.js 16", description: "App Router, Turbopack, TypeScript throughout" },
  { label: "BACKEND", name: "FastAPI", description: "Python REST API with async request handling" },
  { label: "DATABASE", name: "PostgreSQL", description: "Every table scoped to a tenant, isolation enforced at the data layer" },
  { label: "AUTOMATION", name: "Celery + Redis", description: "Background jobs and the event-driven workflow engine" },
  { label: "DEPLOY", name: "Docker + GitHub Actions", description: "Images built in CI, pulled straight to production" },
];

const FEATURES = [
  {
    dot: "bg-brand",
    label: "MULTI-TENANT",
    heading: "Role-based access",
    description: "Owner, manager, staff, and IT-admin roles, each with a different view of the same platform.",
  },
  {
    dot: "bg-tertiary-fixed-dim",
    label: "AUTOMATED",
    heading: "Workflow engine",
    description: "Business events trigger emails, tasks, and webhooks automatically — no manual follow-up.",
  },
  {
    dot: "bg-orange-400",
    label: "MONITORED",
    heading: "Real-time error tracking",
    description: "Sentry and uptime monitoring watch every request, live, in production.",
  },
  {
    dot: "bg-emerald-400",
    label: "SECURE",
    heading: "Tenant isolation",
    description: "Every database query is scoped to your business — enforced in the code, not just policy.",
  },
];

export default function AboutPage() {
  return (
    <div className="-m-6 min-h-[calc(100vh-3rem)] px-8 py-10">
      <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold tracking-[0.2em] text-tertiary-fixed-dim">
        <MarkLogo />
        BIZNIZFLOWPILOT &middot; ARCHITECTURE
      </div>

      <h1 className="text-[42px] font-extrabold leading-tight tracking-tight">
        <span className="bg-gradient-to-r from-white via-primary-fixed-dim to-tertiary-fixed-dim bg-clip-text text-transparent">
          BiznizFlowPilot
        </span>
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-on-surface-variant">
        A multi-tenant ERP built on a modern, production-grade stack &mdash; real automation, real
        tenant isolation, real reliability.
      </p>
      <div className="mt-4 h-0.5 w-16 rounded-full bg-gradient-to-r from-brand to-tertiary-fixed-dim" />

      <div className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-[1.1fr_1fr]">
        {/* Stack layers */}
        <div className="space-y-3">
          {STACK_LAYERS.map((layer) => (
            <div
              key={layer.label}
              className="erp-panel flex items-center justify-between gap-4 px-5 py-4"
            >
              <div>
                <div className="flex items-center gap-2 text-[10px] font-semibold tracking-[0.15em] text-tertiary-fixed-dim">
                  <span className="h-1.5 w-1.5 rounded-full bg-tertiary-fixed-dim" />
                  {layer.label}
                </div>
                <p className="mt-1 text-lg font-semibold text-surface-bright">{layer.name}</p>
              </div>
              <p className="max-w-[55%] text-right text-xs leading-relaxed text-on-surface-variant">
                {layer.description}
              </p>
            </div>
          ))}
        </div>

        {/* Feature grid */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {FEATURES.map((feature) => (
            <div key={feature.label} className="erp-panel p-5">
              <div className="flex items-center gap-2 text-[10px] font-semibold tracking-[0.15em] text-on-surface-variant">
                <span className={`h-1.5 w-1.5 rounded-full ${feature.dot}`} />
                {feature.label}
              </div>
              <p className="mt-3 text-base font-semibold text-surface-bright">{feature.heading}</p>
              <div className="mt-2 h-px w-8 bg-outline-variant" />
              <p className="mt-3 text-xs leading-relaxed text-on-surface-variant">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-10 flex items-center justify-between border-t border-outline-variant pt-6">
        <div>
          <p className="bg-gradient-to-r from-brand to-tertiary-fixed-dim bg-clip-text text-lg font-bold text-transparent">
            app.mmnexus.co.za
          </p>
          <p className="mt-0.5 text-xs text-on-surface-variant">Live production platform &middot; BiznizFlowPilot</p>
        </div>
        <MarkLogo />
      </div>
    </div>
  );
}
