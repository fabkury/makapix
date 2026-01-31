/**
 * ProfileTabs component - tab switching for gallery/favourites.
 * The favourites (Lightning) tab is only visible to authenticated users.
 */

interface ProfileTabsProps {
  activeTab: 'gallery' | 'favourites';
  onTabChange: (tab: 'gallery' | 'favourites') => void;
  isAuthenticated?: boolean;
}

export default function ProfileTabs({ activeTab, onTabChange, isAuthenticated = false }: ProfileTabsProps) {
  return (
    <div className="profile-tabs">
      <button
        className={`tab ${activeTab === 'gallery' ? 'active' : ''}`}
        onClick={() => onTabChange('gallery')}
        style={activeTab === 'gallery' ? { filter: 'drop-shadow(0 4px 12px rgba(255, 255, 255, 0.6))' } : undefined}
      >
        🖼️
        {activeTab === 'gallery' && <div className="tab-indicator" />}
      </button>
      {isAuthenticated && (
        <button
          className={`tab ${activeTab === 'favourites' ? 'active' : ''}`}
          onClick={() => onTabChange('favourites')}
          style={activeTab === 'favourites' ? { filter: 'drop-shadow(0 4px 12px rgba(255, 255, 255, 0.6))' } : undefined}
        >
          ⚡
          {activeTab === 'favourites' && <div className="tab-indicator" />}
        </button>
      )}

      <style jsx>{`
        .profile-tabs {
          display: flex;
          gap: 32px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.2);
          margin-bottom: 24px;
        }
        .tab {
          position: relative;
          padding: 12px 4px;
          background: none;
          border: none;
          cursor: pointer;
          font-size: 1.25rem;
          color: rgba(255, 255, 255, 0.5);
          transition: color 0.2s ease;
        }
        .tab:hover {
          color: rgba(255, 255, 255, 0.8);
        }
        .tab.active {
          color: white;
        }
        .tab-indicator {
          position: absolute;
          bottom: 0;
          left: 0;
          right: 0;
          height: 2px;
          background: linear-gradient(to right, var(--accent-pink), var(--accent-cyan));
        }
      `}</style>
    </div>
  );
}
