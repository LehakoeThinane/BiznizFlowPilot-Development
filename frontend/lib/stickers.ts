// Curated built-in sticker set. Keys must match app/services/messaging.py's
// STICKER_KEYS exactly - the server validates against that list.
export interface Sticker {
  key: string;
  emoji: string;
  label: string;
}

export const STICKERS: Sticker[] = [
  { key: "smile", emoji: "😄", label: "Smile" },
  { key: "laugh", emoji: "😂", label: "Laugh" },
  { key: "heart", emoji: "❤️", label: "Heart" },
  { key: "thumbs_up", emoji: "👍", label: "Thumbs up" },
  { key: "thumbs_down", emoji: "👎", label: "Thumbs down" },
  { key: "fire", emoji: "🔥", label: "Fire" },
  { key: "clap", emoji: "👏", label: "Clap" },
  { key: "party", emoji: "🎉", label: "Party" },
  { key: "wave", emoji: "👋", label: "Wave" },
  { key: "thinking", emoji: "🤔", label: "Thinking" },
  { key: "cry", emoji: "😢", label: "Cry" },
  { key: "angry", emoji: "😠", label: "Angry" },
  { key: "cool", emoji: "😎", label: "Cool" },
  { key: "wink", emoji: "😉", label: "Wink" },
  { key: "star", emoji: "⭐", label: "Star" },
  { key: "check", emoji: "✅", label: "Check" },
  { key: "cross", emoji: "❌", label: "Cross" },
  { key: "hundred", emoji: "💯", label: "100" },
  { key: "pray", emoji: "🙏", label: "Pray" },
  { key: "muscle", emoji: "💪", label: "Muscle" },
  { key: "eyes", emoji: "👀", label: "Eyes" },
  { key: "rocket", emoji: "🚀", label: "Rocket" },
  { key: "clown", emoji: "🤡", label: "Clown" },
  { key: "ghost", emoji: "👻", label: "Ghost" },
];

export function stickerEmoji(key: string): string {
  return STICKERS.find((s) => s.key === key)?.emoji ?? "❔";
}
