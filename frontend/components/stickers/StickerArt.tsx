import type { ReactElement, SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

// Shared "die-cut" look: bold flat color, white outline, soft drop shadow -
// distinct from a plain emoji glyph, meant to read as an actual sticker.
const BASE: IconProps = {
  viewBox: "0 0 100 100",
  xmlns: "http://www.w3.org/2000/svg",
};

const OUTLINE = { stroke: "#fff", strokeWidth: 4, strokeLinejoin: "round" as const, strokeLinecap: "round" as const };

function Shadow({ id }: { id: string }) {
  return (
    <defs>
      <filter id={id} x="-20%" y="-20%" width="140%" height="140%">
        <feDropShadow dx="0" dy="2" stdDeviation="2" floodColor="#000" floodOpacity="0.25" />
      </filter>
    </defs>
  );
}

function Heart(props: IconProps) {
  return (
    <svg {...BASE} {...props}>
      <Shadow id="s-heart" />
      <path
        filter="url(#s-heart)"
        d="M50 90 C22 68 6 47 6 29 C6 13 18 3 32 3 C42 3 48 9 50 16 C52 9 58 3 68 3 C82 3 94 13 94 29 C94 47 78 68 50 90 Z"
        fill="#FF4B6E" {...OUTLINE}
      />
      <path d="M50 78 C30 60 18 44 18 30" fill="none" stroke="#FF8FA6" strokeWidth={5} strokeLinecap="round" />
    </svg>
  );
}

function Fire(props: IconProps) {
  return (
    <svg {...BASE} {...props}>
      <Shadow id="s-fire" />
      <path
        filter="url(#s-fire)"
        d="M50 4 C33 22 24 34 24 53 C24 74 36 92 50 92 C64 92 76 74 76 53 C76 44 71 40 68 44 C69 28 58 14 50 4 Z"
        fill="#FF7A1A" {...OUTLINE}
      />
      <path
        d="M50 34 C42 46 38 54 38 64 C38 75 44 83 50 83 C56 83 62 75 62 64 C62 59 59 57 57 59 C57 49 55 41 50 34 Z"
        fill="#FFD23F"
      />
    </svg>
  );
}

function Star(props: IconProps) {
  return (
    <svg {...BASE} {...props}>
      <Shadow id="s-star" />
      <polygon
        filter="url(#s-star)"
        points="50,5 60.6,35.4 92.8,36.1 67.1,55.6 76.5,86.4 50,68 23.6,86.4 32.9,55.6 7.2,36.1 39.4,35.4"
        fill="#FFC94A" {...OUTLINE}
      />
    </svg>
  );
}

function PartyPopper(props: IconProps) {
  return (
    <svg {...BASE} {...props}>
      <Shadow id="s-party" />
      <path filter="url(#s-party)" d="M14 88 L52 18 L74 38 Z" fill="#FF7A1A" {...OUTLINE} />
      <circle cx="72" cy="18" r="4" fill="#FFC94A" />
      <circle cx="88" cy="30" r="3.5" fill="#4CC9F0" />
      <circle cx="64" cy="8" r="3" fill="#FF4B6E" />
      <rect x="82" y="12" width="7" height="7" rx="1.5" fill="#7CDA5B" transform="rotate(20 85 15)" />
      <rect x="90" y="45" width="6" height="6" rx="1.5" fill="#FF4B6E" transform="rotate(-15 93 48)" />
      <circle cx="60" cy="26" r="2.5" fill="#fff" />
    </svg>
  );
}

function Balloons(props: IconProps) {
  return (
    <svg {...BASE} {...props}>
      <Shadow id="s-balloons" />
      <path d="M35 92 C35 92 44 70 44 55" fill="none" stroke="#C7A5E0" strokeWidth={3} />
      <path d="M56 94 C56 94 60 72 58 58" fill="none" stroke="#F7A6BE" strokeWidth={3} />
      <path d="M74 88 C74 88 76 68 72 55" fill="none" stroke="#9AD0E8" strokeWidth={3} />
      <ellipse filter="url(#s-balloons)" cx="36" cy="38" rx="17" ry="21" fill="#FF4B6E" {...OUTLINE} />
      <Shadow id="s-balloons2" />
      <ellipse filter="url(#s-balloons2)" cx="62" cy="26" rx="19" ry="23" fill="#4CC9F0" {...OUTLINE} />
      <Shadow id="s-balloons3" />
      <ellipse filter="url(#s-balloons3)" cx="78" cy="46" rx="13" ry="16" fill="#FFC94A" {...OUTLINE} />
      <ellipse cx="31" cy="30" rx="4" ry="6" fill="#fff" opacity="0.5" />
      <ellipse cx="56" cy="17" rx="4" ry="6" fill="#fff" opacity="0.5" />
    </svg>
  );
}

function Trophy(props: IconProps) {
  return (
    <svg {...BASE} {...props}>
      <Shadow id="s-trophy" />
      <path d="M22 20 C14 20 14 40 26 42" fill="none" stroke="#FFC94A" strokeWidth={6} strokeLinecap="round" />
      <path d="M78 20 C86 20 86 40 74 42" fill="none" stroke="#FFC94A" strokeWidth={6} strokeLinecap="round" />
      <path
        filter="url(#s-trophy)"
        d="M28 14 H72 V34 C72 50 62 58 50 58 C38 58 28 50 28 34 Z"
        fill="#FFC94A" {...OUTLINE}
      />
      <rect x="44" y="58" width="12" height="16" fill="#FFC94A" stroke="#fff" strokeWidth={3} />
      <path d="M32 80 H68 L74 92 H26 Z" fill="#E8A93A" stroke="#fff" strokeWidth={4} strokeLinejoin="round" />
      <circle cx="50" cy="34" r="8" fill="#FFE9A8" />
    </svg>
  );
}

function CheckBadge(props: IconProps) {
  return (
    <svg {...BASE} {...props}>
      <Shadow id="s-check" />
      <circle filter="url(#s-check)" cx="50" cy="50" r="44" fill="#3DBE64" {...OUTLINE} />
      <polyline points="30,52 44,66 72,34" fill="none" stroke="#fff" strokeWidth={9} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Crown(props: IconProps) {
  return (
    <svg {...BASE} {...props}>
      <Shadow id="s-crown" />
      <path
        filter="url(#s-crown)"
        d="M10 70 L18 28 L35 48 L50 15 L65 48 L82 28 L90 70 Z"
        fill="#FFC94A" {...OUTLINE}
      />
      <rect x="10" y="70" width="80" height="14" rx="3" fill="#E8A93A" stroke="#fff" strokeWidth={4} />
      <circle cx="18" cy="28" r="5" fill="#FF4B6E" />
      <circle cx="50" cy="17" r="6" fill="#4CC9F0" />
      <circle cx="82" cy="28" r="5" fill="#FF4B6E" />
    </svg>
  );
}

function Rocket(props: IconProps) {
  return (
    <svg {...BASE} {...props}>
      <Shadow id="s-rocket" />
      <path filter="url(#s-rocket)" d="M50 4 C64 20 68 42 62 66 H38 C32 42 36 20 50 4 Z" fill="#F4F6FA" {...OUTLINE} />
      <path d="M38 55 L18 82 L38 74 Z" fill="#4CC9F0" stroke="#fff" strokeWidth={3.5} strokeLinejoin="round" />
      <path d="M62 55 L82 82 L62 74 Z" fill="#4CC9F0" stroke="#fff" strokeWidth={3.5} strokeLinejoin="round" />
      <circle cx="50" cy="34" r="9" fill="#4CC9F0" stroke="#fff" strokeWidth={3} />
      <path d="M41 66 C41 78 45 88 50 94 C55 88 59 78 59 66 Z" fill="#FF7A1A" stroke="#fff" strokeWidth={3.5} strokeLinejoin="round" />
      <path d="M46 66 C46 74 48 81 50 86 C52 81 54 74 54 66 Z" fill="#FFD23F" />
    </svg>
  );
}

function CoffeeCup(props: IconProps) {
  return (
    <svg {...BASE} {...props}>
      <Shadow id="s-coffee" />
      <path d="M8 22 C4 12 12 6 16 14" fill="none" stroke="#D9C7B8" strokeWidth={3.5} strokeLinecap="round" />
      <path d="M20 16 C16 6 24 0 28 8" fill="none" stroke="#D9C7B8" strokeWidth={3.5} strokeLinecap="round" />
      <path d="M74 42 C90 42 90 66 74 66" fill="none" stroke="#8A5A34" strokeWidth={7} strokeLinecap="round" />
      <path
        filter="url(#s-coffee)"
        d="M22 34 H74 V72 C74 84 62 92 48 92 C34 92 22 84 22 72 Z"
        fill="#8A5A34" {...OUTLINE}
      />
      <path d="M28 34 H68 L64 46 H32 Z" fill="#D9C7B8" />
    </svg>
  );
}

function MoonStars(props: IconProps) {
  return (
    <svg {...BASE} {...props}>
      <Shadow id="s-moon" />
      <path
        filter="url(#s-moon)"
        d="M62 8 A42 42 0 1 0 62 92 A34 34 0 1 1 62 8 Z"
        fill="#6C5CE7" {...OUTLINE}
      />
      <path d="M78 20 L81 27 L88 29 L81 31 L78 38 L75 31 L68 29 L75 27 Z" fill="#FFD23F" />
      <path d="M86 46 L88 50 L92 52 L88 54 L86 58 L84 54 L80 52 L84 50 Z" fill="#FFD23F" />
    </svg>
  );
}

function Sun(props: IconProps) {
  return (
    <svg {...BASE} {...props}>
      <Shadow id="s-sun" />
      {Array.from({ length: 8 }).map((_, i) => (
        <rect
          key={i}
          x="46" y="2" width="8" height="18" rx="4"
          fill="#FFC94A"
          transform={`rotate(${i * 45} 50 50)`}
        />
      ))}
      <circle filter="url(#s-sun)" cx="50" cy="50" r="24" fill="#FFD23F" {...OUTLINE} />
    </svg>
  );
}

function Lightning(props: IconProps) {
  return (
    <svg {...BASE} {...props}>
      <Shadow id="s-bolt" />
      <path filter="url(#s-bolt)" d="M56 4 L24 56 H44 L34 96 L82 40 H58 Z" fill="#FFD23F" {...OUTLINE} />
    </svg>
  );
}

function Gift(props: IconProps) {
  return (
    <svg {...BASE} {...props}>
      <Shadow id="s-gift" />
      <path d="M50 32 C40 14 22 16 26 28 C29 34 40 33 50 32 Z" fill="#FFC94A" stroke="#fff" strokeWidth={3.5} strokeLinejoin="round" />
      <path d="M50 32 C60 14 78 16 74 28 C71 34 60 33 50 32 Z" fill="#FFC94A" stroke="#fff" strokeWidth={3.5} strokeLinejoin="round" />
      <rect filter="url(#s-gift)" x="16" y="34" width="68" height="16" rx="2" fill="#FF4B6E" {...OUTLINE} />
      <rect x="16" y="50" width="68" height="42" fill="#FF4B6E" stroke="#fff" strokeWidth={4} />
      <rect x="43" y="34" width="14" height="58" fill="#FFC94A" />
    </svg>
  );
}

function MusicNote(props: IconProps) {
  return (
    <svg {...BASE} {...props}>
      <Shadow id="s-music" />
      <path d="M40 70 V20 L78 10 V60" fill="none" stroke="#B24CF0" strokeWidth={6} strokeLinecap="round" strokeLinejoin="round" />
      <ellipse filter="url(#s-music)" cx="30" cy="72" rx="14" ry="11" fill="#B24CF0" {...OUTLINE} />
      <ellipse cx="68" cy="62" rx="14" ry="11" fill="#B24CF0" stroke="#fff" strokeWidth={4} />
    </svg>
  );
}

function ThumbsUp(props: IconProps) {
  return (
    <svg {...BASE} {...props}>
      <Shadow id="s-thumb" />
      <path
        d="M32 45 C32 30 40 12 46 8 C50 6 54 9 53 15 L48 34 H74 C80 34 84 39 82 45 L74 78 C72 85 66 90 58 90 H32 Z"
        fill="#FFCB6B" {...OUTLINE}
        filter="url(#s-thumb)"
      />
      <rect x="12" y="45" width="20" height="45" rx="8" fill="#4CC9F0" stroke="#fff" strokeWidth={4} />
      <line x1="48" y1="46" x2="76" y2="46" stroke="#F0A93A" strokeWidth={3} />
    </svg>
  );
}

export interface StickerDef {
  key: string;
  label: string;
  Icon: (props: IconProps) => ReactElement;
}

export const STICKER_ART: StickerDef[] = [
  { key: "heart", label: "Heart", Icon: Heart },
  { key: "fire", label: "Fire", Icon: Fire },
  { key: "star", label: "Star", Icon: Star },
  { key: "party_popper", label: "Party popper", Icon: PartyPopper },
  { key: "balloons", label: "Balloons", Icon: Balloons },
  { key: "trophy", label: "Trophy", Icon: Trophy },
  { key: "check_badge", label: "Check", Icon: CheckBadge },
  { key: "crown", label: "Crown", Icon: Crown },
  { key: "rocket", label: "Rocket", Icon: Rocket },
  { key: "coffee_cup", label: "Coffee", Icon: CoffeeCup },
  { key: "moon_stars", label: "Goodnight", Icon: MoonStars },
  { key: "sun", label: "Sunshine", Icon: Sun },
  { key: "lightning", label: "Lightning", Icon: Lightning },
  { key: "gift", label: "Gift", Icon: Gift },
  { key: "music_note", label: "Music", Icon: MusicNote },
  { key: "thumbs_up", label: "Thumbs up", Icon: ThumbsUp },
];

export function getStickerArt(key: string): StickerDef | undefined {
  return STICKER_ART.find((s) => s.key === key);
}
