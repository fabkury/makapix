import { useState } from 'react';
import { CollapsiblePanel } from '@/app/components/CollapsiblePanel';

const AVAILABLE_BADGES = [
  'Bug Hunter',
  'Code Reviewer',
  'Community Leader',
  'Early Adopter',
  'Helpful Contributor',
  'Moderator',
  'Problem Solver',
  'Quality Contributor',
  'Rising Star',
  'Trusted Member',
  'Veteran',
].sort();

export function BadgePanel() {
  const [userBadges, setUserBadges] = useState<Set<string>>(new Set(['Early Adopter', 'Rising Star']));
  const [selectedBadge, setSelectedBadge] = useState('');
  
  const handleBadgeSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedBadge(e.target.value);
  };
  
  const handleGrantRevoke = () => {
    if (!selectedBadge) return;
    
    const newBadges = new Set(userBadges);
    const hasBadge = userBadges.has(selectedBadge);
    
    if (hasBadge) {
      newBadges.delete(selectedBadge);
    } else {
      newBadges.add(selectedBadge);
    }
    
    setUserBadges(newBadges);
    setSelectedBadge('');
  };
  
  const isGrantButton = selectedBadge && !userBadges.has(selectedBadge);
  const isRevokeButton = selectedBadge && userBadges.has(selectedBadge);
  
  return (
    <CollapsiblePanel title="Badges">
      <div className="space-y-4">
        <div>
          <label className="block text-sm text-gray-300 mb-2">
            Current badges ({userBadges.size})
          </label>
          <div className="flex flex-wrap gap-2 mb-4">
            {Array.from(userBadges).map((badge) => (
              <span
                key={badge}
                className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-cyan-500/20 text-cyan-400 border border-cyan-400/30"
              >
                {badge}
              </span>
            ))}
            {userBadges.size === 0 && (
              <span className="text-sm text-gray-500 italic">No badges yet</span>
            )}
          </div>
        </div>
        
        <div>
          <label className="block text-sm text-gray-300 mb-2">
            Select badge
          </label>
          <select
            value={selectedBadge}
            onChange={handleBadgeSelect}
            className="w-full px-3 py-2 bg-white/5 border border-white/20 rounded-lg focus:ring-2 focus:ring-cyan-400 focus:border-cyan-400 outline-none text-white"
          >
            <option value="" className="bg-black">-- Choose a badge --</option>
            {AVAILABLE_BADGES.map((badge) => (
              <option key={badge} value={badge} className="bg-black">
                {badge} {userBadges.has(badge) ? '✓' : ''}
              </option>
            ))}
          </select>
        </div>
        
        <button
          onClick={handleGrantRevoke}
          disabled={!selectedBadge}
          className={`w-full py-2.5 rounded-lg font-medium transition-colors ${
            !selectedBadge
              ? 'bg-white/5 text-gray-600 cursor-not-allowed'
              : isRevokeButton
              ? 'bg-pink-500 text-black hover:bg-pink-400 active:bg-pink-600'
              : 'bg-cyan-500 text-black hover:bg-cyan-400 active:bg-cyan-600'
          }`}
        >
          {isRevokeButton ? 'Revoke' : 'Grant'}
        </button>
      </div>
    </CollapsiblePanel>
  );
}