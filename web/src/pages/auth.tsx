import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Layout from '../components/Layout';

interface AuthTokens {
  token: string;
  refresh_token?: string;
  user_id: string;
  expires_at: string;
}

interface RegisterResponse {
  message: string;
  user_id: string;
  email: string;
  handle: string;
}

export default function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [registrationSuccess, setRegistrationSuccess] = useState<RegisterResponse | null>(null);
  const [emailNotVerified, setEmailNotVerified] = useState(false);
  const [resendingVerification, setResendingVerification] = useState(false);
  const [verificationResent, setVerificationResent] = useState(false);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  // Check if already logged in
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      router.push('/');
    }
  }, [router]);

  // Listen for OAuth success message from popup
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      // Verify message origin for security (in production, check against your domain)
      if (event.data && event.data.type === 'OAUTH_SUCCESS') {
        const { tokens } = event.data;
        if (tokens) {
          localStorage.setItem('access_token', tokens.access_token);
          localStorage.setItem('refresh_token', tokens.refresh_token || '');
          localStorage.setItem('user_id', tokens.user_id);
          localStorage.setItem('user_handle', tokens.user_handle || '');
          
          // Reload the page to update authentication state
          window.location.reload();
        }
      }
    };

    window.addEventListener('message', handleMessage);
    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setEmailNotVerified(false);
    setVerificationResent(false);
    
    // Trim and validate inputs
    const trimmedEmail = email.trim();
    const trimmedPassword = password.trim();
    
    // Client-side validation
    if (!trimmedEmail) {
      setError('Email is required');
      return;
    }
    
    if (mode === 'login' && !trimmedPassword) {
      setError('Password is required');
      return;
    }
    
    setLoading(true);

    try {
      if (mode === 'register') {
        const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ email: trimmedEmail }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: response.statusText }));
          let errorMessage = 'Failed to register';
          
          // Handle FastAPI validation errors (array of error objects)
          if (Array.isArray(errorData.detail)) {
            const messages = errorData.detail.map((err: { msg?: string; loc?: (string | number)[]; type?: string }) => {
              const field = err.loc && err.loc.length > 1 ? err.loc[err.loc.length - 1] : '';
              const msg = err.msg || 'Validation error';
              
              if (msg.includes('String should have at least 1 character')) {
                return field ? `${field} is required` : 'This field is required';
              }
              
              return field ? `${field}: ${msg}` : msg;
            });
            errorMessage = messages.join(', ');
          } else if (typeof errorData.detail === 'string') {
            errorMessage = errorData.detail;
          }
          
          throw new Error(errorMessage);
        }

        const data: RegisterResponse = await response.json();
        setRegistrationSuccess(data);
      } else {
        const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ email: trimmedEmail, password: trimmedPassword }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: response.statusText }));
          let errorMessage = 'Failed to login';
          
          // Handle FastAPI validation errors (array of error objects)
          if (Array.isArray(errorData.detail)) {
            const messages = errorData.detail.map((err: { msg?: string; loc?: (string | number)[]; type?: string }) => {
              // Extract field name from location if available
              const field = err.loc && err.loc.length > 1 ? err.loc[err.loc.length - 1] : '';
              const msg = err.msg || 'Validation error';
              
              // Provide user-friendly messages for common validation errors
              if (msg.includes('String should have at least 1 character')) {
                return field ? `${field} is required` : 'This field is required';
              }
              
              return field ? `${field}: ${msg}` : msg;
            });
            errorMessage = messages.join(', ');
          } else if (typeof errorData.detail === 'string') {
            errorMessage = errorData.detail;
          }
          
          // Check if the error is about email not being verified
          if (response.status === 403 && errorMessage.toLowerCase().includes('email not verified')) {
            setEmailNotVerified(true);
          }
          
          throw new Error(errorMessage);
        }

        const data: AuthTokens = await response.json();
        localStorage.setItem('access_token', data.token);
        if (data.refresh_token) {
          localStorage.setItem('refresh_token', data.refresh_token);
        }
        localStorage.setItem('user_id', data.user_id);
        router.push('/');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${mode}`);
    } finally {
      setLoading(false);
    }
  };

  const handleResendVerification = async () => {
    setResendingVerification(true);
    setVerificationResent(false);

    try {
      // Use the unauthenticated endpoint for resending verification
      const response = await fetch(`${API_BASE_URL}/api/auth/request-verification`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(errorData.detail || 'Failed to resend verification email');
      }

      setVerificationResent(true);
      setError(null);
      setEmailNotVerified(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resend verification email');
    } finally {
      setResendingVerification(false);
    }
  };

  return (
    <Layout title={mode === 'login' ? 'Login' : 'Register'}>
      <div className="auth-container">
        {registrationSuccess ? (
          <div className="success-card">
            <div className="success-icon">✉️</div>
            <h2>Check Your Email</h2>
            <p className="success-message">{registrationSuccess.message}</p>
            <div className="credentials">
              <div className="credential-item">
                <span className="credential-label">Email</span>
                <span className="credential-value">{registrationSuccess.email}</span>
              </div>
              <div className="credential-item">
                <span className="credential-label">Handle</span>
                <span className="credential-value">{registrationSuccess.handle}</span>
              </div>
            </div>
            <p className="hint">
              We&apos;ve sent you an email with your temporary password.
              After verification, you can change your password.
            </p>
            <button
              onClick={() => {
                setRegistrationSuccess(null);
                setMode('login');
                setEmail(registrationSuccess.email);
              }}
              className="primary-button"
            >
              Go to Login
            </button>
          </div>
        ) : (
          <div className="auth-card">
            <div className="logo-section">
              <img src="/logo.png" alt="Makapix Club" className="auth-logo" />
            </div>

            <div className="tabs">
              <button
                className={`tab ${mode === 'login' ? 'active' : ''}`}
                onClick={() => {
                  setMode('login');
                  setError(null);
                }}
              >
                Login
              </button>
              <button
                className={`tab ${mode === 'register' ? 'active' : ''}`}
                onClick={() => {
                  setMode('register');
                  setError(null);
                }}
              >
                Register
              </button>
            </div>

            <form onSubmit={handleSubmit} className="form">
              {verificationResent && (
                <div className="success-alert">
                  Verification email sent! Please check your inbox.
                </div>
              )}
              {error && (
                <div className="error-alert">
                  {error}
                  {emailNotVerified && (
                    <div className="resend-section">
                      <button
                        type="button"
                        onClick={handleResendVerification}
                        disabled={resendingVerification}
                        className="resend-button"
                      >
                        {resendingVerification ? 'Sending...' : 'Resend verification email'}
                      </button>
                    </div>
                  )}
                </div>
              )}

              <div className="field">
                <label htmlFor="email">Email</label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  maxLength={255}
                  placeholder="your@email.com"
                />
                {mode === 'register' && (
                  <span className="field-hint">
                    A password will be sent to this email
                  </span>
                )}
              </div>

              {mode === 'login' && (
                <div className="field">
                  <label htmlFor="password">Password</label>
                  <input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={1}
                    placeholder="Enter your password"
                  />
                  <div className="help-links">
                    <Link href="/forgot-password" className="help-link">
                      Forgot your password?
                    </Link>
                  </div>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="primary-button"
              >
                {loading 
                  ? 'Please wait...' 
                  : mode === 'login' 
                    ? 'Login' 
                    : 'Create Account'
                }
              </button>
            </form>

            <div className="divider">
              <span>or continue with</span>
            </div>

            <button
              onClick={() => {
                const apiBaseUrl = typeof window !== 'undefined' 
                  ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
                  : '';
                window.open(`${apiBaseUrl}/api/auth/github/login`, 'oauth', 'width=600,height=700,scrollbars=yes,resizable=yes');
              }}
              className="github-button"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
              </svg>
              GitHub
            </button>
          </div>
        )}
      </div>

      <style jsx>{`
        .auth-container {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: calc(100vh - var(--header-height));
          padding: 24px;
        }

        .auth-card,
        .success-card {
          width: 100%;
          max-width: 400px;
          background: var(--bg-secondary);
          border-radius: 16px;
          padding: 32px;
        }

        .logo-section {
          display: flex;
          justify-content: center;
          margin-bottom: 24px;
        }

        .auth-logo {
          width: 80px;
          height: 80px;
          border-radius: 50%;
          object-fit: cover;
        }

        .tabs {
          display: flex;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
          margin-bottom: 24px;
        }

        .tab {
          flex: 1;
          padding: 12px;
          background: transparent;
          color: var(--text-muted);
          font-size: 1rem;
          font-weight: 500;
          border-bottom: 2px solid transparent;
          transition: all var(--transition-fast);
        }

        .tab:hover {
          color: var(--text-secondary);
        }

        .tab.active {
          color: var(--accent-cyan);
          border-bottom-color: var(--accent-cyan);
        }

        .form {
          display: flex;
          flex-direction: column;
          gap: 20px;
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

        .field-hint {
          font-size: 0.8rem;
          color: var(--text-muted);
        }

        .help-links {
          display: flex;
          flex-direction: column;
          gap: 6px;
          margin-top: 4px;
        }

        .help-link {
          font-size: 0.85rem;
          color: var(--accent-cyan);
          text-align: right;
        }

        .error-alert {
          padding: 12px 16px;
          background: rgba(239, 68, 68, 0.15);
          border: 1px solid rgba(239, 68, 68, 0.3);
          border-radius: 8px;
          color: #f87171;
          font-size: 0.9rem;
        }

        .success-alert {
          padding: 12px 16px;
          background: rgba(34, 197, 94, 0.15);
          border: 1px solid rgba(34, 197, 94, 0.3);
          border-radius: 8px;
          color: #4ade80;
          font-size: 0.9rem;
        }

        .resend-section {
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid rgba(239, 68, 68, 0.2);
        }

        .resend-button {
          width: 100%;
          padding: 10px 16px;
          background: transparent;
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: 6px;
          color: var(--text-secondary);
          font-size: 0.9rem;
          font-weight: 500;
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .resend-button:hover:not(:disabled) {
          background: rgba(255, 255, 255, 0.05);
          border-color: var(--accent-cyan);
          color: var(--accent-cyan);
        }

        .resend-button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .primary-button {
          padding: 14px;
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          font-size: 1rem;
          font-weight: 600;
          border-radius: 10px;
          transition: all var(--transition-fast);
        }

        .primary-button:hover:not(:disabled) {
          box-shadow: 0 0 20px rgba(255, 110, 180, 0.4);
          transform: translateY(-1px);
        }

        .primary-button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .divider {
          display: flex;
          align-items: center;
          gap: 16px;
          margin: 24px 0;
          color: var(--text-muted);
          font-size: 0.85rem;
        }

        .divider::before,
        .divider::after {
          content: '';
          flex: 1;
          height: 1px;
          background: rgba(255, 255, 255, 0.1);
        }

        .github-button {
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 10px;
          padding: 14px;
          background: #24292e;
          color: white;
          font-size: 1rem;
          font-weight: 600;
          border-radius: 10px;
          transition: all var(--transition-fast);
        }

        .github-button:hover {
          background: #2f363d;
        }

        /* Success card styles */
        .success-card {
          text-align: center;
        }

        .success-icon {
          font-size: 4rem;
          margin-bottom: 16px;
        }

        .success-card h2 {
          font-size: 1.5rem;
          color: var(--text-primary);
          margin-bottom: 12px;
        }

        .success-message {
          color: var(--text-secondary);
          margin-bottom: 20px;
        }

        .credentials {
          background: var(--bg-tertiary);
          border-radius: 10px;
          padding: 16px;
          margin-bottom: 20px;
          text-align: left;
        }

        .credential-item {
          display: flex;
          justify-content: space-between;
          padding: 8px 0;
        }

        .credential-item:not(:last-child) {
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .credential-label {
          color: var(--text-muted);
          font-size: 0.9rem;
        }

        .credential-value {
          color: var(--text-primary);
          font-weight: 500;
        }

        .hint {
          font-size: 0.85rem;
          color: var(--text-muted);
          margin-bottom: 20px;
        }
      `}</style>
    </Layout>
  );
}
