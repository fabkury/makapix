import { useState, useMemo, useRef, useEffect } from 'react';
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
  files: Array<{ format: string; file_bytes: number; is_native: boolean }>;
  art_url: string;
  hidden_by_user: boolean;
  reaction_count: number;
  comment_count: number;
  view_count: number;
  license_identifier: string | null;
}

interface PostTableProps {
  posts: PMDPost[];
  selectedIds: Set<number>;
  setSelectedIds: (ids: Set<number>) => void;
  currentPage: number;
  setCurrentPage: (page: number) => void;
  itemsPerPage: number;
  loading: boolean;
  onToggleHide: (id: number) => void;
  onDelete: (id: number) => void;
}

type SortKey =
  | 'title'
  | 'description'
  | 'created_at'
  | 'license_identifier'
  | 'width'
  | 'height'
  | 'frame_count'
  | 'file_format'
  | 'file_bytes'
  | 'reaction_count'
  | 'comment_count'
  | 'view_count'
  | 'hidden_by_user';
type SortOrder = 'asc' | 'desc';

// Format file size in binary prefixes (KiB, MiB)
const formatFileSize = (bytes: number | null): string => {
  if (bytes === null || bytes === undefined) return '-';
  const kib = 1024;
  const mib = kib * 1024;
  if (bytes >= mib) {
    return `${Math.round((bytes / mib) * 10) / 10} MiB`;
  } else if (bytes >= kib) {
    return `${Math.round(bytes / kib)} KiB`;
  }
  return `${bytes} B`;
};

