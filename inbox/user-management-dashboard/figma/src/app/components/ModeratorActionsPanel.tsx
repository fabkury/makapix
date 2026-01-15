import { useState } from 'react';
import { CollapsiblePanel } from '@/app/components/CollapsiblePanel';
import { UserCheck, UserX, Eye, EyeOff, Ban, Mail } from 'lucide-react';

export function ModeratorActionsPanel() {
  const [isTrusted, setIsTrusted] = useState(false);
  const [isHidden, setIsHidden] = useState(false);
  const [confirmBan, setConfirmBan] = useState<number>(0);
  const [confirmEmail, setConfirmEmail] = useState(false);
  const [emailRevealed, setEmailRevealed] = useState(false);
  const [confirmHide, setConfirmHide] = useState<number>(0);
  
  const handleToggleTrust = () => {
    setIsTrusted(!isTrusted);
  };
  
  const handleToggleHidden = () => {
    if (confirmHide < 2) {
      setConfirmHide(confirmHide + 1);
      setTimeout(() => setConfirmHide(0), 3000);
      return;
    }
    
    setIsHidden(!isHidden);
    setConfirmHide(0);
  };
  
  const handleBanUser = () => {
    if (confirmBan < 2) {
      setConfirmBan(confirmBan + 1);
      setTimeout(() => setConfirmBan(0), 3000);
      return;
    }
    
    alert('User has been banned');
    setConfirmBan(0);
  };
  
  const handleRevealEmail = () => {
    if (!confirmEmail) {
      setConfirmEmail(true);
      setTimeout(() => setConfirmEmail(false), 3000);
      return;
    }
    
    setEmailRevealed(true);
    setConfirmEmail(false);
  };
  
  return (
    <CollapsiblePanel title="Moderation actions">
      <div className="space-y-3">
        <button
          onClick={handleToggleTrust}
          className={`w-full py-3 px-4 rounded-lg font-medium transition-colors flex items-center justify-center gap-2 ${
            isTrusted
              ? 'bg-white/10 text-white hover:bg-white/15 active:bg-white/20 border border-white/20'
              : 'bg-cyan-500 text-black hover:bg-cyan-400 active:bg-cyan-600'
          }`}
        >
          {isTrusted ? (
            <>
              <UserX className="w-5 h-5" />
              Distrust User
            </>
          ) : (
            <>
              <UserCheck className="w-5 h-5" />
              Trust User
            </>
          )}
        </button>
        
        <div className="h-3" />
        
        <button
          onClick={handleToggleHidden}
          className={`w-full py-3 px-4 rounded-lg font-medium transition-colors flex items-center justify-center gap-2 ${
            confirmHide > 0
              ? isHidden
                ? 'bg-white/20 text-white hover:bg-white/25 active:bg-white/30 border border-white/30'
                : 'bg-pink-600 text-black hover:bg-pink-500 active:bg-pink-700'
              : isHidden
              ? 'bg-white/10 text-white hover:bg-white/15 active:bg-white/20 border border-white/20'
              : 'bg-pink-500 text-black hover:bg-pink-400 active:bg-pink-600'
          }`}
        >
          {isHidden ? (
            <>
              <Eye className="w-5 h-5" />
              {confirmHide === 0 && 'Unhide User'}
              {confirmHide === 1 && 'Click again to confirm'}
              {confirmHide === 2 && 'Click once more to unhide'}
            </>
          ) : (
            <>
              <EyeOff className="w-5 h-5" />
              {confirmHide === 0 && 'Hide User'}
              {confirmHide === 1 && 'Click again to confirm'}
              {confirmHide === 2 && 'Click once more to hide'}
            </>
          )}
        </button>
        
        <div className="h-3" />
        
        <button
          onClick={handleBanUser}
          className={`w-full py-3 px-4 rounded-lg font-medium transition-colors flex items-center justify-center gap-2 ${
            confirmBan > 0
              ? 'bg-pink-600 text-black hover:bg-pink-500 active:bg-pink-700'
              : 'bg-pink-500 text-black hover:bg-pink-400 active:bg-pink-600'
          }`}
        >
          <Ban className="w-5 h-5" />
          {confirmBan === 0 && 'Ban User'}
          {confirmBan === 1 && 'Click again to confirm'}
          {confirmBan === 2 && 'Click once more to ban'}
        </button>
        
        <div className="h-3" />
        
        <button
          onClick={handleRevealEmail}
          className={`w-full py-3 px-4 rounded-lg font-medium transition-colors flex items-center justify-center gap-2 ${
            confirmEmail
              ? 'bg-cyan-600 text-black hover:bg-cyan-500 active:bg-cyan-700'
              : 'bg-cyan-500 text-black hover:bg-cyan-400 active:bg-cyan-600'
          }`}
        >
          <Mail className="w-5 h-5" />
          {confirmEmail ? 'Click to confirm (action will be logged)' : "Reveal User's Email"}
        </button>
        
        {emailRevealed && (
          <div className="mt-4 p-4 bg-cyan-500/10 border border-cyan-500/30 rounded-lg">
            <div className="flex items-start gap-2">
              <Mail className="w-5 h-5 text-cyan-400 flex-shrink-0 mt-0.5" />
              <div>
                <div className="text-white font-medium mb-1">Email Address</div>
                <div className="text-cyan-400 mb-2">user@example.com</div>
                <div className="text-xs text-gray-400">
                  ⚠️ This action has been logged for auditing purposes.
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </CollapsiblePanel>
  );
}
