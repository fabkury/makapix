import { useState } from 'react';
import Link from 'next/link';
import Layout from '../components/Layout';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/forgot-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(errorData.detail || 'Failed to request password reset');
      }

      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout title="Reset Password">
      <div className="page-container">
        {success ? (
          <div className="card">
            <div className="icon">📧</div>
            <h2>Check Your Email</h2>
            <p className="message">
              If an account exists with the email <strong>{email}</strong>, 
              we&apos;ve sent a password reset link.
            </p>
            <p className="hint">
              The link will expire in 1 hour. If you don&apos;t see the email, 
              check your spam folder.
            </p>
            <Link href="/auth" className="primary-button">
              Back to Login
            </Link>
          </div>
        ) : (
          <div className="card">
            <h2>Reset Your Password</h2>
            <p className="description">
              Enter the email address associated with your account, 
              and we&apos;ll send you a link to reset your password.
            </p>

            <form onSubmit={handleSubmit} className="form">
              {error && <div className="error-alert">{error}</div>}

              <div className="field">
                <label htmlFor="email">Email Address</label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="your@email.com"
                  autoFocus
                />
              </div>

              <button type="submit" disabled={loading} className="primary-button">
                {loading ? 'Sending...' : 'Send Reset Link'}
              </button>
            </form>

            <div className="link-section">
              <Link href="/auth" className="back-link">← Back to Login</Link>
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

        .hint {
          font-size: 0.9rem;
          color: var(--text-muted);
          margin-bottom: 24px;
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

        .back-link {
          color: var(--accent-cyan);
          font-size: 0.95rem;
        }
      `}</style>
    </Layout>
  );
}
