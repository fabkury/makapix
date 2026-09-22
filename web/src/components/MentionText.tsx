/**
 * Renders a comment body or post description with its mentions as `@handle`
 * profile links (docs/mentions/). Takes a `MentionSource` from
 * `commentMentionSource` / `descriptionMentionSource`, so payloads from a
 * server without mentions render their plain field verbatim.
 *
 * Inline by default: text nodes and links only, so the host element's
 * `white-space` decides how newlines show. `paragraphs` instead renders one
 * <p> per line, for hosts that already did that with the plain text.
 */
import Link from 'next/link';
import type { ReactNode } from 'react';
import { MentionSource, MentionSegment, segmentsOf } from '../lib/mentions';

interface MentionTextProps {
  source: MentionSource;
  paragraphs?: boolean;
}

function renderSegment(seg: MentionSegment, key: string): ReactNode {
  if (seg.kind === 'plain') return seg.text;
  return (
    <Link
      key={key}
      href={`/u/${seg.sqid}`}
      className="mention-link"
      // Hosts are often clickable cards/overlays; the link wins.
      onClick={(e) => e.stopPropagation()}
    >
      @{seg.handle}
    </Link>
  );
}

export default function MentionText({ source, paragraphs = false }: MentionTextProps) {
  const segments = segmentsOf(source);

  let content: ReactNode;
  if (!paragraphs) {
    content = segments.map((seg, i) => renderSegment(seg, `m${i}`));
  } else {
    // Split plain segments on newlines; mentions never contain one.
    const lines: ReactNode[][] = [[]];
    segments.forEach((seg, i) => {
      if (seg.kind === 'mention') {
        lines[lines.length - 1].push(renderSegment(seg, `m${i}`));
        return;
      }
      seg.text.split('\n').forEach((part, j) => {
        if (j > 0) lines.push([]);
        if (part) lines[lines.length - 1].push(part);
      });
    });
    content = lines.map((line, i) => <p key={i}>{line}</p>);
  }

  return (
    <>
      {content}
      <style jsx global>{`
        .mention-link {
          color: var(--accent-cyan);
          font-weight: 600;
          overflow-wrap: anywhere;
        }
      `}</style>
    </>
  );
}