// Format numbers with metric prefixes
const formatMetricNumber = (num: number): string => {
  if (num < 1000) return num.toString();
  const units = [
    { value: 1e12, symbol: 'T' },
    { value: 1e9, symbol: 'B' },
    { value: 1e6, symbol: 'M' },
    { value: 1e3, symbol: 'K' },
  ];
  for (const unit of units) {
    if (num >= unit.value) {
      const scaled = num / unit.value;
      return parseFloat(scaled.toPrecision(3)) + unit.symbol;
    }
  }
  return num.toString();
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
  onToggleHide,
  onDelete,
}: PostTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [goToPageInput, setGoToPageInput] = useState('');
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null);

  // Column widths state for resizing
  const [columnWidths, setColumnWidths] = useState({
    checkbox: 40,
    visibility: 50,
    thumbnail: 48,
    title: 200,
    description: 250,
    date: 110,
    license: 70,
    frames: 50,
    format: 60,
    size: 80,
    width: 50,
    height: 50,
    reactions: 50,
    comments: 50,
    views: 50,
    delete: 50,
  });

  // Resize handling
  const resizingColumn = useRef<string | null>(null);
  const startX = useRef(0);
  const startWidth = useRef(0);

  const handleResizeMouseDown = (e: React.MouseEvent, columnKey: string) => {
    resizingColumn.current = columnKey;
    startX.current = e.clientX;
    startWidth.current = columnWidths[columnKey as keyof typeof columnWidths];
    e.preventDefault();
    e.stopPropagation();
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!resizingColumn.current) return;
      const diff = e.clientX - startX.current;
      const newWidth = Math.max(40, startWidth.current + diff);
      setColumnWidths((prev) => ({
        ...prev,
        [resizingColumn.current!]: newWidth,
      }));
    };

    const handleMouseUp = () => {
      resizingColumn.current = null;
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  // Sort posts
  const getNativeFile = (post: PMDPost) => post.files?.find(f => f.is_native) || post.files?.[0];

  const sortedPosts = useMemo(() => {
    const sorted = [...posts].sort((a, b) => {
      let aVal: any;
      let bVal: any;

      // Derived fields from files array
      if (sortKey === 'file_format') {
        aVal = getNativeFile(a)?.format || '';
        bVal = getNativeFile(b)?.format || '';
      } else if (sortKey === 'file_bytes') {
        aVal = getNativeFile(a)?.file_bytes || 0;
        bVal = getNativeFile(b)?.file_bytes || 0;
      } else {
        aVal = (a as any)[sortKey];
        bVal = (b as any)[sortKey];
      }

      if (aVal === null) aVal = '';
      if (bVal === null) bVal = '';

      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortOrder === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }

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
  const handleSelectOne = (id: number, checked: boolean) => {
    const newSet = new Set(selectedIds);
    if (checked) {
      newSet.add(id);
    } else {
      newSet.delete(id);
    }
    setSelectedIds(newSet);
  };

  const handleSelectAllCurrentPage = () => {
    const newSet = new Set(selectedIds);
    paginatedPosts.forEach((p) => newSet.add(p.id));
    setSelectedIds(newSet);
  };

  const handleUnselectAllCurrentPage = () => {
    const newSet = new Set(selectedIds);
    paginatedPosts.forEach((p) => newSet.delete(p.id));
    setSelectedIds(newSet);
  };

  const handleSelectAllPages = () => {
    setSelectedIds(new Set(posts.map((p) => p.id)));
  };

  const handleUnselectAllPages = () => {
    setSelectedIds(new Set());
  };

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortOrder('desc');
    }
  };

  const handleGoToPage = () => {
    const pageNum = parseInt(goToPageInput);
    if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= totalPages) {
      setCurrentPage(pageNum - 1);
      setGoToPageInput('');
    }
  };

  const handleDeleteClick = (id: number) => {
    setDeleteConfirmId(id);
  };

  const handleDeleteConfirm = () => {
    if (deleteConfirmId !== null) {
      onDelete(deleteConfirmId);
      setDeleteConfirmId(null);
    }
  };

  const allPageSelected =
    paginatedPosts.length > 0 && paginatedPosts.every((p) => selectedIds.has(p.id));
  const somePageSelected =
    paginatedPosts.some((p) => selectedIds.has(p.id)) && !allPageSelected;

  const SortIndicator = ({ column }: { column: SortKey }) =>
    sortKey === column ? (
      <span className="sort-indicator">{sortOrder === 'asc' ? '▲' : '▼'}</span>
    ) : null;

  const totalWidth = Object.values(columnWidths).reduce((a, b) => a + b, 0);

  return (
    <div className="post-table-container">
      {/* Selection Controls */}
      <div className="selection-controls">
        <div className="badge-group">
          <button className="badge" onClick={handleSelectAllCurrentPage}>
            Select all
          </button>
          <button className="badge" onClick={handleUnselectAllCurrentPage}>
            Unselect all
          </button>
          <button className="badge" onClick={handleSelectAllPages}>
            Select all (all pages)
          </button>
          <button className="badge" onClick={handleUnselectAllPages}>
            Unselect all (all pages)
          </button>
        </div>
        <div className="goto-controls">
          <input
            type="number"
            min="1"
            max={totalPages}
            value={goToPageInput}
            onChange={(e) => setGoToPageInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleGoToPage();
            }}
            placeholder="Page #"
            className="goto-input"
          />
          <button className="goto-btn" onClick={handleGoToPage} disabled={!goToPageInput}>
            Go to page
          </button>
        </div>
      </div>

      {/* Table wrapper for synchronized scrolling */}
      <div className="table-wrapper">
        <table style={{ minWidth: `${totalWidth}px` }}>
          <thead>
            <tr>
              {/* Checkbox */}
              <th style={{ width: `${columnWidths.checkbox}px` }}>
                <input
                  type="checkbox"
                  checked={allPageSelected}
                  ref={(el) => {
                    if (el) el.indeterminate = somePageSelected;
                  }}
                  onChange={(e) => {
                    if (e.target.checked) {
                      handleSelectAllCurrentPage();
                    } else {
                      handleUnselectAllCurrentPage();
                    }
                  }}
                  title="Select all on this page"
                />
                <div
                  className="resize-handle"
                  onMouseDown={(e) => handleResizeMouseDown(e, 'checkbox')}
                />
              </th>
              {/* Visibility */}
              <th
                style={{ width: `${columnWidths.visibility}px` }}
                onClick={() => handleSort('hidden_by_user')}
                className="sortable"
              >
                👁️
                <SortIndicator column="hidden_by_user" />
                <div
                  className="resize-handle"
                  onMouseDown={(e) => handleResizeMouseDown(e, 'visibility')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              {/* Thumbnail */}
              <th style={{ width: `${columnWidths.thumbnail}px` }}>
                <div
                  className="resize-handle"
                  onMouseDown={(e) => handleResizeMouseDown(e, 'thumbnail')}
                />
              </th>
              {/* Title */}
              <th
                style={{ width: `${columnWidths.title}px` }}
                onClick={() => handleSort('title')}
                className="sortable text-left"
              >
                Title
                <SortIndicator column="title" />
                <div
                  className="resize-handle"
                  onMouseDown={(e) => handleResizeMouseDown(e, 'title')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              {/* Description */}
              <th
                style={{ width: `${columnWidths.description}px` }}
                onClick={() => handleSort('description')}
                className="sortable text-left"
              >
                Description
                <SortIndicator column="description" />
                <div
                  className="resize-handle"
                  onMouseDown={(e) => handleResizeMouseDown(e, 'description')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              {/* Date */}
              <th
                style={{ width: `${columnWidths.date}px` }}
                onClick={() => handleSort('created_at')}
                className="sortable"
              >
                Date
                <SortIndicator column="created_at" />
                <div
                  className="resize-handle"
                  onMouseDown={(e) => handleResizeMouseDown(e, 'date')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              {/* License */}
              <th
                style={{ width: `${columnWidths.license}px` }}
                onClick={() => handleSort('license_identifier')}
                className="sortable"
                title="License"
              >
                License
                <SortIndicator column="license_identifier" />
                <div
                  className="resize-handle"
                  onMouseDown={(e) => handleResizeMouseDown(e, 'license')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              {/* Frames */}
              <th
                style={{ width: `${columnWidths.frames}px` }}
                onClick={() => handleSort('frame_count')}
                className="sortable"
                title="Frames"
              >
                🖼️
                <SortIndicator column="frame_count" />
                <div
                  className="resize-handle"
                  onMouseDown={(e) => handleResizeMouseDown(e, 'frames')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              {/* Format */}
              <th
                style={{ width: `${columnWidths.format}px` }}
                onClick={() => handleSort('file_format')}
                className="sortable"
                title="Format"
              >
                📄
                <SortIndicator column="file_format" />
                <div
                  className="resize-handle"
                  onMouseDown={(e) => handleResizeMouseDown(e, 'format')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              {/* Size */}
              <th
                style={{ width: `${columnWidths.size}px` }}
                onClick={() => handleSort('file_bytes')}
                className="sortable"
                title="File size"
              >
                💾
                <SortIndicator column="file_bytes" />
                <div
                  className="resize-handle"
                  onMouseDown={(e) => handleResizeMouseDown(e, 'size')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              {/* Width */}
              <th
                style={{ width: `${columnWidths.width}px` }}
                onClick={() => handleSort('width')}
                className="sortable"
                title="Width"
              >
                ↔️
                <SortIndicator column="width" />
                <div
                  className="resize-handle"
                  onMouseDown={(e) => handleResizeMouseDown(e, 'width')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              {/* Height */}
              <th
                style={{ width: `${columnWidths.height}px` }}
                onClick={() => handleSort('height')}
                className="sortable"
                title="Height"
              >
                ↕️
                <SortIndicator column="height" />
                <div
                  className="resize-handle"
                  onMouseDown={(e) => handleResizeMouseDown(e, 'height')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              {/* Reactions */}
              <th
                style={{ width: `${columnWidths.reactions}px` }}
                onClick={() => handleSort('reaction_count')}
                className="sortable"
                title="Reactions"
              >
                ⚡
                <SortIndicator column="reaction_count" />
                <div
                  className="resize-handle"
                  onMouseDown={(e) => handleResizeMouseDown(e, 'reactions')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              {/* Comments */}
              <th
                style={{ width: `${columnWidths.comments}px` }}
                onClick={() => handleSort('comment_count')}
                className="sortable"
                title="Comments"
              >
                💬
                <SortIndicator column="comment_count" />
                <div
                  className="resize-handle"
                  onMouseDown={(e) => handleResizeMouseDown(e, 'comments')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              {/* Views */}
              <th
                style={{ width: `${columnWidths.views}px` }}
                onClick={() => handleSort('view_count')}
                className="sortable"
                title="Views"
              >
                👁️
                <SortIndicator column="view_count" />
                <div
                  className="resize-handle"
                  onMouseDown={(e) => handleResizeMouseDown(e, 'views')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              {/* Delete */}
              <th style={{ width: `${columnWidths.delete}px` }} title="Delete">
                🗑️
              </th>
            </tr>
          </thead>
          <tbody>
            {paginatedPosts.map((post) => (
              <tr key={post.id} className={`${post.hidden_by_user ? 'hidden-post' : ''} ${selectedIds.has(post.id) ? 'selected' : ''}`}>
                {/* Checkbox */}
                <td style={{ width: `${columnWidths.checkbox}px` }}>
                  <input
                    type="checkbox"
                    checked={selectedIds.has(post.id)}
                    onChange={(e) => handleSelectOne(post.id, e.target.checked)}
                  />
                </td>
                {/* Visibility toggle */}
                <td style={{ width: `${columnWidths.visibility}px` }}>
                  <button
                    className="icon-btn"
                    onClick={() => onToggleHide(post.id)}
                    title={post.hidden_by_user ? 'Unhide post' : 'Hide post'}
                  >
                    {post.hidden_by_user ? '🙈' : '👁️'}
                  </button>
                </td>
                {/* Thumbnail */}
                <td style={{ width: `${columnWidths.thumbnail}px` }}>
                  <Image
                    src={post.art_url}
                    alt={post.title}
                    width={32}
                    height={32}
                    className="thumbnail"
                    unoptimized
                  />
                </td>
                {/* Title */}
                <td style={{ width: `${columnWidths.title}px` }} className="text-left" title={post.title}>
                  <a href={`/p/${post.public_sqid}`} target="_blank" rel="noopener noreferrer">
                    {post.title || 'Untitled'}
                  </a>
                </td>
                {/* Description */}
                <td
                  style={{ width: `${columnWidths.description}px` }}
                  className="text-left description-cell"
                  title={post.description || ''}
                >
                  {post.description || ''}
                </td>
                {/* Date */}
                <td style={{ width: `${columnWidths.date}px` }}>{formatDate(post.created_at)}</td>
                {/* License */}
                <td style={{ width: `${columnWidths.license}px` }} title={post.license_identifier || 'All rights reserved'}>
                  {post.license_identifier || 'ARR'}
                </td>
                {/* Frames */}
                <td style={{ width: `${columnWidths.frames}px` }}>{post.frame_count}</td>
                {/* Format */}
                <td style={{ width: `${columnWidths.format}px` }}>
                  {getNativeFile(post)?.format?.toUpperCase() || '-'}
                </td>
                {/* Size */}
                <td style={{ width: `${columnWidths.size}px` }}>{formatFileSize(getNativeFile(post)?.file_bytes ?? null)}</td>
                {/* Width */}
                <td style={{ width: `${columnWidths.width}px` }}>{post.width}</td>
                {/* Height */}
                <td style={{ width: `${columnWidths.height}px` }}>{post.height}</td>
                {/* Reactions */}
                <td style={{ width: `${columnWidths.reactions}px` }}>
                  {formatMetricNumber(post.reaction_count)}
                </td>
                {/* Comments */}
                <td style={{ width: `${columnWidths.comments}px` }}>
                  {formatMetricNumber(post.comment_count)}
                </td>
                {/* Views */}
                <td style={{ width: `${columnWidths.views}px` }}>
                  {formatMetricNumber(post.view_count)}
                </td>
                {/* Delete */}
                <td style={{ width: `${columnWidths.delete}px` }}>
                  <button
                    className="icon-btn delete-btn"
                    onClick={() => handleDeleteClick(post.id)}
                    title="Delete post"
                  >
                    🗑️
                  </button>
                </td>
              </tr>
            ))}
            {loading && (
              <tr className="loading-row">
                <td colSpan={16}>
                  <div className="loading-content">
                    <div className="loading-spinner"></div>
                    Loading more posts...
                  </div>
                </td>
              </tr>
            )}
            {!loading && paginatedPosts.length === 0 && (
              <tr className="empty-row">
                <td colSpan={16}>No posts found</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="pagination">
        <div className="pagination-info">
          Showing {startIndex + 1} to {Math.min(startIndex + itemsPerPage, sortedPosts.length)} of{' '}
          {sortedPosts.length} posts
        </div>
        <div className="pagination-controls">
          <button
            onClick={() => setCurrentPage(Math.max(0, currentPage - 1))}
            disabled={currentPage === 0}
            className="page-btn"
          >
            ← Previous
          </button>
          <span className="page-info">
            Page {currentPage + 1} of {totalPages || 1}
          </span>
          <button
            onClick={() => setCurrentPage(Math.min(totalPages - 1, currentPage + 1))}
            disabled={currentPage >= totalPages - 1}
            className="page-btn"
          >
            Next →
          </button>
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      {deleteConfirmId !== null && (
        <div className="dialog-overlay" onClick={() => setDeleteConfirmId(null)}>
          <div className="dialog" onClick={(e) => e.stopPropagation()}>
            <h3>Delete Post</h3>
            <p>
              Are you sure you want to delete this post? It will be permanently removed after 7 days.
            </p>
            <div className="dialog-buttons">
              <button className="dialog-btn cancel" onClick={() => setDeleteConfirmId(null)}>
                Cancel
              </button>
              <button className="dialog-btn confirm" onClick={handleDeleteConfirm}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .post-table-container {
          width: 100%;
        }

        .selection-controls {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding: 12px 16px;
          background: var(--bg-tertiary);
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .badge-group {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }

        .badge {
          display: inline-flex;
          align-items: center;
          padding: 6px 12px;
          border-radius: 16px;
          font-size: 0.8rem;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.15s ease;
          background: var(--bg-secondary);
          color: var(--text-secondary);
          border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .badge:hover {
          background: var(--bg-primary);
          color: var(--text-primary);
          border-color: var(--accent-cyan);
        }

        .goto-controls {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .goto-input {
          width: 80px;
          padding: 6px 10px;
          border-radius: 4px;
          border: 1px solid rgba(255, 255, 255, 0.1);
          background: var(--bg-secondary);
          color: var(--text-primary);
          font-size: 0.85rem;
        }

        .goto-input::placeholder {
          color: var(--text-muted);
        }

        .goto-btn {
          padding: 6px 12px;
          border-radius: 4px;
          border: 1px solid rgba(255, 255, 255, 0.1);
          background: var(--bg-secondary);
          color: var(--text-primary);
          font-size: 0.85rem;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .goto-btn:hover:not(:disabled) {
          border-color: var(--accent-cyan);
          color: var(--accent-cyan);
        }

        .goto-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .table-wrapper {
          overflow-x: auto;
          overflow-y: hidden;
        }

        table {
          width: 100%;
          border-collapse: collapse;
          table-layout: fixed;
        }

        thead {
          display: table;
          width: 100%;
          table-layout: fixed;
          background: var(--bg-tertiary);
        }

        th {
          position: relative;
          padding: 10px 8px;
          font-size: 0.75rem;
          font-weight: 600;
          color: var(--text-secondary);
          text-align: center;
          white-space: nowrap;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
          user-select: none;
        }

        th.sortable {
          cursor: pointer;
        }

        th.sortable:hover {
          color: var(--accent-cyan);
          background: var(--bg-secondary);
        }

        th.text-left {
          text-align: left;
        }

        .sort-indicator {
          margin-left: 4px;
          font-size: 0.65rem;
        }

        .resize-handle {
          position: absolute;
          right: 0;
          top: 0;
          bottom: 0;
          width: 4px;
          background: rgba(255, 255, 255, 0.1);
          cursor: col-resize;
          opacity: 0;
          transition: opacity 0.15s ease;
        }

        th:hover .resize-handle {
          opacity: 1;
        }

        .resize-handle:hover {
          background: var(--accent-cyan);
        }

        td {
          padding: 0 8px;
          height: 34px;
          font-size: 0.85rem;
          color: var(--text-primary);
          text-align: center;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          border-bottom: none;
          vertical-align: middle;
        }

        td.text-left {
          text-align: left;
        }

        td.description-cell {
          color: var(--text-secondary);
        }

        tbody {
          display: block;
          height: 576px; /* 16 rows * 34px + 32px buffer */
          overflow: hidden;
        }

        thead tr {
          display: table;
          width: 100%;
          table-layout: fixed;
        }

        tbody tr {
          display: table;
          width: 100%;
          table-layout: fixed;
          height: 34px;
          transition: background 0.15s ease;
        }

        tbody tr:hover {
          background: var(--bg-tertiary);
        }

        tr.selected {
          background: rgba(0, 212, 255, 0.1);
        }

        tr.hidden-post {
          opacity: 0.5;
          background: rgba(255, 255, 255, 0.02);
        }

        td a {
          color: var(--text-primary);
          text-decoration: none;
        }

        td a:hover {
          color: var(--accent-cyan);
        }

        .thumbnail {
          border-radius: 4px;
          image-rendering: pixelated;
          object-fit: contain;
        }

        input[type='checkbox'] {
          width: 16px;
          height: 16px;
          cursor: pointer;
          accent-color: var(--accent-cyan);
        }

        .icon-btn {
          background: transparent;
          border: none;
          cursor: pointer;
          font-size: 1rem;
          padding: 4px;
          border-radius: 4px;
          transition: background 0.15s ease;
        }

        .icon-btn:hover {
          background: rgba(255, 255, 255, 0.1);
        }

        .delete-btn:hover {
          background: rgba(239, 68, 68, 0.2);
        }

        .loading-row td,
        .empty-row td {
          padding: 24px;
          text-align: center;
          color: var(--text-secondary);
        }

        .loading-content {
          display: flex;
          align-items: center;
          justify-content: center;
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
          to {
            transform: rotate(360deg);
          }
        }

        .pagination {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          padding: 16px;
          border-top: 1px solid rgba(255, 255, 255, 0.1);
        }

        .pagination-info {
          font-size: 0.85rem;
          color: var(--text-secondary);
        }

        .pagination-controls {
          display: flex;
          align-items: center;
          gap: 12px;
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

        /* Delete Confirmation Dialog */
        .dialog-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.7);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }

        .dialog {
          background: var(--bg-secondary);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          padding: 24px;
          max-width: 400px;
          width: 90%;
        }

        .dialog h3 {
          margin: 0 0 12px;
          color: var(--text-primary);
          font-size: 1.1rem;
        }

        .dialog p {
          margin: 0 0 20px;
          color: var(--text-secondary);
          font-size: 0.9rem;
          line-height: 1.5;
        }

        .dialog-buttons {
          display: flex;
          gap: 12px;
          justify-content: flex-end;
        }

        .dialog-btn {
          padding: 10px 20px;
          border-radius: 6px;
          font-size: 0.85rem;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .dialog-btn.cancel {
          background: var(--bg-tertiary);
          border: 1px solid rgba(255, 255, 255, 0.1);
          color: var(--text-primary);
        }

        .dialog-btn.cancel:hover {
          border-color: var(--accent-cyan);
        }

        .dialog-btn.confirm {
          background: #ef4444;
          border: none;
          color: white;
        }

        .dialog-btn.confirm:hover {
          background: #dc2626;
        }

        @media (max-width: 768px) {
          .selection-controls {
            flex-direction: column;
            align-items: flex-start;
          }

          .goto-controls {
            width: 100%;
          }

          .pagination {
            flex-direction: column;
            gap: 12px;
          }
        }
      `}</style>
    </div>
  );
}
