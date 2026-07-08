import { redirect } from "next/navigation";

// Pricing/checkout now lives solely on the MM Nexus marketing site - having
// two hand-maintained copies of tier prices/limits drifted out of sync after
// one iteration. This route stays only so existing links/bookmarks to
// /pricing still land somewhere real.
export default function PricingRedirect() {
  redirect("https://mmnexus.co.za/biznizflowpilot#pricing");
}
