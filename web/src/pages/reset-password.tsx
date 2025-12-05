import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Layout from '../components/Layout';
import { validatePassword } from '../utils/passwordValidation';

export default function ResetPasswordPage() {
  const router = useRouter();
  const { token } = router.query;
  
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  useEffect(() => {
    if (router.isReady && !token) {
      router.push('/forgot-password');
    }
  }, [router, token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validate password
    const validation = validatePassword(newPassword);
    if (!validation.isValid) {
      setError(validation.errors.join(' '));
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/reset-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          token: token as string,
          new_password: newPassword,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        // Handle both string and array error formats from FastAPI
        let errorMessage = 'Failed to reset password';
        if (typeof errorData.detail === 'string') {
          errorMessage = errorData.detail;
        } else if (Array.isArray(errorData.detail) && errorData.detail.length > 0) {
          // Pydantic validation errors come as an array of objects with 'msg' field
          errorMessage = errorData.detail.map((e: { msg?: string }) => e.msg || 'Validation error').join('. ');
        }
        throw new Error(errorMessage);
      }

      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (!token && router.isReady) {
    return null;
  }

  return (
    <Layout title="Set New Password">
      <div className="page-container">
        {success ? (
          <div className="card">
            <div className="icon">✅</div>
            <h2>Password Reset Complete</h2>
            <p className="message">
              Your password has been successfully reset. 
              You can now log in with your new password.
            </p>
            <Link href="/auth" className="primary-button">
              Go to Login
            </Link>
          </div>
        ) : (
          <div className="card">
            <h2>Set New Password</h2>
            <p className="description">
              Password must be at least 8 characters with at least one letter and one number.
            </p>

            <form onSubmit={handleSubmit} className="form">
              {error && <div className="error-alert">{error}</div>}

              <div className="field">
                <label htmlFor="newPassword">New Password</label>
                <input
                  id="newPassword"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={8}
                  placeholder="Enter new password"
                  autoFocus
                />
              </div>

              <div className="field">
                <label htmlFor="confirmPassword">Confirm Password</label>
                <input
                  id="confirmPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  minLength={8}
                  placeholder="Confirm new password"
                />
              </div>

              <button type="submit" disabled={loading} className="primary-button">
                {loading ? 'Resetting...' : 'Reset Password'}
              </button>
            </form>

            <div className="link-section">
              <p className="expire-note">
                This link expires in 1 hour. If it has expired, 
                you can <Link href="/forgot-password" className="text-link">request a new one</Link>.
              </p>
            </div>
          </div>
        )}
      </div>

      <style jsx>{`
        .page-container {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: calc(100vh - var(--header-height));
          padding: 24px;
        }

        .card {
          width: 100%;
          max-width: 420px;
          background: var(--bg-secondary);
          border-radius: 16px;
          padding: 32px;
          text-align: center;
        }

        .icon {
          font-size: 3.5rem;
          margin-bottom: 16px;
        }

        h2 {
          font-size: 1.5rem;
          color: var(--text-primary);
          margin-bottom: 12px;
        }

        .description,
        .message {
          color: var(--text-secondary);
          margin-bottom: 24px;
          line-height: 1.5;
        }

        .form {
          display: flex;
          flex-direction: column;
          gap: 20px;
          text-align: left;
        }

        .field {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .field label {
          font-size: 0.9rem;
          font-weight: 500;
          color: var(--text-secondary);
        }

        .field input {
          padding: 14px 16px;
          font-size: 1rem;
        }

        .error-alert {
          padding: 12px 16px;
          background: rgba(239, 68, 68, 0.15);
          border: 1px solid rgba(239, 68, 68, 0.3);
          border-radius: 8px;
          color: #f87171;
          font-size: 0.9rem;
        }

        .primary-button {
          display: block;
          width: 100%;
          padding: 14px;
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          font-size: 1rem;
          font-weight: 600;
          border-radius: 10px;
          border: none;
          cursor: pointer;
          text-align: center;
          text-decoration: none;
          transition: all var(--transition-fast);
        }

        .primary-button:hover:not(:disabled) {
          box-shadow: 0 0 20px rgba(255, 110, 180, 0.4);
        }

        .primary-button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .link-section {
          margin-top: 24px;
          padding-top: 24px;
          border-top: 1px solid rgba(255, 255, 255, 0.1);
        }

        .expire-note {
          font-size: 0.9rem;
          color: var(--text-muted);
          margin: 0;
        }

        .text-link {
          color: var(--accent-cyan);
        }
      `}</style>
    </Layout>
  );
}
