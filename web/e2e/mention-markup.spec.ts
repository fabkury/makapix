/**
 * Mention markup (docs/mentions/): the app proposal's §11 test vectors, run
 * against web/src/lib/mentions.ts. The same rows live in the app's
 * mention_markup_test.dart and the server's api/tests/test_mentions.py — if a
 * row changes, all three move together.
 *
 * Pure-function spec: no page/browser fixture, no network.
 */
import { test, expect } from '@playwright/test';
import {
  MAX_MENTIONS_PER_TEXT,
  UNKNOWN_MENTION_HANDLE,
  commentMentionSource,
  descriptionMentionSource,
  hasMentionMarkup,
  livePicks,
  markupToComposer,
  parseMentionMarkup,
  plainFromMarkup,
  segmentsOf,
  serializeMentions,
  type MentionSegment,
} from '../src/lib/mentions';

// t5 → fab, Qx → mika, ZZZZ → no account.
const HANDLES = new Map([
  ['t5', 'fab'],
  ['Qx', 'mika'],
]);

const plain = (text: string): MentionSegment => ({ kind: 'plain', text });
const mention = (sqid: string, handle: string): MentionSegment => ({
  kind: 'mention',
  sqid,
  handle,
});

test.describe('§11 test vectors', () => {
  test('hi <@t5>! → link to t5', () => {
    expect(plainFromMarkup('hi <@t5>!', HANDLES)).toBe('hi @fab!');
    expect(parseMentionMarkup('hi <@t5>!', HANDLES)).toEqual([
      plain('hi '),
      mention('t5', 'fab'),
      plain('!'),
    ]);
  });

  test('<@t5>, <@Qx>. → two mentions', () => {
    expect(plainFromMarkup('<@t5>, <@Qx>.', HANDLES)).toBe('@fab, @mika.');
    expect(parseMentionMarkup('<@t5>, <@Qx>.', HANDLES)).toEqual([
      mention('t5', 'fab'),
      plain(', '),
      mention('Qx', 'mika'),
      plain('.'),
    ]);
  });

  test('<@ZZZZ> → plain @user, never a link', () => {
    expect(UNKNOWN_MENTION_HANDLE).toBe('user');
    expect(plainFromMarkup('<@ZZZZ>', HANDLES)).toBe('@user');
    expect(parseMentionMarkup('<@ZZZZ>', HANDLES)).toEqual([plain('@user')]);
  });

  test('blocked / policy-excluded <@t5> is flattened on write → plain @fab', () => {
    // The server stores the flattened text; the client sees plain text only.
    expect(parseMentionMarkup('@fab', HANDLES)).toEqual([plain('@fab')]);
    expect(plainFromMarkup('@fab', HANDLES)).toBe('@fab');
  });

  for (const malformed of ['<@t5', '<@>', '<@ t5>', '< @t5>']) {
    test(`malformed ${JSON.stringify(malformed)} → literal text`, () => {
      expect(plainFromMarkup(malformed, HANDLES)).toBe(malformed);
      expect(parseMentionMarkup(malformed, HANDLES)).toEqual([plain(malformed)]);
      expect(hasMentionMarkup(malformed)).toBe(false);
    });
  }

  test('hand-typed @fab → plain text', () => {
    expect(parseMentionMarkup('@fab', HANDLES)).toEqual([plain('@fab')]);
    expect(hasMentionMarkup('@fab')).toBe(false);
  });

  test('a<@t5>b → no boundary rule', () => {
    expect(plainFromMarkup('a<@t5>b', HANDLES)).toBe('a@fabb');
    expect(parseMentionMarkup('a<@t5>b', HANDLES)).toEqual([
      plain('a'),
      mention('t5', 'fab'),
      plain('b'),
    ]);
  });

  test('17 valid mentions → first 16 link', () => {
    const markup = Array.from({ length: 17 }, () => '<@t5>').join(' ');
    const segs = parseMentionMarkup(markup, HANDLES);
    expect(segs.filter((s) => s.kind === 'mention')).toHaveLength(MAX_MENTIONS_PER_TEXT);
    expect(MAX_MENTIONS_PER_TEXT).toBe(16);
    // The 17th is plain text at the end.
    expect(segs[segs.length - 1]).toEqual(plain(' @fab'));
    expect(plainFromMarkup(markup, HANDLES)).toBe(
      Array.from({ length: 17 }, () => '@fab').join(' '),
    );
  });

  test('<@t5> after t5 renames to fabkury → @fabkury', () => {
    const renamed = { t5: 'fabkury' }; // Record lookup works too
    expect(plainFromMarkup('<@t5>', renamed)).toBe('@fabkury');
    expect(parseMentionMarkup('<@t5>', renamed)).toEqual([mention('t5', 'fabkury')]);
  });
});

