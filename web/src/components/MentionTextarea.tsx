/**
 * Textarea with @-mention autocomplete (docs/mentions/). The one composer used
 * by every comment, reply and description field on the website.
 *
 * The text always shows plain `@handle` — never `<@SQID>`. When the user picks
 * a candidate, the composer inserts `@handle ` and records the {handle, sqid}
 * pick; on submit the parent calls `serializeMentions(text, picks)` (or
 * `draft.toMarkup()` from `useMentionDraft`) to get the markup to send.
 * Editing or deleting a picked handle drops its pick, so what links is always
 * what the user sees.
 *
 * Active only when signed in AND GET /config advertises
 * `max_mentions_per_text` (the launch signal); otherwise it behaves exactly
 * like a plain textarea. `mentions={false}` renders a bare <textarea> (used
 * for the deprecated blog, which never gets mentions).
 */
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type TextareaHTMLAttributes,
} from 'react';
import {
  getAccessToken,
  getMentionCandidates,
  getMentionsConfig,
  type MentionCandidate,
  type MentionCandidateReason,
} from '../lib/api';
import {
  HANDLE_CHAR,
  MAX_MENTIONS_PER_TEXT,
  type PickedMention,
  countMentionMarkup,
  livePicks,
  serializeMentions,
} from '../lib/mentions';

const DEBOUNCE_MS = 250;
const MAX_QUERY_LENGTH = 32;

const REASON_LABELS: Record<MentionCandidateReason, string> = {
  owner: 'Artist',
  thread: 'In this thread',
  following: 'You follow',
  follower: 'Follows you',
  search: '',
};

/**
 * Composer state for one field: the display text plus the picks. `bind` spreads
 * onto <MentionTextarea>; `toMarkup()` is what to send.
 */
export function useMentionDraft(initialText = '') {
  const [text, setText] = useState(initialText);
  const [picks, setPicks] = useState<PickedMention[]>([]);

  const reset = useCallback((nextText = '', nextPicks: PickedMention[] = []) => {
    setText(nextText);
    setPicks(nextPicks);
  }, []);

  const toMarkup = useCallback(
    () => serializeMentions(text, picks, MAX_MENTIONS_PER_TEXT),
    [text, picks],
  );

  return {
    text,
    picks,
    setText,
    setPicks,
    reset,
    toMarkup,
    bind: { value: text, onChange: setText, picks, onPicksChange: setPicks },
  };
}

/** The `@token` the caret is in: `start` is the index of the `@`. */
interface ActiveToken {
  start: number;
  end: number;
  query: string;
}

function isHandleChar(ch: string | undefined): boolean {
  return ch !== undefined && HANDLE_CHAR.test(ch);
}

/**
 * The token opens at an `@` that starts the text or follows a non-handle char
 * (the serializer's rule), and runs from there to the caret.
 */
function findActiveToken(text: string, caret: number): ActiveToken | null {
  let i = caret;
  while (i > 0 && isHandleChar(text[i - 1])) i--;
  if (i === 0 || text[i - 1] !== '@') return null;
  const at = i - 1;
  if (at > 0 && isHandleChar(text[at - 1])) return null;
  const query = text.slice(i, caret);
  if (query.length > MAX_QUERY_LENGTH) return null;
  return { start: at, end: caret, query };
}

interface MentionTextareaProps
  extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'value' | 'onChange'> {
  value: string;
  onChange: (value: string) => void;
  picks: PickedMention[];
  onPicksChange: (picks: PickedMention[]) => void;
  /** Integer post id: enables the owner/thread candidate tiers. */
  postId?: number | null;
  /** false renders a bare textarea with no mention support at all. */
  mentions?: boolean;
}

