import { Checkbox } from './ui/checkbox';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import { Eye, EyeOff, Trash2, ChevronLeft, ChevronRight, ChevronUp, ChevronDown } from 'lucide-react';
import { ImageWithFallback } from './figma/ImageWithFallback';
import { useState, useRef, useEffect } from 'react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from './ui/alert-dialog';

// Format numbers with metric prefixes (K, M, B, T) up to 4 significant digits
function formatMetricNumber(num: number): string {
  // Handle undefined, null, or invalid numbers
  if (num == null || typeof num !== 'number' || isNaN(num)) {
    return '0';
  }
  
  if (num < 1000) {
    return num.toString();
  }
  
  const units = [
    { value: 1e12, symbol: 'T' },
    { value: 1e9, symbol: 'B' },
    { value: 1e6, symbol: 'M' },
    { value: 1e3, symbol: 'K' },
  ];
  
  for (const unit of units) {
    if (num >= unit.value) {
      const scaled = num / unit.value;
      // Use toPrecision for up to 4 significant digits, then clean up
      const formatted = parseFloat(scaled.toPrecision(4));
      return formatted + unit.symbol;
    }
  }
  
  return num.toString();
}

// Format file size in binary prefixes (KiB, MiB)
function formatFileSize(bytes: number): string {
  if (bytes == null || typeof bytes !== 'number' || isNaN(bytes)) {
    return '0 B';
  }
  
  const kib = 1024;
  const mib = kib * 1024;
  
  if (bytes >= mib) {
    const size = bytes / mib;
    return `${Math.round(size * 10) / 10} MiB`;
  } else if (bytes >= kib) {
    const size = bytes / kib;
    return `${Math.round(size)} KiB`;
  } else {
    return `${bytes} B`;
  }
}

interface Artwork {
  id: string;
  imageUrl: string;
  title: string;
  description: string;
  uploadDate: string;
  reactions: number;
  comments: number;
  views: number;
  isHidden: boolean;
  frameCount: number;
  fileFormat: string;
  fileSize: number;
  width: number;
  height: number;
}

interface ArtworkTableProps {
  artworks: Artwork[];
  selectedIds: Set<string>;
  setSelectedIds: (ids: Set<string>) => void;
  currentPage: number;
  setCurrentPage: (page: number) => void;
  itemsPerPage: number;
  totalPages: number;
  onToggleHide: (id: string) => void;
  onDelete: (id: string) => void;
}

