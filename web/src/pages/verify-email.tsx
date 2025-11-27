import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Layout from '../components/Layout';

interface VerifyResponse {
  message: string;
  verified: boolean;
  handle: string;
  can_change_password: boolean;
  can_change_handle: boolean;
}

export default function VerifyEmailPage() {
  const router = useRouter();
  const { token } = router.query;
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState<string>('');
  const [verifyData, setVerifyData] = useState<VerifyResponse | null>(null);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  useEffect(() => {
    const verifyEmail = async () => {
      if (!token || typeof token !== 'string') {
        if (router.isReady && !token) {
          setStatus('error');
          setMessage('Missing verification token');
        }
        return;
      }

      try {
        const response = await fetch(
          `${API_BASE_URL}/api/auth/verify-email?token=${encodeURIComponent(token)}`
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: 'Verification failed' }));
          throw new Error(errorData.detail || 'Verification failed');
        }

        const data: VerifyResponse = await response.json();
        setStatus('success');
        setMessage(data.message);
        setVerifyData(data);
      } catch (err) {
        setStatus('error');
        setMessage(err instanceof Error ? err.message : 'Verification failed');
      }
    };

    verifyEmail();
  }, [token, router.isReady, API_BASE_URL]);

  return (
    <Layout title="Email Verification">
      <div className="page-container">
        <div className="card">
          {status === 'loading' && (
            <>
              <div className="icon loading">⏳</div>
              <h2>Verifying Your Email</h2>
              <p className="message">Please wait while we verify your email address...</p>
            </>
          )}

          {status === 'success' && (
            <>
              <div className="icon success">✅</div>
              <h2>Email Verified!</h2>
              <p className="message">{message}</p>
              
              {verifyData && (
                <div className="info-box">
                  <p className="info-text">
                    Your handle: <strong>@{verifyData.handle}</strong>
                  </p>
                  <p className="info-hint">
                    You can change your password and handle after logging in.
                  </p>
                </div>
              )}
              
              <Link href="/auth" className="primary-button">
                Go to Login
              </Link>
            </>
          )}

          {status === 'error' && (
            <>
              <div className="icon error">❌</div>
              <h2>Verification Failed</h2>
              <p className="error-message">{message}</p>
              <p className="hint">
                The verification link may have expired or already been used.
              </p>
              <div className="actions">
                <Link href="/auth" className="primary-button">
                  Go to Login
                </Link>
              </div>
            </>
          )}
        </div>
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
          max-width: 450px;
          background: var(--bg-secondary);
          border-radius: 16px;
          padding: 40px 32px;
          text-align: center;
        }

        .icon {
          font-size: 4rem;
          margin-bottom: 20px;
        }

        .icon.loading {
          animation: pulse 1.5s ease-in-out infinite;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }

        h2 {
          font-size: 1.5rem;
          color: var(--text-primary);
          margin-bottom: 12px;
        }

        .message {
          color: var(--text-secondary);
          margin-bottom: 24px;
          line-height: 1.5;
        }

        .error-message {
          color: #f87171;
          margin-bottom: 12px;
        }

        .hint {
          font-size: 0.9rem;
          color: var(--text-muted);
          margin-bottom: 24px;
        }

        .info-box {
          background: var(--bg-tertiary);
          border-radius: 12px;
          padding: 16px;
          margin-bottom: 24px;
        }

        .info-text {
          font-size: 1rem;
          color: var(--text-primary);
          margin: 0;
        }

        .info-hint {
          font-size: 0.85rem;
          color: var(--text-muted);
          margin: 8px 0 0 0;
        }

        .primary-button {
          display: inline-block;
          padding: 14px 32px;
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          font-size: 1rem;
          font-weight: 600;
          border-radius: 10px;
          text-decoration: none;
          transition: all var(--transition-fast);
        }

        .primary-button:hover {
          box-shadow: 0 0 20px rgba(255, 110, 180, 0.4);
        }

        .actions {
          display: flex;
          justify-content: center;
          gap: 12px;
          flex-wrap: wrap;
        }
      `}</style>
    </Layout>
  );
}
