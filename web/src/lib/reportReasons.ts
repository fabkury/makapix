// Human labels for report reason codes (docs/ugc-safety/ D3; mirror of
// api/app/schemas.py:REPORT_REASONS). Legacy rows may still carry "abuse" ->
// render as "Harassment or bullying" (D21).
export const REPORT_REASON_LABELS: Record<string, string> = {
  spam: "Spam or misleading",
  harassment: "Harassment or bullying",
  hate: "Hate or discrimination",
  sexual_explicit: "Sexual or explicit content",
  violence_gore: "Violence or gore",
  illegal_csam: "Illegal content or child endangerment",
  self_harm: "Self-harm or suicide",
  copyright: "Copyright or IP violation",
  other: "Something else",
  abuse: "Harassment or bullying",
};

export const reportReasonLabel = (code: string | null | undefined): string =>
  (code && REPORT_REASON_LABELS[code]) || code || "Something else";
