/**
 * Mentions — the `<@SQID>` markup that comment bodies and post descriptions
 * may carry, and the conversions the website needs around it
 * (docs/mentions/README.md).
 *
 * This is a port of the app's `mention_markup.dart` and must behave
 * identically: the proposal's §11 test vectors run against both, and against
 * the server (`web/e2e/mention-markup.spec.ts`, `api/tests/test_mentions.py`).
 *
 * The markup stores the target's `public_sqid`, never the handle: handles are
 * mutable, so the server resolves each sqid to the current handle on every
 * read and sends it in the `mentions` array beside `body_markup` /
 * `description_markup`.
 *
 * Pure module: no network, no DOM.
 */

/**
 * Cap on how many mentions one comment or description may carry. The server
 * is the authority (`max_mentions_per_text` on GET /config, also the feature's
 * launch signal) and flattens extras on write rather than rejecting the text.
 */
export const MAX_MENTIONS_PER_TEXT = 16;

/** Handle shown for a sqid that resolves to no account (a deleted user). */
export const UNKNOWN_MENTION_HANDLE = 'user';

/**
 * `mention := "<@" sqid ">"`, sqid = `[A-Za-z0-9]{1,32}` (server decision S1).
 * Anything else starting with `<@` is plain text. No word-boundary rule.
 */
export const MENTION_PATTERN = /<@([A-Za-z0-9]{1,32})>/g;

/**
 * Characters a handle may contain (mirrors the server's handle rule). Used to
 * decide whether an `@handle` token in composer text is still intact.
 */
export const HANDLE_CHAR = /[\p{L}\p{Nd}\p{Mn}\p{Mc}_-]/u;

/** One entry of the `mentions` array the server sends beside the markup. */
export interface MentionRef {
  public_sqid: string;
  handle: string;
  avatar_url?: string | null;
}

/** A pick the composer recorded: the user chose `handle`, standing for `sqid`. */
export interface PickedMention {
  handle: string;
  sqid: string;
}

export type MentionSegment =
  | { kind: 'plain'; text: string }
  | { kind: 'mention'; sqid: string; handle: string };

/** sqid → current handle. */
export type HandleLookup = Map<string, string> | Record<string, string>;

/** Builds a sqid → handle lookup from a payload's `mentions` array. */
export function handlesOf(refs: MentionRef[] | null | undefined): Map<string, string> {
  const map = new Map<string, string>();
  for (const r of refs ?? []) {
    if (r && r.public_sqid) map.set(r.public_sqid, r.handle ?? UNKNOWN_MENTION_HANDLE);
  }
  return map;
}

function lookup(handles: HandleLookup, sqid: string): string | undefined {
  if (handles instanceof Map) return handles.get(sqid);
  return Object.prototype.hasOwnProperty.call(handles, sqid) ? handles[sqid] : undefined;
}

/**
 * Splits `markup` into plain and mention segments.
 *
 * A sqid missing from `handles` renders as plain `@user` (never a link).
 * Malformed markup (`<@t5`, `<@>`, `<@ t5>`, `< @t5>`) is literal text.
 * At most `maxMentions` mentions link; later ones render as plain `@handle`.
 * Adjacent plain pieces are merged; the result never holds an empty segment.
 */
export function parseMentionMarkup(
  markup: string,
  handles: HandleLookup = new Map(),
  maxMentions: number = MAX_MENTIONS_PER_TEXT,
): MentionSegment[] {
  if (!markup) return [];

  const out: MentionSegment[] = [];
  let buffer = '';
  let linked = 0;
  let cursor = 0;

  const flush = () => {
    if (buffer) {
      out.push({ kind: 'plain', text: buffer });
      buffer = '';
    }
  };

  for (const m of markup.matchAll(MENTION_PATTERN)) {
    const start = m.index ?? 0;
    buffer += markup.slice(cursor, start);
    cursor = start + m[0].length;

    const sqid = m[1];
    const handle = lookup(handles, sqid);

    if (handle === undefined) {
      buffer += `@${UNKNOWN_MENTION_HANDLE}`;
    } else if (linked >= maxMentions) {
      buffer += `@${handle}`;
    } else {
      flush();
      out.push({ kind: 'mention', sqid, handle });
      linked++;
    }
  }

  buffer += markup.slice(cursor);
  flush();
  return out;
}

/** The plain rendering of `markup`: every `<@SQID>` replaced by `@handle`. */
export function plainFromMarkup(
  markup: string,
  handles: HandleLookup = new Map(),
  maxMentions: number = MAX_MENTIONS_PER_TEXT,
): string {
  return parseMentionMarkup(markup, handles, maxMentions)
    .map((s) => (s.kind === 'plain' ? s.text : `@${s.handle}`))
    .join('');
}

/** True when `markup` contains at least one syntactically valid mention. */
export function hasMentionMarkup(markup: string): boolean {
  return new RegExp(MENTION_PATTERN.source).test(markup);
}

/** How many syntactically valid mentions `markup` contains. */
export function countMentionMarkup(markup: string): number {
  let n = 0;
  for (const _ of markup.matchAll(MENTION_PATTERN)) n++;
  return n;
}

function isHandleChar(ch: string | undefined): boolean {
  return ch !== undefined && HANDLE_CHAR.test(ch);
}

/**
 * Shared walk behind `serializeMentions` and `livePicks`: returns the markup
 * and the picks that were consumed.
 */
