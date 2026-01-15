/**
 * ReputationPanel - Adjust user reputation with gamma-biased slider.
 * Range: -1000 to +1000
 * Requires minimum 8-character reason.
 */

import { useState, useCallback } from 'react';
import CollapsiblePanel from './CollapsiblePanel';
import { authenticatedFetch } from '../../lib/api';

interface ReputationPanelProps {
  sqid: string;
  currentReputation: number;
  onReputationChange: (newReputation: number) => void;
}

// Gamma bias for slider (1.5 makes middle range more sensitive)
const GAMMA = 1.5;

// Convert slider position (0-100) to reputation value (-1000 to +1000)
function sliderToReputation(sliderValue: number): number {
  if (sliderValue === 50) return 0;

  if (sliderValue > 50) {
    const posNormalized = (sliderValue - 50) / 50;
    const biased = Math.pow(posNormalized, GAMMA);
    return Math.round(biased * 1000);
  } else {
    const negNormalized = (50 - sliderValue) / 50;
    const biased = Math.pow(negNormalized, GAMMA);
    return -Math.round(biased * 1000);
  }
}

// Convert reputation value to slider position
function reputationToSlider(rep: number): number {
  if (rep === 0) return 50;

  if (rep > 0) {
    const normalized = rep / 1000;
    const unbiased = Math.pow(normalized, 1 / GAMMA);
    return 50 + unbiased * 50;
  } else {
    const normalized = Math.abs(rep) / 1000;
    const unbiased = Math.pow(normalized, 1 / GAMMA);
    return 50 - unbiased * 50;
  }
}

