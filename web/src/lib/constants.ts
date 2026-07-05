// Mirrors the backend source of truth: api/app/constants.py:MONITORED_HASHTAGS.
// Posts carrying any of these tags are hidden in feeds/search/players unless the
// user has explicitly opted into seeing that tag in their content settings.
export const MONITORED_HASHTAGS: {
  tag: string;
  label: string;
  description: string;
}[] = [
  { tag: "politics", label: "#politics", description: "Political content" },
  { tag: "nsfw", label: "#nsfw", description: "Not safe for work" },
  { tag: "explicit", label: "#explicit", description: "Explicit content" },
  {
    tag: "13plus",
    label: "#13plus",
    description: "Intended for ages 13 and up",
  },
  {
    tag: "violence",
    label: "#violence",
    description: "Depictions of violence",
  },
];

export const MONITORED_HASHTAG_SET = new Set(
  MONITORED_HASHTAGS.map((m) => m.tag),
);