export function ArtworkTable({
  artworks,
  selectedIds,
  setSelectedIds,
  currentPage,
  setCurrentPage,
  itemsPerPage,
  totalPages,
  onToggleHide,
  onDelete,
}: ArtworkTableProps) {
  // Sorting state
  const [sortColumn, setSortColumn] = useState<keyof Artwork | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');

  // Handle sort
  const handleSort = (column: keyof Artwork) => {
    if (sortColumn === column) {
      // Toggle direction if clicking same column
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      // Set new column and default to ascending
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  // Sort artworks
  const sortedArtworks = [...artworks].sort((a, b) => {
    if (!sortColumn) return 0;

    const aVal = a[sortColumn];
    const bVal = b[sortColumn];

    // Handle different data types
    let comparison = 0;
    
    if (typeof aVal === 'string' && typeof bVal === 'string') {
      comparison = aVal.localeCompare(bVal);
    } else if (typeof aVal === 'number' && typeof bVal === 'number') {
      comparison = aVal - bVal;
    } else if (typeof aVal === 'boolean' && typeof bVal === 'boolean') {
      comparison = (aVal === bVal) ? 0 : aVal ? 1 : -1;
    } else {
      comparison = String(aVal).localeCompare(String(bVal));
    }

    return sortDirection === 'asc' ? comparison : -comparison;
  });

  const startIndex = currentPage * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentArtworks = sortedArtworks.slice(startIndex, endIndex);

  // Column widths state
  const [columnWidths, setColumnWidths] = useState({
    checkbox: 48,
    visibility: 60,
    thumbnail: 48,
    title: 300,
    description: 400,
    uploadDate: 140,
    frameCount: 60,
    fileFormat: 70,
    fileSize: 90,
    width: 70,
    height: 70,
    reactions: 60,
    comments: 60,
    views: 60,
    delete: 60,
  });

  const resizingColumn = useRef<string | null>(null);
  const startX = useRef(0);
  const startWidth = useRef(0);

  const handleMouseDown = (e: React.MouseEvent, columnKey: string) => {
    resizingColumn.current = columnKey;
    startX.current = e.clientX;
    startWidth.current = columnWidths[columnKey as keyof typeof columnWidths];
    e.preventDefault();
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!resizingColumn.current) return;
      const diff = e.clientX - startX.current;
      const newWidth = Math.max(60, startWidth.current + diff);
      setColumnWidths(prev => ({
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

  const handleSelectOne = (id: string, checked: boolean) => {
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
    currentArtworks.forEach(a => newSet.add(a.id));
    setSelectedIds(newSet);
  };

  const handleUnselectAllCurrentPage = () => {
    const newSet = new Set(selectedIds);
    currentArtworks.forEach(a => newSet.delete(a.id));
    setSelectedIds(newSet);
  };

  const handleSelectAllPages = () => {
    setSelectedIds(new Set(artworks.map(a => a.id)));
  };

  const handleUnselectAllPages = () => {
    setSelectedIds(new Set());
  };

  const [goToPageInput, setGoToPageInput] = useState('');

  const handleGoToPage = () => {
    const pageNum = parseInt(goToPageInput);
    if (!isNaN(pageNum) && pageNum >= 1 && pageNum <= totalPages) {
      setCurrentPage(pageNum - 1);
      setGoToPageInput('');
    }
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(artworks.map(a => a.id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  const allSelected = artworks.length > 0 && artworks.every(a => selectedIds.has(a.id));
  const someSelected = artworks.some(a => selectedIds.has(a.id)) && !allSelected;

  return (
    <div>
      {/* Selection Controls */}
      <div className="px-4 py-3 border-b bg-gray-50 flex flex-wrap items-center gap-2">
        <Badge 
          variant="outline" 
          className="cursor-pointer hover:bg-gray-100"
          onClick={handleSelectAllCurrentPage}
        >
          Select all
        </Badge>
        <Badge 
          variant="outline" 
          className="cursor-pointer hover:bg-gray-100"
          onClick={handleUnselectAllCurrentPage}
        >
          Unselect all
        </Badge>
        <Badge 
          variant="outline" 
          className="cursor-pointer hover:bg-gray-100"
          onClick={handleSelectAllPages}
        >
          Select all (all pages)
        </Badge>
        <Badge 
          variant="outline" 
          className="cursor-pointer hover:bg-gray-100"
          onClick={handleUnselectAllPages}
        >
          Unselect all (all pages)
        </Badge>
        
        {/* Page navigation controls */}
        <div className="flex items-center gap-2 ml-auto">
          <Input
            type="number"
            min="1"
            max={totalPages}
            value={goToPageInput}
            onChange={(e) => setGoToPageInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleGoToPage();
              }
            }}
            placeholder="Page #"
            className="w-24 h-8 text-sm"
          />
          <Button
            variant="outline"
            size="sm"
            onClick={handleGoToPage}
            disabled={!goToPageInput}
          >
            Go to page
          </Button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse" style={{ tableLayout: 'fixed' }}>
          <thead>
            <tr className="border-b bg-gray-50" style={{ height: '40px' }}>
              {/* Checkbox */}
              <th className="px-4 relative" style={{ width: `${columnWidths.checkbox}px` }}>
                <Checkbox
                  checked={allSelected}
                  onCheckedChange={handleSelectAll}
                  aria-label="Select all artworks"
                  className={someSelected ? "data-[state=checked]:bg-gray-400" : ""}
                />
                <div
                  className="absolute right-0 top-0 bottom-0 w-1 bg-gray-300 hover:bg-blue-500 cursor-col-resize"
                  onMouseDown={(e) => handleMouseDown(e, 'checkbox')}
                />
              </th>
              
              {/* Hide/Unhide */}
              <th className="px-2 text-center relative cursor-pointer hover:bg-gray-100" style={{ width: `${columnWidths.visibility}px` }} onClick={() => handleSort('isHidden')}>
                <Eye className="h-4 w-4 mx-auto text-gray-500" />
                <div
                  className="absolute right-0 top-0 bottom-0 w-1 bg-gray-300 hover:bg-blue-500 cursor-col-resize"
                  onMouseDown={(e) => handleMouseDown(e, 'visibility')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              
              {/* Thumbnail */}
              <th className="px-2 relative" style={{ width: `${columnWidths.thumbnail}px` }}>
                <div
                  className="absolute right-0 top-0 bottom-0 w-1 bg-gray-300 hover:bg-blue-500 cursor-col-resize"
                  onMouseDown={(e) => handleMouseDown(e, 'thumbnail')}
                />
              </th>
              
              {/* Title */}
              <th className="text-left px-4 relative cursor-pointer hover:bg-gray-100" style={{ width: `${columnWidths.title}px` }} onClick={() => handleSort('title')}>
                <div className="flex items-center gap-1">
                  Title
                  {sortColumn === 'title' && (
                    sortDirection === 'asc' ? (
                      <ChevronUp className="h-3 w-3" />
                    ) : (
                      <ChevronDown className="h-3 w-3" />
                    )
                  )}
                </div>
                <div
                  className="absolute right-0 top-0 bottom-0 w-1 bg-gray-300 hover:bg-blue-500 cursor-col-resize"
                  onMouseDown={(e) => handleMouseDown(e, 'title')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              
              {/* Description */}
              <th className="text-left px-4 relative cursor-pointer hover:bg-gray-100" style={{ width: `${columnWidths.description}px` }} onClick={() => handleSort('description')}>
                <div className="flex items-center gap-1">
                  Description
                  {sortColumn === 'description' && (
                    sortDirection === 'asc' ? (
                      <ChevronUp className="h-3 w-3" />
                    ) : (
                      <ChevronDown className="h-3 w-3" />
                    )
                  )}
                </div>
                <div
                  className="absolute right-0 top-0 bottom-0 w-1 bg-gray-300 hover:bg-blue-500 cursor-col-resize"
                  onMouseDown={(e) => handleMouseDown(e, 'description')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              
              {/* Upload Date */}
              <th className="text-left px-4 relative cursor-pointer hover:bg-gray-100" style={{ width: `${columnWidths.uploadDate}px` }} onClick={() => handleSort('uploadDate')}>
                <div className="flex items-center gap-1">
                  Upload Date
                  {sortColumn === 'uploadDate' && (
                    sortDirection === 'asc' ? (
                      <ChevronUp className="h-3 w-3" />
                    ) : (
                      <ChevronDown className="h-3 w-3" />
                    )
                  )}
                </div>
                <div
                  className="absolute right-0 top-0 bottom-0 w-1 bg-gray-300 hover:bg-blue-500 cursor-col-resize"
                  onMouseDown={(e) => handleMouseDown(e, 'uploadDate')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              
              {/* Frame Count */}
              <th className="text-center px-4 relative cursor-pointer hover:bg-gray-100" style={{ width: `${columnWidths.frameCount}px` }} onClick={() => handleSort('frameCount')}>
                🖼️
                <div
                  className="absolute right-0 top-0 bottom-0 w-1 bg-gray-300 hover:bg-blue-500 cursor-col-resize"
                  onMouseDown={(e) => handleMouseDown(e, 'frameCount')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              
              {/* File Format */}
              <th className="text-center px-4 relative cursor-pointer hover:bg-gray-100" style={{ width: `${columnWidths.fileFormat}px` }} onClick={() => handleSort('fileFormat')}>
                📄
                <div
                  className="absolute right-0 top-0 bottom-0 w-1 bg-gray-300 hover:bg-blue-500 cursor-col-resize"
                  onMouseDown={(e) => handleMouseDown(e, 'fileFormat')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              
              {/* File Size */}
              <th className="text-center px-4 relative cursor-pointer hover:bg-gray-100" style={{ width: `${columnWidths.fileSize}px` }} onClick={() => handleSort('fileSize')}>
                💾
                <div
                  className="absolute right-0 top-0 bottom-0 w-1 bg-gray-300 hover:bg-blue-500 cursor-col-resize"
                  onMouseDown={(e) => handleMouseDown(e, 'fileSize')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              
              {/* Width */}
              <th className="text-center px-4 relative cursor-pointer hover:bg-gray-100" style={{ width: `${columnWidths.width}px` }} onClick={() => handleSort('width')}>
                ↔️
                <div
                  className="absolute right-0 top-0 bottom-0 w-1 bg-gray-300 hover:bg-blue-500 cursor-col-resize"
                  onMouseDown={(e) => handleMouseDown(e, 'width')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              
              {/* Height */}
              <th className="text-center px-4 relative cursor-pointer hover:bg-gray-100" style={{ width: `${columnWidths.height}px` }} onClick={() => handleSort('height')}>
                ↕️
                <div
                  className="absolute right-0 top-0 bottom-0 w-1 bg-gray-300 hover:bg-blue-500 cursor-col-resize"
                  onMouseDown={(e) => handleMouseDown(e, 'height')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              
              {/* Reactions */}
              <th className="text-center px-4 relative cursor-pointer hover:bg-gray-100" style={{ width: `${columnWidths.reactions}px` }} onClick={() => handleSort('reactions')}>
                ⚡
                <div
                  className="absolute right-0 top-0 bottom-0 w-1 bg-gray-300 hover:bg-blue-500 cursor-col-resize"
                  onMouseDown={(e) => handleMouseDown(e, 'reactions')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              
              {/* Comments */}
              <th className="text-center px-4 relative cursor-pointer hover:bg-gray-100" style={{ width: `${columnWidths.comments}px` }} onClick={() => handleSort('comments')}>
                💬
                <div
                  className="absolute right-0 top-0 bottom-0 w-1 bg-gray-300 hover:bg-blue-500 cursor-col-resize"
                  onMouseDown={(e) => handleMouseDown(e, 'comments')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              
              {/* Views */}
              <th className="text-center px-4 relative cursor-pointer hover:bg-gray-100" style={{ width: `${columnWidths.views}px` }} onClick={() => handleSort('views')}>
                👁️
                <div
                  className="absolute right-0 top-0 bottom-0 w-1 bg-gray-300 hover:bg-blue-500 cursor-col-resize"
                  onMouseDown={(e) => handleMouseDown(e, 'views')}
                  onClick={(e) => e.stopPropagation()}
                />
              </th>
              
              {/* Delete */}
              <th className="px-2 text-center relative" style={{ width: `${columnWidths.delete}px` }}>
                <Trash2 className="h-4 w-4 mx-auto text-gray-500" />
              </th>
            </tr>
          </thead>
          <tbody>
            {currentArtworks.map((artwork) => (
              <tr 
                key={artwork.id} 
                className={`border-b hover:bg-gray-50 ${artwork.isHidden ? 'opacity-50 bg-gray-100' : ''}`}
                style={{ height: '32px' }}
              >
                {/* Checkbox */}
                <td className="px-4" style={{ height: '32px', width: `${columnWidths.checkbox}px` }}>
                  <div className="flex items-center justify-center" style={{ height: '32px' }}>
                    <Checkbox
                      checked={selectedIds.has(artwork.id)}
                      onCheckedChange={(checked) => handleSelectOne(artwork.id, checked as boolean)}
                      aria-label={`Select ${artwork.title}`}
                    />
                  </div>
                </td>
                
                {/* Hide/Unhide */}
                <td className="px-2 text-center" style={{ height: '32px', width: `${columnWidths.visibility}px` }}>
                  <div className="flex items-center justify-center" style={{ height: '32px' }}>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onToggleHide(artwork.id)}
                      className="h-6 w-6 p-0"
                      aria-label={artwork.isHidden ? "Unhide artwork" : "Hide artwork"}
                    >
                      {artwork.isHidden ? (
                        <EyeOff className="h-4 w-4 text-gray-500" />
                      ) : (
                        <Eye className="h-4 w-4 text-gray-500" />
                      )}
                    </Button>
                  </div>
                </td>
                
                {/* Thumbnail */}
                <td className="px-2" style={{ height: '32px', width: `${columnWidths.thumbnail}px` }}>
                  <div className="flex items-center justify-center" style={{ height: '32px' }}>
                    <ImageWithFallback
                      src={artwork.imageUrl}
                      alt={artwork.title}
                      style={{ width: '32px', height: '32px' }}
                      className="object-cover rounded"
                    />
                  </div>
                </td>
                
                {/* Title */}
                <td className="px-4" style={{ height: '32px', width: `${columnWidths.title}px` }}>
                  <div className="flex items-center" style={{ height: '32px' }}>
                    <span className="text-sm truncate block leading-tight">
                      {artwork.title}
                    </span>
                  </div>
                </td>
                
                {/* Description */}
                <td className="px-4" style={{ height: '32px', width: `${columnWidths.description}px` }}>
                  <div className="flex items-center" style={{ height: '32px', paddingTop: '1px', paddingBottom: '1px' }}>
                    <span className="text-sm text-gray-600 truncate block leading-tight">
                      {artwork.description}
                    </span>
                  </div>
                </td>
                
                {/* Upload Date */}
                <td className="px-4" style={{ height: '32px', width: `${columnWidths.uploadDate}px` }}>
                  <div className="flex items-center" style={{ height: '32px' }}>
                    <span className="text-sm text-gray-600 leading-tight whitespace-nowrap">
                      {new Date(artwork.uploadDate).toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric'
                      })}
                    </span>
                  </div>
                </td>
                
                {/* Frame Count */}
                <td className="px-4 text-center" style={{ height: '32px', width: `${columnWidths.frameCount}px` }}>
                  <div className="flex items-center justify-center" style={{ height: '32px' }}>
                    <span className="text-sm text-gray-600 leading-tight">{artwork.frameCount}</span>
                  </div>
                </td>
                
                {/* File Format */}
                <td className="px-4 text-center" style={{ height: '32px', width: `${columnWidths.fileFormat}px` }}>
                  <div className="flex items-center justify-center" style={{ height: '32px' }}>
                    <span className="text-sm text-gray-600 leading-tight">{artwork.fileFormat}</span>
                  </div>
                </td>
                
                {/* File Size */}
                <td className="px-4 text-center" style={{ height: '32px', width: `${columnWidths.fileSize}px` }}>
                  <div className="flex items-center justify-center" style={{ height: '32px' }}>
                    <span className="text-sm text-gray-600 leading-tight">{formatFileSize(artwork.fileSize)}</span>
                  </div>
                </td>
                
                {/* Width */}
                <td className="px-4 text-center" style={{ height: '32px', width: `${columnWidths.width}px` }}>
                  <div className="flex items-center justify-center" style={{ height: '32px' }}>
                    <span className="text-sm text-gray-600 leading-tight">{artwork.width}</span>
                  </div>
                </td>
                
                {/* Height */}
                <td className="px-4 text-center" style={{ height: '32px', width: `${columnWidths.height}px` }}>
                  <div className="flex items-center justify-center" style={{ height: '32px' }}>
                    <span className="text-sm text-gray-600 leading-tight">{artwork.height}</span>
                  </div>
                </td>
                
                {/* Reactions */}
                <td className="px-4 text-center" style={{ height: '32px', width: `${columnWidths.reactions}px` }}>
                  <div className="flex items-center justify-center" style={{ height: '32px' }}>
                    <span className="text-sm text-gray-600 leading-tight">{formatMetricNumber(artwork.reactions)}</span>
                  </div>
                </td>
                
                {/* Comments */}
                <td className="px-4 text-center" style={{ height: '32px', width: `${columnWidths.comments}px` }}>
                  <div className="flex items-center justify-center" style={{ height: '32px' }}>
                    <span className="text-sm text-gray-600 leading-tight">{formatMetricNumber(artwork.comments)}</span>
                  </div>
                </td>
                
                {/* Views */}
                <td className="px-4 text-center" style={{ height: '32px', width: `${columnWidths.views}px` }}>
                  <div className="flex items-center justify-center" style={{ height: '32px' }}>
                    <span className="text-sm text-gray-600 leading-tight">{formatMetricNumber(artwork.views)}</span>
                  </div>
                </td>
                
                {/* Delete */}
                <td className="px-2 text-center" style={{ height: '32px', width: `${columnWidths.delete}px` }}>
                  <div className="flex items-center justify-center" style={{ height: '32px' }}>
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0"
                          aria-label="Delete artwork"
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Delete Artwork</AlertDialogTitle>
                          <AlertDialogDescription>
                            Are you sure you want to delete "{artwork.title}"? This action cannot be undone.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction
                            onClick={() => onDelete(artwork.id)}
                            className="bg-red-600 hover:bg-red-700"
                          >
                            Delete
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex flex-col gap-3 px-4 py-4 border-t">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="text-sm text-gray-600">
            Showing {startIndex + 1} to {Math.min(endIndex, artworks.length)} of {artworks.length} artworks
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(currentPage - 1)}
              disabled={currentPage === 0}
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Previous
            </Button>
            <span className="text-sm text-gray-600">
              Page {currentPage + 1} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(currentPage + 1)}
              disabled={currentPage >= totalPages - 1}
            >
              Next
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}