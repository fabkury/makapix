import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../../components/Layout';
import PlayerCard from '../../../components/PlayerCard';
import RegisterPlayerModal from '../../../components/RegisterPlayerModal';
import { listPlayers, Player } from '../../../lib/api';

interface User {
  id: number;
  user_key: string;
  public_sqid: string | null;
  handle: string;
}

export default function PlayersPage() {
  const router = useRouter();
  const { sqid } = router.query;
  const sqidStr = typeof sqid === 'string' ? sqid : null;

  const [user, setUser] = useState<User | null>(null);
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showRegisterModal, setShowRegisterModal] = useState(false);

  const API_BASE_URL =
    typeof window !== 'undefined'
      ? process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin
      : '';

  // Fetch user by sqid first
  useEffect(() => {
    if (!sqidStr) return;

    const fetchUser = async () => {
      try {
        const token = localStorage.getItem('access_token');
        const headers: HeadersInit = token ? { 'Authorization': `Bearer ${token}` } : {};
        
        const response = await fetch(`${API_BASE_URL}/api/user/u/${sqidStr}`, { headers });
        
        if (!response.ok) {
          setError('User not found');
          setLoading(false);
          return;
        }

        const userData = await response.json();
        setUser(userData);
      } catch (err: any) {
        setError(err.message || 'Failed to load user');
        setLoading(false);
      }
    };

    fetchUser();
  }, [sqidStr, API_BASE_URL]);

  // Fetch players once we have the user
  useEffect(() => {
    if (!user || !user.public_sqid) return;

    const loadPlayers = async (isInitial = false) => {
      if (isInitial) {
        setLoading(true);
        setError(null);
      }
      try {
        // API endpoint handles authorization - will return 403 if not owner
        const data = await listPlayers(user.public_sqid!);
        setPlayers(data.items);
      } catch (err: any) {
        if (isInitial) {
          // Check if it's an authorization error
          if (err.message?.includes('403') || err.message?.includes('permission')) {
            setError('You can only view your own players');
          } else {
            setError(err.message || 'Failed to load players');
          }
        }
      } finally {
        if (isInitial) {
          setLoading(false);
        }
      }
    };

    // Initial load
    loadPlayers(true);

    // Poll for status updates every 5 seconds
    const pollInterval = setInterval(() => {
      loadPlayers(false);
    }, 5000);

    return () => clearInterval(pollInterval);
  }, [user]);

  const handleRefresh = async () => {
    if (!user || !user.public_sqid) return;
    try {
      const data = await listPlayers(user.public_sqid);
      setPlayers(data.items);
    } catch (err: any) {
      console.error('Failed to refresh players:', err);
    }
  };

  const handleDelete = async () => {
    await handleRefresh();
  };

  const handleRegisterSuccess = async (player: Player) => {
    await handleRefresh();
  };

  const currentUserId = typeof window !== 'undefined' ? localStorage.getItem('user_id') : null;
  const isOwnProfile = user && currentUserId === String(user.id);

  if (loading) {
    return (
      <Layout title="Loading...">
        <div className="loading-container">
          <div className="loading-spinner"></div>
        </div>
        <style jsx>{`
          .loading-container {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - var(--header-height));
          }
          .loading-spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--bg-tertiary);
            border-top-color: var(--accent-cyan);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
          }
          @keyframes spin {
            to {
              transform: rotate(360deg);
            }
          }
        `}</style>
      </Layout>
    );
  }

  if (error || !isOwnProfile) {
    return (
      <Layout title="Access Denied">
        <div className="error-container">
          <span className="error-icon">🔒</span>
          <h1>{error || 'You can only view your own players'}</h1>
        </div>
        <style jsx>{`
          .error-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - var(--header-height));
            padding: 2rem;
            text-align: center;
          }
          .error-icon {
            font-size: 4rem;
            margin-bottom: 1rem;
          }
          h1 {
            font-size: 1.5rem;
            color: var(--text-primary);
          }
        `}</style>
      </Layout>
    );
  }

  const onlineCount = players.filter((p) => p.connection_status === 'online').length;
  const hasPlayers = players.length > 0;

  return (
    <Layout title="My Players">
      <div className="players-container">
        <div className="page-header">
          <h1>My Players</h1>
          <div className="header-actions">
            <button className="register-btn" onClick={() => setShowRegisterModal(true)}>
              + Register Player
            </button>
          </div>
        </div>

        <div className="stats-bar">
          <div className="stat">
            <span className="stat-value">{players.length}</span>
            <span className="stat-label">Total</span>
          </div>
          <div className="stat">
            <span className="stat-value">{onlineCount}</span>
            <span className="stat-label">Online</span>
          </div>
          <div className="stat">
            <span className="stat-value">{players.length - onlineCount}</span>
            <span className="stat-label">Offline</span>
          </div>
        </div>

        {!hasPlayers ? (
          <div className="empty-state">
            <span className="empty-icon">🖼️</span>
            <h2>No players registered</h2>
            <p>Register a player to start displaying artworks on your devices.</p>
            <button className="register-btn-large" onClick={() => setShowRegisterModal(true)}>
              Register Your First Player
            </button>
          </div>
        ) : (
          <div className="players-list">
            {players.map((player) => (
              <PlayerCard
                key={player.id}
                player={player}
                sqid={user!.public_sqid!}
                onDelete={handleDelete}
                onRefresh={handleRefresh}
              />
            ))}
          </div>
        )}

        <RegisterPlayerModal
          isOpen={showRegisterModal}
          onClose={() => setShowRegisterModal(false)}
          onSuccess={handleRegisterSuccess}
        />
      </div>

      <style jsx>{`
        .players-container {
          max-width: 1200px;
          margin: 0 auto;
          padding: 24px;
        }

        .page-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
        }

        .page-header h1 {
          font-size: 2rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0;
        }

        .header-actions {
          display: flex;
          gap: 12px;
        }

        .register-btn {
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          border: none;
          border-radius: 8px;
          padding: 10px 20px;
          font-size: 1rem;
          font-weight: 600;
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .register-btn:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 20px rgba(255, 110, 180, 0.4);
        }

        .stats-bar {
          display: flex;
          gap: 24px;
          background: var(--bg-secondary);
          border-radius: 12px;
          padding: 20px;
          margin-bottom: 24px;
        }

        .stat {
          display: flex;
          flex-direction: column;
          align-items: center;
        }

        .stat-value {
          font-size: 2rem;
          font-weight: 700;
          color: var(--text-primary);
        }

        .stat-label {
          font-size: 0.85rem;
          color: var(--text-muted);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-top: 4px;
        }

        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 4rem 2rem;
          text-align: center;
          background: var(--bg-secondary);
          border-radius: 16px;
        }

        .empty-icon {
          font-size: 4rem;
          margin-bottom: 1rem;
          opacity: 0.5;
        }

        .empty-state h2 {
          font-size: 1.5rem;
          color: var(--text-primary);
          margin: 0 0 8px 0;
        }

        .empty-state p {
          color: var(--text-secondary);
          margin: 0 0 24px 0;
        }

        .register-btn-large {
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          border: none;
          border-radius: 8px;
          padding: 12px 24px;
          font-size: 1rem;
          font-weight: 600;
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .register-btn-large:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 20px rgba(255, 110, 180, 0.4);
        }

        .players-list {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        @media (max-width: 600px) {
          .page-header {
            flex-direction: column;
            align-items: flex-start;
            gap: 16px;
          }

          .stats-bar {
            flex-direction: column;
            gap: 16px;
          }
        }
      `}</style>
    </Layout>
  );
}

