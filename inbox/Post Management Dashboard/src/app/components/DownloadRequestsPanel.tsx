import { Button } from './ui/button';
import { Download, Clock, AlertCircle } from 'lucide-react';

export interface DownloadRequest {
  id: string;
  date: string;
  artworkCount: number;
  status: 'ready' | 'expired';
  expiresAt?: string;
}

interface DownloadRequestsPanelProps {
  requests: DownloadRequest[];
}

export function DownloadRequestsPanel({ requests }: DownloadRequestsPanelProps) {
  const handleDownload = (requestId: string) => {
    // Mock download functionality
    const link = document.createElement('a');
    link.href = '#';
    link.download = `artworks-${requestId}.zip`;
    alert(`Downloading artworks package ${requestId}...`);
  };

  return (
    <div className="mt-6 bg-white lg:rounded-lg shadow">
      <div className="px-4 py-3 border-b">
        <h2 className="font-semibold">Download links</h2>
      </div>
      
      <div className="p-4">
        {requests.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Clock className="h-12 w-12 mx-auto mb-2 text-gray-300" />
            <p>No download requests yet</p>
            <p className="text-sm">Your download requests will appear here when ready</p>
          </div>
        ) : (
          <div className="space-y-2">
            {requests.map((request) => (
              <div
                key={request.id}
                className={`flex items-center justify-between p-3 rounded-lg border ${
                  request.status === 'expired'
                    ? 'bg-gray-50 border-gray-200'
                    : 'bg-blue-50 border-blue-200'
                }`}
              >
                <div className="flex items-center gap-3">
                  {request.status === 'expired' ? (
                    <AlertCircle className="h-5 w-5 text-gray-400" />
                  ) : (
                    <Download className="h-5 w-5 text-blue-600" />
                  )}
                  <div>
                    <div className="text-sm">
                      <span className={request.status === 'expired' ? 'text-gray-500' : 'text-gray-900'}>
                        {request.artworkCount} artwork{request.artworkCount !== 1 ? 's' : ''}
                      </span>
                      <span className="text-gray-400 mx-2">•</span>
                      <span className="text-gray-500 text-xs">
                        {new Date(request.date).toLocaleString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          year: 'numeric',
                          hour: 'numeric',
                          minute: '2-digit'
                        })}
                      </span>
                    </div>
                    {request.status === 'ready' && request.expiresAt && (
                      <div className="text-xs text-gray-500 mt-1">
                        Expires: {new Date(request.expiresAt).toLocaleString('en-US', {
                          month: 'short',
                          day: 'numeric',
                          hour: 'numeric',
                          minute: '2-digit'
                        })}
                      </div>
                    )}
                    {request.status === 'expired' && (
                      <div className="text-xs text-gray-400 mt-1">
                        Download link expired
                      </div>
                    )}
                  </div>
                </div>
                
                {request.status === 'ready' ? (
                  <Button
                    size="sm"
                    onClick={() => handleDownload(request.id)}
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Download
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled
                  >
                    Expired
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}