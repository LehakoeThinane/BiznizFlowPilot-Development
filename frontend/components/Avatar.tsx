import type { Presence } from "@/types/api";
import { presenceDotClass, presenceLabel } from "@/lib/presence";

function initialsOf(name: string): string {
  return (name || "?")
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0] ?? "")
    .join("")
    .toUpperCase();
}

const SIZE_CLASSES = {
  sm: { circle: "h-8 w-8 text-xs", dot: "h-2.5 w-2.5" },
  md: { circle: "h-9 w-9 text-xs", dot: "h-3 w-3" },
} as const;

interface AvatarProps {
  name: string;
  avatarUrl?: string | null;
  presence?: Presence | null;
  size?: keyof typeof SIZE_CLASSES;
  onClick?: () => void;
}

export function Avatar({ name, avatarUrl, presence, size = "md", onClick }: AvatarProps) {
  const { circle, dot } = SIZE_CLASSES[size];
  return (
    <div
      className={`relative shrink-0 ${onClick ? "cursor-pointer rounded-full transition-opacity hover:opacity-80" : ""}`}
      onClick={(event) => {
        event.stopPropagation();
        onClick?.();
      }}
      onKeyDown={(event) => {
        if (onClick && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          onClick();
        }
      }}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      aria-label={onClick ? `Open ${name}'s profile` : undefined}
    >
      {avatarUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={avatarUrl} alt={name} className={`${circle} rounded-full object-cover`} />
      ) : (
        <div
          className={`flex ${circle} items-center justify-center rounded-full bg-blue-600 font-semibold text-white`}
        >
          {initialsOf(name)}
        </div>
      )}
      {presence && (
        <span
          title={presenceLabel(presence)}
          className={`absolute -bottom-0.5 -right-0.5 ${dot} rounded-full border-2 border-[#0f1c33] ${presenceDotClass(presence)}`}
        />
      )}
    </div>
  );
}
