import { useEffect, useState } from "react";
import { getMe, setAvatarFromPost } from "../lib/api";

interface UseAsAvatarDialogProps {
  postSqid: string;
  artUrl: string;
  open: boolean;
  onClose: () => void;
}

/**
 * Confirmation dialog for "Use as profile photo" (docs/avatar-from-post/).
 * Shows the artwork rendered as an avatar next to the current user's handle —
 * exactly how it will appear once set — then calls the from-post endpoint.
 * On success, syncs localStorage and dispatches `makapix:user-updated` so the
 * navbar avatar refreshes live.
 */
export default function UseAsAvatarDialog({
  postSqid,
  artUrl,
  open,
  onClose,
}: UseAsAvatarDialogProps) {
  const [handle, setHandle] = useState<string | null>(null);
  const [userKey, setUserKey] = useState<string | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  // Fetch the current user's handle + user_key each time the dialog opens
  // (localStorage doesn't store either).
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setHandle(null);
    setUserKey(null);
    setLoadFailed(false);
    setError(null);
    setDone(false);
    setSubmitting(false);
    getMe()
      .then((me) => {
        if (cancelled) return;
        if (me.user?.handle && me.user?.user_key) {
          setHandle(me.user.handle);
          setUserKey(me.user.user_key);
        } else {
          setLoadFailed(true);
        }
      })
      .catch(() => {
        if (!cancelled) setLoadFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  if (!open) return null;

  const handleConfirm = async () => {
    if (!userKey || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const updated = await setAvatarFromPost(userKey, postSqid);
      const avatarUrl = updated.avatar_url ?? null;
      try {
        if (avatarUrl) localStorage.setItem("avatar_url", avatarUrl);
        else localStorage.removeItem("avatar_url");
      } catch {
        // ignore storage failures
      }
      window.dispatchEvent(
        new CustomEvent("makapix:user-updated", {
          detail: { avatar_url: avatarUrl },
        }),
      );
      setDone(true);
    } catch (e) {
      const err = e as Error & { status?: number };
      if (err.status === 429) {
        setError(
          "You're changing your profile photo too fast — try again later.",
        );
      } else {
        setError(
          err.message || "Could not set your profile photo. Please try again.",
        );
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{done ? "Profile photo updated" : "Use as profile photo?"}</h2>
          <button
            className="close-btn"
            onClick={onClose}
            disabled={submitting}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="modal-body">
          {done ? (
            <>
              <p className="intro">This artwork is now your profile photo.</p>
              <div className="modal-actions">
                <button type="button" className="submit-btn" onClick={onClose}>
                  Done
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="intro">
                Here&apos;s how your profile will look with this artwork as your
                photo:
              </p>

              <div className="preview-row">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img className="preview-avatar" src={artUrl} alt="" />
                <span className="preview-handle">
                  {loadFailed ? "you" : (handle ?? "…")}
                </span>
              </div>

              {loadFailed && (
                <div className="error-message">
                  Could not load your profile. Please try again.
                </div>
              )}
              {error && <div className="error-message">{error}</div>}

              <div className="modal-actions">
                <button
                  type="button"
                  className="cancel-btn"
                  onClick={onClose}
                  disabled={submitting}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="submit-btn"
                  onClick={handleConfirm}
                  disabled={submitting || !userKey}
                >
                  {submitting ? "Setting…" : "Set profile photo"}
                </button>
              </div>
            </>
          )}
        </div>
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
          z-index: 21000;
          padding: 20px;
        }

        .modal-content {
          background: var(--bg-primary);
          border-radius: 12px;
          width: 100%;
          max-width: 420px;
          max-height: 90vh;
          overflow-y: auto;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }

        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 20px 24px;
          border-bottom: 1px solid var(--bg-tertiary);
        }

        .modal-header h2 {
          font-size: 1.35rem;
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

        .modal-body {
          padding: 24px;
        }

        .intro {
          color: var(--text-secondary);
          font-size: 0.9rem;
          margin: 0 0 16px 0;
          line-height: 1.5;
        }

        .preview-row {
          display: flex;
          align-items: center;
          background: var(--bg-secondary);
          border-radius: 8px;
          padding: 12px 16px;
        }

        .preview-avatar {
          width: 32px;
          height: 32px;
          border-radius: 0;
          object-fit: cover;
          image-rendering: pixelated;
          flex-shrink: 0;
        }

        .preview-handle {
          margin-left: 12px;
          font-size: 14px;
          font-weight: 500;
          color: var(--text-primary);
        }

        .error-message {
          background: rgba(239, 68, 68, 0.1);
          color: var(--accent-pink);
          padding: 12px;
          border-radius: 6px;
          font-size: 0.9rem;
          margin-top: 16px;
        }

        .modal-actions {
          display: flex;
          justify-content: flex-end;
          margin-top: 24px;
        }

        .modal-actions > :global(* + *) {
          margin-left: 12px;
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
          background: linear-gradient(
            135deg,
            var(--accent-pink),
            var(--accent-purple)
          );
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
