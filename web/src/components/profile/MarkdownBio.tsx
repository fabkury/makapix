/**
 * MarkdownBio component - renders bio with simple markdown support.
 * Supports:
 * - **bold**
 * - *italic*
 * - [text](url) links
 * - `code`
 * - [text]{color:#hex} custom colors
 */

import { useMemo } from 'react';

interface MarkdownBioProps {
  bio: string;
  maxLength?: number;
}

// Allowed CSS color values (hex, named colors)
const COLOR_PATTERN = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;
const NAMED_COLORS = [
  'red', 'blue', 'green', 'yellow', 'purple', 'pink', 'cyan', 'white', 'black',
  'orange', 'gray', 'grey', 'magenta', 'lime', 'teal', 'navy', 'maroon', 'olive'
];

function isValidColor(color: string): boolean {
  return COLOR_PATTERN.test(color) || NAMED_COLORS.includes(color.toLowerCase());
}

function sanitizeColor(color: string): string | null {
  const trimmed = color.trim().toLowerCase();
  if (COLOR_PATTERN.test(trimmed) || NAMED_COLORS.includes(trimmed)) {
    return trimmed;
  }
  return null;
}

function parseMarkdown(text: string): React.ReactNode[] {
  const elements: React.ReactNode[] = [];
  let currentIndex = 0;
  let keyIndex = 0;

  // Patterns to match
  // Order matters - more specific patterns first
  const patterns = [
    // Custom color: [text]{color:value}
    { regex: /\[([^\]]+)\]\{color:([^}]+)\}/g, type: 'color' },
    // Links: [text](url)
    { regex: /\[([^\]]+)\]\(([^)]+)\)/g, type: 'link' },
    // Bold: **text**
    { regex: /\*\*([^*]+)\*\*/g, type: 'bold' },
    // Italic: *text*
    { regex: /\*([^*]+)\*/g, type: 'italic' },
    // Code: `text`
    { regex: /`([^`]+)`/g, type: 'code' },
  ];

  // Find all matches
  type Match = { start: number; end: number; type: string; groups: string[] };
  const matches: Match[] = [];

  for (const pattern of patterns) {
    const regex = new RegExp(pattern.regex.source, 'g');
    let match;
    while ((match = regex.exec(text)) !== null) {
      matches.push({
        start: match.index,
        end: match.index + match[0].length,
        type: pattern.type,
        groups: match.slice(1),
      });
    }
  }

  // Sort by position, filter overlapping
  matches.sort((a, b) => a.start - b.start);
  const filtered: Match[] = [];
  let lastEnd = 0;
  for (const m of matches) {
    if (m.start >= lastEnd) {
      filtered.push(m);
      lastEnd = m.end;
    }
  }

  // Build elements
  for (const m of filtered) {
    // Add plain text before this match
    if (m.start > currentIndex) {
      elements.push(text.slice(currentIndex, m.start));
    }

    // Add the formatted element
    switch (m.type) {
      case 'color': {
        const [content, colorValue] = m.groups;
        const safeColor = sanitizeColor(colorValue);
        if (safeColor) {
          elements.push(
            <span key={keyIndex++} style={{ color: safeColor }}>
              {content}
            </span>
          );
        } else {
          elements.push(content);
        }
        break;
      }
      case 'link': {
        const [linkText, url] = m.groups;
        // Only allow http/https URLs
        if (url.startsWith('http://') || url.startsWith('https://')) {
          elements.push(
            <a
              key={keyIndex++}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="bio-link"
            >
              {linkText}
            </a>
          );
        } else {
          elements.push(`[${linkText}](${url})`);
        }
        break;
      }
      case 'bold':
        elements.push(<strong key={keyIndex++}>{m.groups[0]}</strong>);
        break;
      case 'italic':
        elements.push(<em key={keyIndex++} className="bio-italic">{m.groups[0]}</em>);
        break;
      case 'code':
        elements.push(<code key={keyIndex++} className="bio-code">{m.groups[0]}</code>);
        break;
    }

    currentIndex = m.end;
  }

  // Add remaining plain text
  if (currentIndex < text.length) {
    elements.push(text.slice(currentIndex));
  }

  return elements;
}

export default function MarkdownBio({ bio, maxLength = 1000 }: MarkdownBioProps) {
  const truncatedBio = bio.length > maxLength ? bio.slice(0, maxLength) + '...' : bio;

  const elements = useMemo(() => {
    // Split by newlines and process each line
    const lines = truncatedBio.split('\n');
    return lines.map((line, i) => (
      <p key={i} className="bio-line">
        {parseMarkdown(line)}
      </p>
    ));
  }, [truncatedBio]);

  return (
    <div className="markdown-bio">
      {elements}

      <style jsx global>{`
        .markdown-bio {
          font-size: 0.95rem;
          line-height: 1.6;
          color: rgba(255, 255, 255, 0.8);
        }
        .markdown-bio .bio-line {
          margin: 0 0 8px 0;
        }
        .markdown-bio .bio-line:last-child {
          margin-bottom: 0;
        }
        .markdown-bio strong {
          color: white;
          font-weight: 600;
        }
        .markdown-bio .bio-italic {
          color: var(--accent-cyan);
        }
        .markdown-bio .bio-link {
          color: var(--accent-pink);
          text-decoration: none;
        }
        .markdown-bio .bio-link:hover {
          text-decoration: underline;
        }
        .markdown-bio .bio-code {
          color: var(--accent-cyan);
          background: rgba(255, 255, 255, 0.1);
          padding: 2px 6px;
          border-radius: 4px;
          font-family: monospace;
          font-size: 0.9em;
        }
      `}</style>
    </div>
  );
}
