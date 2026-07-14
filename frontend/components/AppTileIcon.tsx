// Inline SVGs instead of the Material Symbols icon font for the home page
// app tiles - the font's ligature rendering was unreliable at this size
// (rendered outside its own box instead of substituting the glyph), while
// inline SVG (same technique as the sidebar logo mark) has no such risk.
const PATHS: Record<string, string> = {
  payments:
    "M2 7a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7Z M2 10h20 M6 15h4",
  groups:
    "M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z M2.5 20a6.5 6.5 0 0 1 13 0 M17 8.5a2.5 2.5 0 1 0 0-5 M21.5 19.5a5.5 5.5 0 0 0-5-5.5",
  event_available:
    "M5 4h14a1 1 0 0 1 1 1v15a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Z M4 9h16 M8 2v4 M16 2v4 M8.5 14.5l2 2 4-4",
  account_balance:
    "M4 10h16 M4 10 12 4l8 6 M6 10v9 M10 10v9 M14 10v9 M18 10v9 M3 21h18",
  receipt_long:
    "M6 2h12a1 1 0 0 1 1 1v18l-2.5-1.5L14 21l-2.5-1.5L9 21l-2.5-1.5L4 21V3a1 1 0 0 1 1-1Z M8 7h8 M8 11h8 M8 15h5",
  track_changes:
    "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z M12 12h.01",
  trending_up: "M3 17l6-6 4 4 8-8 M15 7h6v6",
  shopping_cart:
    "M3 4h2l2.4 12.2a2 2 0 0 0 2 1.6h8.4a2 2 0 0 0 2-1.6L22 8H6 M9.5 21a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z M18 21a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z",
  fact_check:
    "M5 4h14a1 1 0 0 1 1 1v15a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Z M7.5 9l1.5 1.5L12 7.5 M8 15h8 M8 18h8",
  inventory_2:
    "M3 8l9-5 9 5-9 5-9-5Z M3 8v9l9 5 9-5V8 M12 13v9",
  warehouse: "M3 10 12 4l9 6v10H3V10Z M9 20v-6h6v6 M3 10h18",
  handshake: "M9 17H7a5 5 0 0 1 0-10h2 M15 7h2a5 5 0 0 1 0 10h-2 M8 12h8",
  task_alt:
    "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z M8.5 12.5l2.2 2.2L16 10",
  analytics: "M4 20V10 M10 20V4 M16 20v-7 M21 20H3",
  account_tree:
    "M5 5h5v5H5V5Z M14 5h5v5h-5V5Z M9.5 8h5 M7.5 10v4h4v3 M14.5 10v4h-3 M6 16h4v5H6v-5Z M13 16h5v5h-5v-5Z",
  auto_awesome:
    "M12 3l1.8 4.2L18 9l-4.2 1.8L12 15l-1.8-4.2L6 9l4.2-1.8L12 3Z M5 15.5l.9 2.1L8 18.5l-2.1.9L5 21.5l-.9-2.1L2 18.5l2.1-.9L5 15.5Z",
  bolt: "M13 2 4 14h6l-1 8 9-12h-6l1-8Z",
};

export function AppTileIcon({ name, className }: { name: string; className?: string }) {
  const d = PATHS[name];
  if (!d) return null;
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {d.split(" M").map((segment, i) => (
        <path key={i} d={i === 0 ? segment : `M${segment}`} />
      ))}
    </svg>
  );
}
