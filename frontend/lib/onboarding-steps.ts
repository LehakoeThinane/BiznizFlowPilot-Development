/** Onboarding checklist copy, keyed by the same step keys the backend
 * returns from GET /api/v1/onboarding (see app/core/onboarding.py's
 * STEP_DEFINITIONS). The backend decides which steps exist and whether
 * each is done; this file only owns display copy. */

export interface OnboardingStepInfo {
  title: string;
  description: string;
  guideSlug: string;
  href: string;
}

export const ONBOARDING_STEPS: Record<string, OnboardingStepInfo> = {
  invite_team: {
    title: "Invite your team",
    description: "Bring your teammates in so work isn't stuck with just you.",
    guideSlug: "invite-team",
    href: "/organization",
  },
  add_first_lead: {
    title: "Add your first lead",
    description: "Log a prospect or customer to start your sales pipeline.",
    guideSlug: "add-first-lead",
    href: "/leads",
  },
  set_up_inventory: {
    title: "Set up inventory",
    description: "Add a product so you can track stock and orders.",
    guideSlug: "set-up-inventory",
    href: "/inventory",
  },
  explore_finance: {
    title: "Explore finance",
    description: "Log an expense or invoice to see your numbers in one place.",
    guideSlug: "explore-finance",
    href: "/finance",
  },
  set_up_automation: {
    title: "Set up automation",
    description: "Create a workflow so routine handoffs happen without you.",
    guideSlug: "set-up-automation",
    href: "/runs",
  },
  try_ai_copilot: {
    title: "Try the AI copilot",
    description: "Ask it to create a task or update a lead right from chat.",
    guideSlug: "try-ai-copilot",
    href: "/chat",
  },
  set_up_hr: {
    title: "Set up HR",
    description: "Add your first employee to start managing leave and payroll.",
    guideSlug: "set-up-hr",
    href: "/employees",
  },
  add_subsidiary: {
    title: "Add a subsidiary",
    description: "Bring a second business into the same organization account.",
    guideSlug: "add-subsidiary",
    href: "/organization",
  },
};