function matchPicks(
  displayText: string,
  picked: PickedMention[],
  maxMentions: number,
): { markup: string; used: PickedMention[] } {
  if (!displayText || picked.length === 0) return { markup: displayText, used: [] };

  // Longest handle first, so `@fabkury` is not eaten by a pick of `@fab`.
  const remaining = [...picked].sort((a, b) => b.handle.length - a.handle.length);
  const used: PickedMention[] = [];

  let out = '';
  let i = 0;

  while (i < displayText.length) {
    const ch = displayText[i];
    if (ch !== '@' || used.length >= maxMentions || remaining.length === 0) {
      out += ch;
      i++;
      continue;
    }

    // The `@` must open a token: start of text, or after a non-handle char.
    if (i > 0 && isHandleChar(displayText[i - 1])) {
      out += ch;
      i++;
      continue;
    }

    let hit: PickedMention | null = null;
    for (const p of remaining) {
      const end = i + 1 + p.handle.length;
      if (end > displayText.length) continue;
      if (displayText.slice(i + 1, end) !== p.handle) continue;
      // The token must end here, not run into more handle characters.
      if (end < displayText.length && isHandleChar(displayText[end])) continue;
      hit = p;
      break;
    }

    if (!hit) {
      out += ch;
      i++;
      continue;
    }

    out += `<@${hit.sqid}>`;
    i += 1 + hit.handle.length;
    used.push(hit);
    remaining.splice(remaining.indexOf(hit), 1);
  }

  return { markup: out, used };
}

/**
 * Turns composer text into the markup to send.
 *
 * The composer shows plain `@handle` (the user never sees a sqid) and keeps
 * the list of picks. A pick becomes `<@sqid>` only where its `@handle` token
 * still appears intact: the `@` starts the text or follows a non-handle char,
 * and the handle does not run into more handle chars. Editing `@fab` into
 * `@fabx`, or deleting it, quietly drops that mention.
 *
 * Each occurrence consumes one pick. Where two picked handles both match at
 * one position (`@fab` and `@fabkury`), the longer wins. At most `maxMentions`
 * replacements are made. Text that already looks like markup is left alone.
 */
export function serializeMentions(
  displayText: string,
  picked: PickedMention[],
  maxMentions: number = MAX_MENTIONS_PER_TEXT,
): string {
  return matchPicks(displayText, picked, maxMentions).markup;
}

/**
 * The subset of `picked` that still matches an intact token in `displayText`
 * (in match order). The composer prunes its picks with this on every edit, so
 * a deleted mention does not come back when the handle is retyped by hand.
 */
export function livePicks(
  displayText: string,
  picked: PickedMention[],
  maxMentions: number = MAX_MENTIONS_PER_TEXT,
): PickedMention[] {
  return matchPicks(displayText, picked, maxMentions).used;
}

/**
 * Converts stored markup into composer state for editing: the display text
 * (`@handle`, never a sqid) plus the picks that make an unchanged save
 * round-trip to the same markup. Unresolvable or past-cap mentions become
 * plain text, as they render.
 */
export function markupToComposer(
  markup: string,
  mentions: MentionRef[] | null | undefined,
  maxMentions: number = MAX_MENTIONS_PER_TEXT,
): { text: string; picks: PickedMention[] } {
  const segments = parseMentionMarkup(markup, handlesOf(mentions), maxMentions);
  let text = '';
  const picks: PickedMention[] = [];
  for (const s of segments) {
    if (s.kind === 'plain') {
      text += s.text;
    } else {
      text += `@${s.handle}`;
      picks.push({ handle: s.handle, sqid: s.sqid });
    }
  }
  return { text, picks };
}

/**
 * What a renderer needs. `isMarkup` is false when the payload only had the
 * plain field: plain text is rendered verbatim, never parsed, so a plain body
 * that happens to contain `<@abc>` does not turn into `@user`.
 */
export interface MentionSource {
  text: string;
  mentions: MentionRef[];
  isMarkup: boolean;
}

/**
 * Picks the markup + mentions of a comment payload, falling back to the plain
 * `body` when the server (or a cached response) predates mentions.
 */
export function commentMentionSource(c: {
  body?: string | null;
  body_markup?: string | null;
  mentions?: MentionRef[] | null;
}): MentionSource {
  if (typeof c.body_markup === 'string') {
    return { text: c.body_markup, mentions: c.mentions ?? [], isMarkup: true };
  }
  return { text: c.body ?? '', mentions: [], isMarkup: false };
}

/** Same as `commentMentionSource`, for a post's description. */
export function descriptionMentionSource(p: {
  description?: string | null;
  description_markup?: string | null;
  mentions?: MentionRef[] | null;
}): MentionSource {
  if (typeof p.description_markup === 'string') {
    return { text: p.description_markup, mentions: p.mentions ?? [], isMarkup: true };
  }
  return { text: p.description ?? '', mentions: [], isMarkup: false };
}

/** Segments of a `MentionSource`: parsed markup, or the plain text verbatim. */
export function segmentsOf(
  source: MentionSource,
  maxMentions: number = MAX_MENTIONS_PER_TEXT,
): MentionSegment[] {
  if (!source.isMarkup) return source.text ? [{ kind: 'plain', text: source.text }] : [];
  return parseMentionMarkup(source.text, handlesOf(source.mentions), maxMentions);
}

/** Composer state for editing a `MentionSource` (see `markupToComposer`). */
export function composerStateOf(
  source: MentionSource,
  maxMentions: number = MAX_MENTIONS_PER_TEXT,
): { text: string; picks: PickedMention[] } {
  if (!source.isMarkup) return { text: source.text, picks: [] };
  return markupToComposer(source.text, source.mentions, maxMentions);
}