export default function MentionTextarea({
  value,
  onChange,
  picks,
  onPicksChange,
  postId = null,
  mentions = true,
  onKeyDown,
  onSelect,
  onBlur,
  onFocus,
  ...rest
}: MentionTextareaProps) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const listId = useId();

  const [maxMentions, setMaxMentions] = useState<number | null>(null);
  const [signedIn, setSignedIn] = useState(false);
  const [focused, setFocused] = useState(false);
  const [token, setToken] = useState<ActiveToken | null>(null);
  const [items, setItems] = useState<MentionCandidate[]>([]);
  const [active, setActive] = useState(0);
  // Escape dismisses the list for the token that starts at this index.
  const [dismissedAt, setDismissedAt] = useState<number | null>(null);

  useEffect(() => {
    if (!mentions) return;
    setSignedIn(!!getAccessToken());
    let cancelled = false;
    getMentionsConfig().then((cfg) => {
      if (!cancelled) setMaxMentions(cfg ? cfg.max_mentions_per_text : null);
    });
    return () => {
      cancelled = true;
    };
  }, [mentions]);

  const enabled = mentions && signedIn && maxMentions !== null;
  const cap = maxMentions ?? MAX_MENTIONS_PER_TEXT;

  // Mentions the text will carry on send: picks still intact + pasted markup.
  const mentionCount = useMemo(
    () => (enabled ? countMentionMarkup(serializeMentions(value, picks, Infinity)) : 0),
    [enabled, value, picks],
  );
  const capReached = mentionCount >= cap;

  const syncToken = useCallback(() => {
    const el = ref.current;
    if (!enabled || !el || el.selectionStart !== el.selectionEnd) {
      setToken(null);
      return;
    }
    const next = findActiveToken(el.value, el.selectionStart);
    setToken((prev) =>
      prev && next && prev.start === next.start && prev.end === next.end && prev.query === next.query
        ? prev
        : next,
    );
  }, [enabled]);

  // Re-derive the token whenever the text changes (typing, or a parent reset).
  useEffect(() => {
    if (focused) syncToken();
    else setToken(null);
  }, [value, focused, syncToken]);

  useEffect(() => {
    if (!token) setDismissedAt(null);
  }, [token]);

  const tokenStart = token?.start ?? null;
  const tokenQuery = token?.query ?? null;
  const suppressed = tokenStart !== null && dismissedAt === tokenStart;

  // A different token never shows the previous token's candidates.
  useEffect(() => {
    setItems([]);
  }, [tokenStart]);

  // Fetch candidates: debounced, and each new query aborts the previous one.
  useEffect(() => {
    if (!enabled || tokenQuery === null || capReached || suppressed) {
      setItems([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      getMentionCandidates(tokenQuery, postId, controller.signal)
        .then((result) => {
          if (controller.signal.aborted) return;
          setItems(result);
          setActive(0);
        })
        .catch(() => {
          if (!controller.signal.aborted) setItems([]);
        });
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [enabled, tokenStart, tokenQuery, capReached, suppressed, postId]);

  const open = enabled && focused && token !== null && !suppressed && !capReached && items.length > 0;
  const showCapHint = enabled && focused && token !== null && !suppressed && capReached;

  const handleChange = (next: string) => {
    onChange(next);
    if (enabled && picks.length > 0) {
      const kept = livePicks(next, picks, Infinity);
      if (kept.length !== picks.length) onPicksChange(kept);
    }
  };

  const pick = (candidate: MentionCandidate) => {
    const el = ref.current;
    if (!token || !el) return;
    // Replace the whole token, including any handle chars after the caret.
    let end = token.end;
    while (end < value.length && isHandleChar(value[end])) end++;
    const after = value.slice(end);
    const needsSpace = !/^\s/.test(after);
    const insert = `@${candidate.handle}${needsSpace ? ' ' : ''}`;
    const next = value.slice(0, token.start) + insert + after;
    if (el.maxLength > 0 && next.length > el.maxLength) return;

    const caret = token.start + insert.length + (needsSpace ? 0 : 1);
    onChange(next);
    onPicksChange(
      livePicks(next, [...picks, { handle: candidate.handle, sqid: candidate.public_sqid }], Infinity),
    );
    setItems([]);
    setToken(null);
    requestAnimationFrame(() => {
      el.focus();
      el.setSelectionRange(caret, caret);
    });
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (open && !e.nativeEvent.isComposing) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActive((a) => (a + 1) % items.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActive((a) => (a - 1 + items.length) % items.length);
        return;
      }
      if ((e.key === 'Enter' && !e.shiftKey) || e.key === 'Tab') {
        e.preventDefault();
        const choice = items[Math.min(active, items.length - 1)];
        if (choice) pick(choice);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        if (token) setDismissedAt(token.start);
        return;
      }
    }
    onKeyDown?.(e);
  };

  if (!mentions) {
    return (
      <textarea
        ref={ref}
        {...rest}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        onSelect={onSelect}
        onBlur={onBlur}
        onFocus={onFocus}
      />
    );
  }

  const optionId = (i: number) => `${listId}-opt-${i}`;

  return (
    <div className="mention-composer">
      <textarea
        ref={ref}
        {...rest}
        value={value}
        onChange={(e) => handleChange(e.target.value)}
        onKeyDown={handleKeyDown}
        onSelect={(e) => {
          syncToken();
          onSelect?.(e);
        }}
        onFocus={(e) => {
          setFocused(true);
          onFocus?.(e);
        }}
        onBlur={(e) => {
          setFocused(false);
          onBlur?.(e);
        }}
        role={enabled ? 'combobox' : undefined}
        aria-multiline={enabled ? true : undefined}
        aria-autocomplete={enabled ? 'list' : undefined}
        aria-expanded={enabled ? open : undefined}
        aria-controls={open ? listId : undefined}
        aria-activedescendant={open ? optionId(active) : undefined}
      />
      {open && (
        <ul id={listId} role="listbox" aria-label="Mention someone" className="mention-list">
          {items.map((c, i) => (
            <li
              key={c.public_sqid}
              id={optionId(i)}
              role="option"
              aria-selected={i === active}
              className={`mention-option ${i === active ? 'is-active' : ''}`}
              // Keep focus in the textarea; pick on press.
              onMouseDown={(e) => {
                e.preventDefault();
                pick(c);
              }}
              onMouseEnter={() => setActive(i)}
            >
              {c.avatar_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={c.avatar_url} alt="" width={24} height={24} className="avatar mention-avatar" />
              ) : (
                <span className="mention-avatar placeholder" aria-hidden="true">
                  {c.handle.charAt(0).toUpperCase()}
                </span>
              )}
              <span className="mention-handle">@{c.handle}</span>
              {REASON_LABELS[c.reason] && (
                <span className="mention-reason">{REASON_LABELS[c.reason]}</span>
              )}
            </li>
          ))}
        </ul>
      )}
      {showCapHint && (
        <div className="mention-list mention-cap-hint" role="status">
          You can mention up to {cap} people in one text.
        </div>
      )}
      <style jsx>{`
        .mention-composer {
          position: relative;
          display: block;
          width: 100%;
        }
        .mention-list {
          position: absolute;
          top: calc(100% + 4px);
          left: 0;
          right: 0;
          z-index: 50;
          max-height: 240px;
          overflow-y: auto;
          margin: 0;
          padding: 4px;
          list-style: none;
          background: var(--bg-secondary);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          box-shadow: 0 10px 38px -10px rgba(0, 0, 0, 0.5), 0 10px 20px -15px rgba(0, 0, 0, 0.4);
          text-align: left;
        }
        .mention-option {
          display: flex;
          align-items: center;
          min-height: 40px;
          padding: 6px 10px;
          border-radius: 6px;
          cursor: pointer;
          color: var(--text-primary);
          font-size: 0.9rem;
        }
        .mention-option.is-active {
          background: var(--bg-tertiary);
        }
        .mention-avatar {
          width: 24px;
          height: 24px;
          border-radius: 4px;
          object-fit: cover;
          flex-shrink: 0;
          margin-right: 10px;
        }
        .mention-avatar.placeholder {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          background: var(--bg-tertiary);
          color: var(--text-secondary);
          font-size: 0.75rem;
          font-weight: 700;
        }
        .mention-handle {
          flex: 1;
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-weight: 600;
        }
        .mention-reason {
          flex-shrink: 0;
          margin-left: 10px;
          font-size: 0.75rem;
          color: var(--text-muted);
        }
        .mention-cap-hint {
          padding: 10px 12px;
          font-size: 0.8rem;
          color: var(--text-secondary);
        }
      `}</style>
    </div>
  );
}
