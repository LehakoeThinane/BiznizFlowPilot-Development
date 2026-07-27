import type { Presence, PresenceStatus } from "@/types/api";

export interface PresencePreset {
  value: Exclude<PresenceStatus, "custom" | "offline">;
  label: string;
  dot: string;
}

// Single source of truth for preset metadata, shared by the avatar dot and
// the status picker so they can't silently drift apart.
export const PRESENCE_PRESETS: PresencePreset[] = [
  { value: "online", label: "Online", dot: "bg-emerald-500" },
  { value: "away", label: "Away", dot: "bg-amber-400" },
  { value: "busy", label: "Busy", dot: "bg-rose-500" },
  { value: "in_meeting", label: "In a meeting", dot: "bg-violet-500" },
];

const CUSTOM_DOT = "bg-sky-500";

export function presenceDotClass(presence: Presence | null | undefined): string {
  if (!presence) return "";
  if (presence.status === "offline") return "bg-transparent ring-2 ring-inset ring-[#666]";
  if (presence.status === "custom") return CUSTOM_DOT;
  return PRESENCE_PRESETS.find((p) => p.value === presence.status)?.dot ?? "bg-[#666]";
}

export function presenceLabel(presence: Presence | null | undefined): string {
  if (!presence) return "";
  if (presence.status === "offline") return "Offline";
  if (presence.status === "custom") return presence.status_text || "Custom status";
  return PRESENCE_PRESETS.find((p) => p.value === presence.status)?.label ?? presence.status;
}