test.describe('parser details', () => {
  test('empty text → no segments', () => {
    expect(parseMentionMarkup('', HANDLES)).toEqual([]);
  });

  test('adjacent plain pieces merge (unresolved between text)', () => {
    expect(parseMentionMarkup('x <@ZZZZ> y', HANDLES)).toEqual([plain('x @user y')]);
  });

  test('33-char sqid is not a mention', () => {
    const long = `<@${'a'.repeat(33)}>`;
    expect(parseMentionMarkup(long, HANDLES)).toEqual([plain(long)]);
  });

  test('newlines are preserved in plain segments', () => {
    expect(parseMentionMarkup('line1\n<@t5>\nline3', HANDLES)).toEqual([
      plain('line1\n'),
      mention('t5', 'fab'),
      plain('\nline3'),
    ]);
  });
});

test.describe('serializeMentions', () => {
  const fab = { handle: 'fab', sqid: 't5' };
  const fabkury = { handle: 'fabkury', sqid: 'K9' };
  const mika = { handle: 'mika', sqid: 'Qx' };

  test('picked handle becomes markup', () => {
    expect(serializeMentions('hi @fab!', [fab])).toBe('hi <@t5>!');
  });

  test('no picks → text unchanged', () => {
    expect(serializeMentions('hi @fab!', [])).toBe('hi @fab!');
  });

  test('@ after a handle char does not open a token', () => {
    expect(serializeMentions('mail x@fab', [fab])).toBe('mail x@fab');
    expect(serializeMentions('(@fab)', [fab])).toBe('(<@t5>)');
  });

  test('handle running into more handle chars is not a match', () => {
    expect(serializeMentions('@fabx', [fab])).toBe('@fabx');
    expect(serializeMentions('@fab_', [fab])).toBe('@fab_');
    expect(serializeMentions('@fab-', [fab])).toBe('@fab-');
    expect(serializeMentions('@fabé', [fab])).toBe('@fabé');
    expect(serializeMentions('@fab.', [fab])).toBe('<@t5>.');
  });

  test('longest handle first', () => {
    expect(serializeMentions('@fabkury and @fab', [fab, fabkury])).toBe(
      '<@K9> and <@t5>',
    );
    // Only @fab picked: @fabkury stays plain, @fab links.
    expect(serializeMentions('@fabkury and @fab', [fab])).toBe('@fabkury and <@t5>');
  });

  test('each occurrence consumes one pick', () => {
    expect(serializeMentions('@fab @fab', [fab])).toBe('<@t5> @fab');
    expect(serializeMentions('@fab @fab', [fab, fab])).toBe('<@t5> <@t5>');
  });

  test('two different picks', () => {
    expect(serializeMentions('@mika, @fab', [fab, mika])).toBe('<@Qx>, <@t5>');
  });

  test('cap: at most maxMentions replacements', () => {
    const text = Array.from({ length: 17 }, () => '@fab').join(' ');
    const picks = Array.from({ length: 17 }, () => fab);
    const out = serializeMentions(text, picks);
    expect(out.match(/<@t5>/g)).toHaveLength(16);
    expect(out.endsWith(' @fab')).toBe(true);
    expect(serializeMentions('@fab @mika', [fab, mika], 1)).toBe('<@t5> @mika');
  });

  test('edited or deleted handle drops the pick', () => {
    expect(serializeMentions('hi @fa', [fab])).toBe('hi @fa');
    expect(serializeMentions('hi there', [fab])).toBe('hi there');
    expect(livePicks('hi @fabx', [fab, mika])).toEqual([]);
    expect(livePicks('hi @fab @mika', [fab, mika])).toEqual([fab, mika]);
  });

  test('pasted markup is left alone', () => {
    expect(serializeMentions('<@Qx> @fab', [fab])).toBe('<@Qx> <@t5>');
  });
});

test.describe('edit round-trip and payload fallback', () => {
  test('markup → composer state → same markup', () => {
    const mentions = [
      { public_sqid: 't5', handle: 'fab', avatar_url: null },
      { public_sqid: 'Qx', handle: 'mika', avatar_url: null },
    ];
    const markup = 'great palette <@t5>, see <@Qx>\'s remix';
    const { text, picks } = markupToComposer(markup, mentions);
    expect(text).toBe("great palette @fab, see @mika's remix");
    expect(serializeMentions(text, picks)).toBe(markup);
  });

  test('unresolved mention becomes plain @user on edit', () => {
    const { text, picks } = markupToComposer('hi <@ZZZZ>', []);
    expect(text).toBe('hi @user');
    expect(picks).toEqual([]);
  });

  test('comment payload without markup fields falls back to body, verbatim', () => {
    const src = commentMentionSource({ body: 'raw <@t5> text' });
    expect(src.isMarkup).toBe(false);
    expect(segmentsOf(src)).toEqual([plain('raw <@t5> text')]);
  });

  test('comment payload with markup fields renders links', () => {
    const src = commentMentionSource({
      body: 'hi @fab',
      body_markup: 'hi <@t5>',
      mentions: [{ public_sqid: 't5', handle: 'fab' }],
    });
    expect(segmentsOf(src)).toEqual([plain('hi '), mention('t5', 'fab')]);
  });

  test('post payload: null description_markup → empty', () => {
    const src = descriptionMentionSource({ description: null, description_markup: null });
    expect(segmentsOf(src)).toEqual([]);
  });
});