export default function ReputationPanel({ sqid, currentReputation, onReputationChange }: ReputationPanelProps) {
  const [delta, setDelta] = useState(0);
  const [sliderValue, setSliderValue] = useState(50);
  const [reason, setReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSliderChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value);
    setSliderValue(value);
    setDelta(sliderToReputation(value));
  }, []);

  const handleIncrement = useCallback(() => {
    const newDelta = Math.min(1000, delta + 1);
    setDelta(newDelta);
    setSliderValue(reputationToSlider(newDelta));
  }, [delta]);

  const handleDecrement = useCallback(() => {
    const newDelta = Math.max(-1000, delta - 1);
    setDelta(newDelta);
    setSliderValue(reputationToSlider(newDelta));
  }, [delta]);

  const handleSubmit = async () => {
    if (reason.length < 8 || delta === 0) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const response = await authenticatedFetch(`${apiBaseUrl}/api/admin/user/${sqid}/reputation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ delta, reason }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to adjust reputation');
      }

      const data = await response.json();
      onReputationChange(data.new_total);

      // Reset form
      setDelta(0);
      setSliderValue(50);
      setReason('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to adjust reputation');
    } finally {
      setIsSubmitting(false);
    }
  };

  const isDisabled = reason.length < 8 || delta === 0 || isSubmitting;
  const isPositive = delta >= 0;

  return (
    <CollapsiblePanel title="Reputation">
      <div className="reputation-panel">
        <div className="current-rep">
          Current reputation: <span className={currentReputation >= 0 ? 'positive' : 'negative'}>
            {currentReputation > 0 ? '+' : ''}{currentReputation}
          </span>
        </div>

        <div className="slider-section">
          <div className="slider-header">
            <label>
              Change: <span className={isPositive ? 'positive' : 'negative'}>
                {delta > 0 ? '+' : ''}{delta}
              </span>
            </label>
            <div className="increment-buttons">
              <button onClick={handleDecrement} disabled={delta <= -1000} title="Decrease by 1">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="m18 15-6-6-6 6" />
                </svg>
              </button>
              <button onClick={handleIncrement} disabled={delta >= 1000} title="Increase by 1">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="m6 9 6 6 6-6" />
                </svg>
              </button>
            </div>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            step="0.1"
            value={sliderValue}
            onChange={handleSliderChange}
            className="rep-slider"
          />
          <div className="slider-labels">
            <span>-1000</span>
            <span>0</span>
            <span>+1000</span>
          </div>
        </div>

        <div className="reason-section">
          <label>Reason {reason.length < 8 && <span className="hint">(min 8 characters)</span>}</label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Enter reason for reputation change..."
            rows={3}
          />
          <div className="char-count">{reason.length} / 8 characters</div>
        </div>

        {error && <div className="error">{error}</div>}

        <button
          onClick={handleSubmit}
          disabled={isDisabled}
          className={`submit-btn ${isPositive ? 'grant' : 'remove'}`}
        >
          {isSubmitting ? 'Submitting...' : isPositive ? 'Grant' : 'Remove'}
        </button>
      </div>

      <style jsx>{`
        .reputation-panel {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .current-rep {
          font-size: 0.9rem;
          color: var(--text-secondary);
        }
        .positive { color: var(--accent-cyan); }
        .negative { color: var(--accent-pink); }
        .slider-section {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .slider-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .slider-header label {
          font-size: 0.9rem;
          color: var(--text-secondary);
        }
        .increment-buttons {
          display: flex;
          gap: 12px;
        }
        .increment-buttons button {
          background: transparent;
          border: none;
          padding: 4px;
          cursor: pointer;
          color: var(--text-secondary);
          border-radius: 4px;
          transition: background 0.15s ease;
        }
        .increment-buttons button:hover:not(:disabled) {
          background: rgba(255, 255, 255, 0.1);
        }
        .increment-buttons button:disabled {
          opacity: 0.3;
          cursor: not-allowed;
        }
        .increment-buttons button:first-child svg {
          color: var(--accent-pink);
        }
        .increment-buttons button:last-child svg {
          color: var(--accent-cyan);
        }
        .rep-slider {
          width: 100%;
          height: 8px;
          background: var(--bg-tertiary);
          border-radius: 4px;
          -webkit-appearance: none;
          appearance: none;
          cursor: pointer;
        }
        .rep-slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          width: 18px;
          height: 18px;
          background: var(--text-primary);
          border-radius: 50%;
          border: 2px solid var(--accent-cyan);
          cursor: pointer;
        }
        .slider-labels {
          display: flex;
          justify-content: space-between;
          font-size: 0.75rem;
          color: var(--text-muted);
        }
        .reason-section {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .reason-section label {
          font-size: 0.9rem;
          color: var(--text-secondary);
        }
        .hint {
          color: var(--text-muted);
          font-size: 0.8rem;
        }
        textarea {
          width: 100%;
          padding: 12px;
          background: var(--bg-tertiary);
          border: 1px solid var(--border-color);
          border-radius: 6px;
          color: var(--text-primary);
          font-size: 0.9rem;
          resize: none;
        }
        textarea::placeholder {
          color: var(--text-muted);
        }
        textarea:focus {
          outline: none;
          border-color: var(--accent-cyan);
          box-shadow: 0 0 0 2px rgba(0, 212, 255, 0.2);
        }
        .char-count {
          font-size: 0.75rem;
          color: var(--text-muted);
        }
        .error {
          color: var(--accent-pink);
          font-size: 0.85rem;
        }
        .submit-btn {
          width: 100%;
          padding: 12px;
          border: none;
          border-radius: 6px;
          font-size: 0.95rem;
          font-weight: 600;
          cursor: pointer;
          transition: background 0.15s ease, opacity 0.15s ease;
        }
        .submit-btn:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }
        .submit-btn.grant {
          background: var(--accent-cyan);
          color: #000;
        }
        .submit-btn.grant:hover:not(:disabled) {
          background: #00e5ff;
        }
        .submit-btn.remove {
          background: var(--accent-pink);
          color: #000;
        }
        .submit-btn.remove:hover:not(:disabled) {
          background: #ff6090;
        }
      `}</style>
    </CollapsiblePanel>
  );
}
