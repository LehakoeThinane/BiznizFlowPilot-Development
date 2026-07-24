import type { ReactNode } from "react";

/** Short in-app "how to" guides, one per onboarding checklist step. Hand-
 * authored as JSX rather than parsed markdown - these are logged-in,
 * already-known users, so there's no lead-capture gate here (unlike the
 * marketing site's downloadable guides), and no markdown/PDF library is
 * needed just to render a page of copy. */

export interface OnboardingGuide {
  title: string;
  content: ReactNode;
}

export const ONBOARDING_GUIDES: Record<string, OnboardingGuide> = {
  "invite-team": {
    title: "Invite your team",
    content: (
      <>
        <p>Go to Organization and click Invite. Enter a teammate&apos;s email and pick their role.</p>
        <p>They&apos;ll get an email with a link to set their own password - you never see or set it for them.</p>
        <p>Everyone you invite has to use an email on your business&apos;s own domain, not a personal address.</p>
      </>
    ),
  },
  "add-first-lead": {
    title: "Add your first lead",
    content: (
      <>
        <p>Go to Leads and click Add Lead. A lead can be a person or a company you&apos;re trying to sell to.</p>
        <p>Move it through your pipeline as it progresses - new, qualified, won, or lost.</p>
      </>
    ),
  },
  "set-up-inventory": {
    title: "Set up inventory",
    content: (
      <>
        <p>Go to Inventory and add your first product, with a SKU and a price.</p>
        <p>Once you&apos;re tracking stock, you&apos;ll get low-stock alerts automatically.</p>
      </>
    ),
  },
  "explore-finance": {
    title: "Explore finance",
    content: (
      <>
        <p>Go to Finance to log an expense or raise an invoice.</p>
        <p>Your profit-and-loss numbers update automatically as you go, no separate spreadsheet required.</p>
      </>
    ),
  },
  "set-up-automation": {
    title: "Set up automation",
    content: (
      <>
        <p>Go to Runs (Workflows) and create your first automation - for example, notify a manager whenever a task is created.</p>
        <p>Automations run quietly in the background so your team isn&apos;t the one manually connecting every step.</p>
      </>
    ),
  },
  "try-ai-copilot": {
    title: "Try the AI copilot",
    content: (
      <>
        <p>Open Chat and ask the copilot to do something concrete - &ldquo;create a task for me&rdquo; or &ldquo;update this lead&apos;s status.&rdquo;</p>
        <p>It always asks for confirmation before changing anything, so nothing happens without your sign-off.</p>
      </>
    ),
  },
  "set-up-hr": {
    title: "Set up HR",
    content: (
      <>
        <p>Go to Employees and add your first employee record - name, position, and start date.</p>
        <p>From there you can track leave requests and run payroll for them.</p>
      </>
    ),
  },
  "add-subsidiary": {
    title: "Add a subsidiary",
    content: (
      <>
        <p>Go to Organization to add a second business under the same account.</p>
        <p>Each subsidiary keeps its own data, but an IT Admin role can manage every subsidiary from one login.</p>
      </>
    ),
  },
};
