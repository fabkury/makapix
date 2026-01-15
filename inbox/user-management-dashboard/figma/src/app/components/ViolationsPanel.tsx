import { useState } from 'react';
import { CollapsiblePanel } from '@/app/components/CollapsiblePanel';
import { Trash2, ChevronLeft, ChevronRight } from 'lucide-react';

interface Violation {
  id: string;
  date: string;
  reason: string;
  moderator: string;
}

// Generate mock violations
const generateMockViolations = (): Violation[] => {
  return [
    {
      id: 'v1',
      date: new Date('2026-01-10').toISOString(),
      reason: 'Posted spam content in multiple threads',
      moderator: 'ModAlice',
    },
    {
      id: 'v2',
      date: new Date('2026-01-05').toISOString(),
      reason: 'Inappropriate language in comments',
      moderator: 'ModBob',
    },
    {
      id: 'v3',
      date: new Date('2025-12-28').toISOString(),
      reason: 'Harassment of other users',
      moderator: 'ModCarol',
    },
  ];
};

const VIOLATIONS_PER_PAGE = 5;

export function ViolationsPanel() {
  const [violations, setViolations] = useState<Violation[]>(generateMockViolations());
  const [reason, setReason] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [confirmIssue, setConfirmIssue] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<{ id: string; clicks: number } | null>(null);
  
  const totalPages = Math.ceil(violations.length / VIOLATIONS_PER_PAGE);
  const startIndex = (currentPage - 1) * VIOLATIONS_PER_PAGE;
  const endIndex = startIndex + VIOLATIONS_PER_PAGE;
  const currentViolations = violations.slice(startIndex, endIndex);
  
  const handleDeleteViolation = (id: string) => {
    if (confirmDelete?.id === id) {
      const newClicks = confirmDelete.clicks + 1;
      if (newClicks >= 3) {
        setViolations(violations.filter(v => v.id !== id));
        setConfirmDelete(null);
      } else {
        setConfirmDelete({ id, clicks: newClicks });
        setTimeout(() => setConfirmDelete(null), 3000);
      }
    } else {
      setConfirmDelete({ id, clicks: 1 });
      setTimeout(() => setConfirmDelete(null), 3000);
    }
  };
  
  const handleIssueViolation = () => {
    if (reason.length >= 8) {
      if (!confirmIssue) {
        setConfirmIssue(true);
        setTimeout(() => setConfirmIssue(false), 3000);
        return;
      }
      
      const newViolation: Violation = {
        id: `v${Date.now()}`,
        date: new Date().toISOString(),
        reason: reason,
        moderator: 'CurrentMod',
      };
      
      setViolations([newViolation, ...violations]);
      setReason('');
      setConfirmIssue(false);
    }
  };
  
  const formatDate = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };
  
  const isDisabled = reason.length < 8;
  
  return (
    <CollapsiblePanel title="Violations">
      <div className="space-y-4">
        <div>
          <div className="text-sm text-gray-300 mb-2">
            Total violations: {violations.length}
          </div>
          
          {violations.length > 0 ? (
            <>
              <div className="space-y-2 mb-4">
                {currentViolations.map((violation) => (
                  <div
                    key={violation.id}
                    className="border border-white/20 rounded-lg p-3 flex gap-3"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-xs text-gray-400 mb-1">
                        {formatDate(violation.date)} • by {violation.moderator}
                      </div>
                      <div className="text-sm text-white">
                        {violation.reason}
                      </div>
                    </div>
                    
                    <button
                      onClick={() => handleDeleteViolation(violation.id)}
                      className={`p-1.5 rounded transition-colors flex-shrink-0 ${
                        confirmDelete?.id === violation.id && confirmDelete.clicks === 1
                          ? 'bg-pink-500/20 hover:bg-pink-500/30'
                          : confirmDelete?.id === violation.id && confirmDelete.clicks === 2
                          ? 'bg-pink-500/40 hover:bg-pink-500/50'
                          : 'hover:bg-pink-500/20'
                      }`}
                      title={
                        confirmDelete?.id === violation.id
                          ? `Click ${3 - confirmDelete.clicks} more time${3 - confirmDelete.clicks === 1 ? '' : 's'} to confirm`
                          : 'Revoke violation'
                      }
                    >
                      <Trash2 className="w-4 h-4 text-pink-400" />
                    </button>
                  </div>
                ))}
              </div>
              
              {totalPages > 1 && (
                <div className="flex items-center justify-between pb-4 border-b border-white/10">
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
            </>
          ) : (
            <div className="text-sm text-gray-500 italic py-4 border-b border-white/10">
              No violations
            </div>
          )}
        </div>
        
        <div className="pt-2">
          <label className="block text-sm text-gray-300 mb-2">
            Issue new violation
          </label>
          
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Enter reason for violation (min 8 characters)..."
            className="w-full px-3 py-2 bg-white/5 border border-white/20 rounded-lg focus:ring-2 focus:ring-pink-400 focus:border-pink-400 outline-none resize-none text-white placeholder:text-gray-500"
            rows={3}
          />
          <div className="text-xs text-gray-400 mt-1">{reason.length} / 8 characters</div>
        </div>
        
        <button
          onClick={handleIssueViolation}
          disabled={isDisabled}
          className={`w-full py-2.5 rounded-lg font-medium transition-colors ${
            isDisabled
              ? 'bg-white/5 text-gray-600 cursor-not-allowed'
              : confirmIssue
              ? 'bg-pink-600 text-black hover:bg-pink-500 active:bg-pink-700'
              : 'bg-pink-500 text-black hover:bg-pink-400 active:bg-pink-600'
          }`}
        >
          {confirmIssue ? 'Click again to confirm' : 'Issue Violation'}
        </button>
      </div>
    </CollapsiblePanel>
  );
}