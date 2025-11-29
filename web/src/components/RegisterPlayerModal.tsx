import { useState } from 'react';
import { registerPlayer, Player } from '../lib/api';

interface RegisterPlayerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (player: Player) => void;
}

export default function RegisterPlayerModal({
  isOpen,
  onClose,
  onSuccess,
}: RegisterPlayerModalProps) {
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const player = await registerPlayer({
        registration_code: code.toUpperCase().trim(),
        name: name.trim(),
      });
      onSuccess(player);
      setCode('');
      setName('');
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to register player');
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    if (!isLoading) {
      setCode('');
      setName('');
      setError(null);
      onClose();
    }
  };

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Register a Player</h2>
          <button className="close-btn" onClick={handleClose} disabled={isLoading}>
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="code">Registration Code</label>
            <input
              id="code"
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 6))}
              placeholder="A3F8X2"
              maxLength={6}
              required
              disabled={isLoading}
              autoFocus
            />
            <small>Enter the 6-character code shown on your player</small>
          </div>

          <div className="form-group">
            <label htmlFor="name">Player Name</label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Living Room Display"
              maxLength={100}
              required
              disabled={isLoading}
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <div className="modal-actions">
            <button type="button" className="cancel-btn" onClick={handleClose} disabled={isLoading}>
              Cancel
            </button>
            <button type="submit" className="submit-btn" disabled={isLoading}>
              {isLoading ? 'Registering...' : 'Register'}
            </button>
          </div>
        </form>
      </div>

      <style jsx>{`
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.6);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          padding: 20px;
        }

        .modal-content {
          background: var(--bg-primary);
          border-radius: 12px;
          width: 100%;
          max-width: 500px;
          max-height: 90vh;
          overflow-y: auto;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }

        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 24px;
          border-bottom: 1px solid var(--bg-tertiary);
        }

        .modal-header h2 {
          font-size: 1.5rem;
          font-weight: 600;
          color: var(--text-primary);
          margin: 0;
        }

        .close-btn {
          background: none;
          border: none;
          font-size: 2rem;
          color: var(--text-secondary);
          cursor: pointer;
          padding: 0;
          width: 32px;
          height: 32px;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: color var(--transition-fast);
        }

        .close-btn:hover:not(:disabled) {
          color: var(--text-primary);
        }

        .close-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        form {
          padding: 24px;
        }

        .form-group {
          margin-bottom: 20px;
        }

        .form-group label {
          display: block;
          font-size: 0.9rem;
          font-weight: 500;
          color: var(--text-primary);
          margin-bottom: 8px;
        }

        .form-group input {
          width: 100%;
          padding: 10px 12px;
          font-size: 1rem;
          background: var(--bg-secondary);
          border: 2px solid var(--bg-tertiary);
          border-radius: 6px;
          color: var(--text-primary);
          transition: border-color var(--transition-fast);
          font-family: monospace;
          letter-spacing: 2px;
          text-transform: uppercase;
        }

        .form-group input:focus {
          outline: none;
          border-color: var(--accent-cyan);
        }

        .form-group input:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .form-group small {
          display: block;
          font-size: 0.8rem;
          color: var(--text-muted);
          margin-top: 4px;
        }

        .error-message {
          background: rgba(239, 68, 68, 0.1);
          color: var(--accent-pink);
          padding: 12px;
          border-radius: 6px;
          font-size: 0.9rem;
          margin-bottom: 20px;
        }

        .modal-actions {
          display: flex;
          gap: 12px;
          justify-content: flex-end;
          margin-top: 24px;
        }

        .cancel-btn,
        .submit-btn {
          padding: 10px 20px;
          font-size: 1rem;
          border-radius: 6px;
          cursor: pointer;
          transition: all var(--transition-fast);
          border: none;
        }

        .cancel-btn {
          background: var(--bg-tertiary);
          color: var(--text-secondary);
        }

        .cancel-btn:hover:not(:disabled) {
          background: var(--bg-secondary);
          color: var(--text-primary);
        }

        .submit-btn {
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          font-weight: 600;
        }

        .submit-btn:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 4px 20px rgba(255, 110, 180, 0.4);
        }

        .cancel-btn:disabled,
        .submit-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
      `}</style>
    </div>
  );
}

