import { Button } from './ui/button';
import { Download, Eye, EyeOff, Trash2 } from 'lucide-react';
import { Checkbox } from './ui/checkbox';
import { useState } from 'react';

interface BulkActionsPanelProps {
  selectedCount: number;
  onDownload: () => void;
  onHide: () => void;
  onUnhide: () => void;
  onDelete: () => void;
}

export function BulkActionsPanel({
  selectedCount,
  onDownload,
  onHide,
  onUnhide,
  onDelete,
}: BulkActionsPanelProps) {
  const isDisabled = selectedCount === 0;
  const isDeleteDisabled = selectedCount === 0 || selectedCount > 32;
  const isDownloadDisabled = selectedCount === 0 || selectedCount > 128;
  const [includeComments, setIncludeComments] = useState(true);
  const [emailNotification, setEmailNotification] = useState(false);

  const handleDeleteClick = () => {
    if (window.confirm(`Are you sure you want to delete ${selectedCount} artwork${selectedCount !== 1 ? 's' : ''}? This action cannot be undone.`)) {
      onDelete();
    }
  };

  return (
    <>
      {/* Selection state panel */}
      <div className="border-t bg-gray-50 px-4 py-4">
        <div className="flex flex-col gap-2">
          <span className="text-xs font-medium text-gray-700">Selection</span>
          <span className="text-sm text-gray-600">
            {selectedCount > 0 ? (
              <><span className="text-lg font-bold text-blue-600">{selectedCount}</span> artwork{selectedCount !== 1 ? 's' : ''} selected</>
            ) : (
              <>No artworks selected</>
            )}
          </span>
        </div>
      </div>

      {/* Batch actions panel */}
      <div className="border-t bg-gray-50 px-4 py-4">
        <div className="flex flex-col gap-4">
          <span className="text-xs font-medium text-gray-700">Batch actions</span>
          <div className="flex gap-2 flex-wrap">
            <Button
              variant="outline"
              size="sm"
              onClick={onHide}
              disabled={isDisabled}
            >
              <EyeOff className="h-4 w-4 mr-2" />
              Hide
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={onUnhide}
              disabled={isDisabled}
            >
              <Eye className="h-4 w-4 mr-2" />
              Unhide
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDeleteClick}
              disabled={isDeleteDisabled}
              className="text-red-600 hover:text-red-700 hover:bg-red-50 disabled:text-gray-400"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Delete
            </Button>
          </div>
          {selectedCount > 32 && (
            <span className="text-xs text-gray-500">
              Only up to 32 artworks can be deleted per operation.
            </span>
          )}
        </div>
      </div>

      {/* Artwork batch download panel */}
      <div className="border-t bg-gray-50 px-4 py-4">
        <div className="flex flex-col gap-4">
          <span className="text-xs font-medium text-gray-700">Batch download</span>
          <div className="flex flex-col gap-3">
            <ul className="text-sm text-gray-700 list-disc list-inside space-y-1">
              <li>Selected artworks will be put into one zip file for download.</li>
              <li>Maximum 128 artworks per batch and 8 batches per day.</li>
              <li>Most requests are ready within minutes.</li>
              <li>Once the link is available, it lasts for 7 days.</li>
            </ul>
            <div className="flex items-center gap-2">
              <Checkbox
                id="include-comments"
                checked={includeComments}
                onCheckedChange={(checked) => setIncludeComments(checked as boolean)}
                disabled={isDisabled}
              />
              <label 
                htmlFor="include-comments" 
                className={`text-sm cursor-pointer ${isDisabled ? 'text-gray-400' : 'text-gray-600'}`}
              >
                Include received comments and reactions
              </label>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="email-notification"
                checked={emailNotification}
                onCheckedChange={(checked) => setEmailNotification(checked as boolean)}
                disabled={isDisabled}
              />
              <label 
                htmlFor="email-notification" 
                className={`text-sm cursor-pointer ${isDisabled ? 'text-gray-400' : 'text-gray-600'}`}
              >
                Send me an e-mail when the link is ready
              </label>
            </div>
            <div>
              <Button
                variant="outline"
                size="sm"
                onClick={onDownload}
                disabled={isDownloadDisabled}
              >
                <Download className="h-4 w-4 mr-2" />
                Request Download
              </Button>
            </div>
            {selectedCount > 128 && (
              <span className="text-xs text-gray-500">
                Only up to 128 artworks can be downloaded per batch.
              </span>
            )}
          </div>
        </div>
      </div>
    </>
  );
}