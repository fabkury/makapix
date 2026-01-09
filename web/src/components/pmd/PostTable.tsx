import { useState, useMemo } from 'react';
import Image from 'next/image';

export interface PMDPost {
  id: number;
  public_sqid: string;
  title: string;
  description: string | null;
  created_at: string;
  width: number;
  height: number;
  frame_count: number;
  file_format: string | null;
  file_bytes: number | null;
  art_url: string;
  hidden_by_user: boolean;
  reaction_count: number;
  comment_count: number;
  view_count: number;
}

interface PostTableProps {
  posts: PMDPost[];
  selectedIds: Set<number>;
  setSelectedIds: (ids: Set<number>) => void;
  currentPage: number;
  setCurrentPage: (page: number) => void;
  itemsPerPage: number;
  loading: boolean;
}

type SortKey = 'title' | 'created_at' | 'width' | 'height' | 'frame_count' | 'file_format' | 'file_bytes' | 'reaction_count' | 'comment_count' | 'view_count' | 'hidden_by_user';
type SortOrder = 'asc' | 'desc';

const formatBytes = (bytes: number | null): string => {
  if (bytes === null) return '-';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

const formatDate = (dateStr: string): string => {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
};

export function PostTable({
  posts,
  selectedIds,
  setSelectedIds,
  currentPage,
  setCurrentPage,
  itemsPerPage,
  loading,
}: PostTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  // Sort posts
  const sortedPosts = useMemo(() => {
    const sorted = [...posts].sort((a, b) => {
      let aVal = a[sortKey];
      let bVal = b[sortKey];

      // Handle nulls
      if (aVal === null) aVal = '' as any;
      if (bVal === null) bVal = '' as any;

      // String comparison for text fields
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortOrder === 'asc'
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }

      // Numeric comparison
      const aNum = Number(aVal);
      const bNum = Number(bVal);
      return sortOrder === 'asc' ? aNum - bNum : bNum - aNum;
    });
    return sorted;
  }, [posts, sortKey, sortOrder]);

  // Paginate
  const totalPages = Math.ceil(sortedPosts.length / itemsPerPage);
  const startIndex = currentPage * itemsPerPage;
  const paginatedPosts = sortedPosts.slice(startIndex, startIndex + itemsPerPage);

  // Selection handlers
  const handleSelectAll = () => {
    const pageIds = paginatedPosts.map((p) => p.id);
    const allSelected = pageIds.every((id) => selectedIds.has(id));

    const newSelected = new Set(selectedIds);
    if (allSelected) {
      pageIds.forEach((id) => newSelected.delete(id));
    } else {
      pageIds.forEach((id) => newSelected.add(id));
    }
    setSelectedIds(newSelected);
  };

  const handleSelect = (id: number) => {
    const newSelected = new Set(selectedIds);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedIds(newSelected);
  };

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortOrder('desc');
    }
  };

  const allPageSelected = paginatedPosts.length > 0 && paginatedPosts.every((p) => selectedIds.has(p.id));

  return (
    <div className="post-table-container">
      <div className="table-header">
        <div className="th checkbox">
          <input
            type="checkbox"
            checked={allPageSelected}
            onChange={handleSelectAll}
            title="Select all on this page"
          />
        </div>
        <div className="th visibility" onClick={() => handleSort('hidden_by_user')}>
          Vis {sortKey === 'hidden_by_user' && (sortOrder === 'asc' ? '▲' : '▼')}
        </div>
        <div className="th thumb">Img</div>
        <div className="th title" onClick={() => handleSort('title')}>
          Title {sortKey === 'title' && (sortOrder === 'asc' ? '▲' : '▼')}
        </div>
        <div className="th date" onClick={() => handleSort('created_at')}>
          Date {sortKey === 'created_at' && (sortOrder === 'asc' ? '▲' : '▼')}
        </div>
        <div className="th frames" onClick={() => handleSort('frame_count')}>
          Frames {sortKey === 'frame_count' && (sortOrder === 'asc' ? '▲' : '▼')}
        </div>
        <div className="th format" onClick={() => handleSort('file_format')}>
          Fmt {sortKey === 'file_format' && (sortOrder === 'asc' ? '▲' : '▼')}
        </div>
        <div className="th size" onClick={() => handleSort('file_bytes')}>
          Size {sortKey === 'file_bytes' && (sortOrder === 'asc' ? '▲' : '▼')}
        </div>
        <div className="th dims" onClick={() => handleSort('width')}>
          W {sortKey === 'width' && (sortOrder === 'asc' ? '▲' : '▼')}
        </div>
        <div className="th dims" onClick={() => handleSort('height')}>
          H {sortKey === 'height' && (sortOrder === 'asc' ? '▲' : '▼')}
        </div>
        <div className="th reactions" onClick={() => handleSort('reaction_count')}>
          Reacts {sortKey === 'reaction_count' && (sortOrder === 'asc' ? '▲' : '▼')}
        </div>
        <div className="th comments" onClick={() => handleSort('comment_count')}>
          Cmts {sortKey === 'comment_count' && (sortOrder === 'asc' ? '▲' : '▼')}
        </div>
        <div className="th views" onClick={() => handleSort('view_count')}>
          Views {sortKey === 'view_count' && (sortOrder === 'asc' ? '▲' : '▼')}
        </div>
      </div>

      <div className="table-body">
        {paginatedPosts.map((post) => (
          <div
            key={post.id}
            className={`table-row ${post.hidden_by_user ? 'hidden-post' : ''} ${
              selectedIds.has(post.id) ? 'selected' : ''
            }`}
          >
            <div className="td checkbox">
              <input
                type="checkbox"
                checked={selectedIds.has(post.id)}
                onChange={() => handleSelect(post.id)}
              />
            </div>
            <div className="td visibility">
              {post.hidden_by_user ? '👁️‍🗨️' : '👁️'}
            </div>
            <div className="td thumb">
              <Image
                src={post.art_url}
                alt={post.title}
                width={40}
                height={40}
                className="thumbnail"
                unoptimized
              />
            </div>
            <div className="td title" title={post.title}>
              <a href={`/art/${post.public_sqid}`} target="_blank" rel="noopener noreferrer">
                {post.title || 'Untitled'}
              </a>
            </div>
            <div className="td date">{formatDate(post.created_at)}</div>
            <div className="td frames">{post.frame_count}</div>
            <div className="td format">{post.file_format?.toUpperCase() || '-'}</div>
            <div className="td size">{formatBytes(post.file_bytes)}</div>
            <div className="td dims">{post.width}</div>
            <div className="td dims">{post.height}</div>
            <div className="td reactions">{post.reaction_count}</div>
            <div className="td comments">{post.comment_count}</div>
            <div className="td views">{post.view_count}</div>
          </div>
        ))}

        {loading && (
          <div className="loading-row">
            <div className="loading-spinner"></div>
            Loading more posts...
          </div>
        )}

        {!loading && paginatedPosts.length === 0 && (
          <div className="empty-row">No posts found</div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="pagination">
          <button
            onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
            disabled={currentPage === 0}
            className="page-btn"
          >
            Previous
          </button>
          <span className="page-info">
            Page {currentPage + 1} of {totalPages}
          </span>
          <button
            onClick={() => setCurrentPage(Math.min(totalPages - 1, currentPage + 1))}
            disabled={currentPage >= totalPages - 1}
            className="page-btn"
          >
            Next
          </button>
        </div>
      )}

      <style jsx>{`
        .post-table-container {
          width: 100%;
          overflow-x: auto;
        }

        .table-header {
          display: flex;
          background: var(--bg-tertiary);
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
          padding: 12px 8px;
          font-size: 0.75rem;
          font-weight: 600;
          color: var(--text-secondary);
          text-transform: uppercase;
          position: sticky;
          top: 0;
          z-index: 10;
        }

        .th {
          cursor: pointer;
          user-select: none;
          padding: 0 4px;
          white-space: nowrap;
        }

        .th:hover {
          color: var(--accent-cyan);
        }

        .th.checkbox,
        .th.thumb {
          cursor: default;
        }

        .th.checkbox { width: 40px; flex-shrink: 0; }
        .th.visibility { width: 50px; flex-shrink: 0; }
        .th.thumb { width: 48px; flex-shrink: 0; }
        .th.title { flex: 1; min-width: 150px; }
        .th.date { width: 100px; flex-shrink: 0; }
        .th.frames { width: 60px; flex-shrink: 0; }
        .th.format { width: 60px; flex-shrink: 0; }
        .th.size { width: 80px; flex-shrink: 0; }
        .th.dims { width: 50px; flex-shrink: 0; }
        .th.reactions { width: 60px; flex-shrink: 0; }
        .th.comments { width: 60px; flex-shrink: 0; }
        .th.views { width: 60px; flex-shrink: 0; }

        .table-body {
          max-height: 600px;
          overflow-y: auto;
        }

        .table-row {
          display: flex;
          align-items: center;
          padding: 8px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
          font-size: 0.85rem;
          transition: background 0.15s ease;
        }

        .table-row:hover {
          background: var(--bg-tertiary);
        }

        .table-row.selected {
          background: rgba(0, 212, 255, 0.1);
        }

        .table-row.hidden-post {
          opacity: 0.5;
          background: rgba(255, 255, 255, 0.02);
        }

        .td {
          padding: 0 4px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .td.checkbox { width: 40px; flex-shrink: 0; }
        .td.visibility { width: 50px; flex-shrink: 0; }
        .td.thumb { width: 48px; flex-shrink: 0; }
        .td.title { flex: 1; min-width: 150px; }
        .td.date { width: 100px; flex-shrink: 0; color: var(--text-secondary); }
        .td.frames { width: 60px; flex-shrink: 0; }
        .td.format { width: 60px; flex-shrink: 0; }
        .td.size { width: 80px; flex-shrink: 0; }
        .td.dims { width: 50px; flex-shrink: 0; }
        .td.reactions { width: 60px; flex-shrink: 0; }
        .td.comments { width: 60px; flex-shrink: 0; }
        .td.views { width: 60px; flex-shrink: 0; }

        .td.title a {
          color: var(--text-primary);
          text-decoration: none;
        }

        .td.title a:hover {
          color: var(--accent-cyan);
        }

        .thumbnail {
          border-radius: 4px;
          image-rendering: pixelated;
          object-fit: contain;
        }

        input[type="checkbox"] {
          width: 16px;
          height: 16px;
          cursor: pointer;
          accent-color: var(--accent-cyan);
        }

        .loading-row,
        .empty-row {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 24px;
          color: var(--text-secondary);
          gap: 8px;
        }

        .loading-spinner {
          width: 20px;
          height: 20px;
          border: 2px solid var(--bg-tertiary);
          border-top-color: var(--accent-cyan);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .pagination {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 16px;
          padding: 16px;
          border-top: 1px solid rgba(255, 255, 255, 0.1);
        }

        .page-btn {
          background: var(--bg-tertiary);
          border: 1px solid rgba(255, 255, 255, 0.1);
          color: var(--text-primary);
          padding: 8px 16px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 0.85rem;
          transition: all 0.15s ease;
        }

        .page-btn:hover:not(:disabled) {
          border-color: var(--accent-cyan);
          color: var(--accent-cyan);
        }

        .page-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .page-info {
          color: var(--text-secondary);
          font-size: 0.85rem;
        }
      `}</style>
    </div>
  );
}
