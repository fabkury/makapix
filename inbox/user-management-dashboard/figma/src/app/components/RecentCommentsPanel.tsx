import { useState } from 'react';
import { CollapsiblePanel } from '@/app/components/CollapsiblePanel';
import { Eye, EyeOff, Trash2, ChevronLeft, ChevronRight } from 'lucide-react';

interface Comment {
  id: string;
  dateTime: string;
  artwork: string;
  text: string;
  isHidden: boolean;
}

// Generate mock comments
const generateMockComments = (): Comment[] => {
  const comments: Comment[] = [];
  const artworks = [
    'https://images.unsplash.com/photo-1579783902614-a3fb3927b6a5?w=100&h=100&fit=crop',
    'https://images.unsplash.com/photo-1541961017774-22349e4a1262?w=100&h=100&fit=crop',
    'https://images.unsplash.com/photo-1578926288207-a90a5366759d?w=100&h=100&fit=crop',
    'https://images.unsplash.com/photo-1547891654-e66ed7ebb968?w=100&h=100&fit=crop',
  ];
  const texts = [
    'This is an amazing piece of work! I really love the color palette and composition.',
    'Great job on the details. The lighting is particularly well done.',
    'Beautiful artwork! The perspective is really interesting.',
    'Nice work! I appreciate the effort you put into this.',
    'Stunning piece! The textures are so realistic.',
    'I love the creativity here. Very inspiring!',
    'This is fantastic! The mood you created is perfect.',
    'Wonderful art! The details are incredible.',
  ];
  
  for (let i = 0; i < 1024; i++) {
    const date = new Date();
    date.setHours(date.getHours() - i);
    
    comments.push({
      id: `comment-${i}`,
      dateTime: date.toISOString(),
      artwork: artworks[i % artworks.length],
      text: texts[i % texts.length],
      isHidden: false,
    });
  }
  
  return comments;
};

const COMMENTS_PER_PAGE = 10;

export function RecentCommentsPanel() {
  const [comments, setComments] = useState<Comment[]>(generateMockComments());
  const [currentPage, setCurrentPage] = useState(1);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  
  const totalPages = Math.ceil(comments.length / COMMENTS_PER_PAGE);
  const startIndex = (currentPage - 1) * COMMENTS_PER_PAGE;
  const endIndex = startIndex + COMMENTS_PER_PAGE;
  const currentComments = comments.slice(startIndex, endIndex);
  
  const handleToggleHidden = (id: string) => {
    setComments(comments.map(c => 
      c.id === id ? { ...c, isHidden: !c.isHidden } : c
    ));
  };
  
  const handleDelete = (id: string) => {
    if (confirmDelete === id) {
      setComments(comments.filter(c => c.id !== id));
      setConfirmDelete(null);
    } else {
      setConfirmDelete(id);
      setTimeout(() => setConfirmDelete(null), 3000);
    }
  };
  
  const formatDateTime = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };
  
  return (
    <CollapsiblePanel title="Recent comments">
      <div className="space-y-4">
        <div className="text-sm text-gray-300">
          Total comments: {comments.length}
        </div>
        
        <div className="space-y-2">
          {currentComments.map((comment) => (
            <div
              key={comment.id}
              className={`border border-white/20 rounded-lg p-3 transition-opacity ${
                comment.isHidden ? 'opacity-40' : 'opacity-100'
              }`}
            >
              <div className="flex gap-3">
                <img
                  src={comment.artwork}
                  alt="Artwork"
                  className="w-16 h-16 rounded object-cover flex-shrink-0 border border-white/10"
                />
                
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-gray-400 mb-1">
                    {formatDateTime(comment.dateTime)}
                  </div>
                  <div className="text-sm text-white line-clamp-2">
                    {comment.text}
                  </div>
                </div>
                
                <div className="flex flex-col gap-1 flex-shrink-0">
                  <button
                    onClick={() => handleToggleHidden(comment.id)}
                    className="p-1.5 rounded hover:bg-white/10 transition-colors"
                    title={comment.isHidden ? 'Unhide' : 'Hide'}
                  >
                    {comment.isHidden ? (
                      <EyeOff className="w-4 h-4 text-cyan-400" />
                    ) : (
                      <Eye className="w-4 h-4 text-cyan-400" />
                    )}
                  </button>
                  
                  <button
                    onClick={() => handleDelete(comment.id)}
                    className={`p-1.5 rounded transition-colors ${
                      confirmDelete === comment.id
                        ? 'bg-pink-500/20 hover:bg-pink-500/30'
                        : 'hover:bg-white/10'
                    }`}
                    title={confirmDelete === comment.id ? 'Click again to confirm' : 'Delete'}
                  >
                    <Trash2 className={`w-4 h-4 ${
                      confirmDelete === comment.id ? 'text-pink-400' : 'text-pink-400'
                    }`} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
        
        {totalPages > 1 && (
          <div className="flex items-center justify-between pt-2">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm disabled:opacity-40 disabled:cursor-not-allowed hover:bg-white/10 transition-colors text-white"
            >
              <ChevronLeft className="w-4 h-4" />
              Previous
            </button>
            
            <span className="text-sm text-gray-300">
              Page {currentPage} of {totalPages}
            </span>
            
            <button
              onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm disabled:opacity-40 disabled:cursor-not-allowed hover:bg-white/10 transition-colors text-white"
            >
              Next
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </CollapsiblePanel>
  );
}