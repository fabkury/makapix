import { useState } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { clearLoggedOutMarker } from '../lib/api';

interface AuthTokens {
  token: string;
  refresh_token?: string | null; // Optional - now stored in HttpOnly cookie, not returned in body
  user_id: number;
  user_key: string;
  public_sqid: string | null;
  user_handle: string | null;
  expires_at: string;
  needs_welcome?: boolean; // First login of a new account → show the welcome wizard once
}

type ApiErrorBody = {
  detail?: string | Array<{ msg?: string; loc?: (string | number)[] }>;
  error?: { message?: string; code?: string };
};

// Read a human message out of either the v1 envelope ({ error: { message } })
// or FastAPI's default ({ detail }), including the array-of-validation-errors form.
function parseApiError(data: ApiErrorBody | null | undefined, fallback: string): string {
  if (data && typeof data === 'object') {
    if (data.error && typeof data.error.message === 'string') return data.error.message;
    const detail = data.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((err) => {
          const field = err.loc && err.loc.length > 1 ? err.loc[err.loc.length - 1] : '';
          const msg = err.msg || 'Validation error';
          if (msg.includes('String should have at least 1 character')) {
            return field ? `${field} is required` : 'This field is required';
          }
          return field ? `${field}: ${msg}` : msg;
        })
        .join(', ');
    }
  }
  return fallback;
}

// Mirrors the server rules (auth.validate_password): >=8 chars, >=1 letter, >=1 digit.
// Client-side check is a fast backstop; the server stays authoritative (weak_password).
function validatePasswordRules(pw: string): string | null {
  if (pw.length < 8) return 'Password must be at least 8 characters long';
  if (!/[a-zA-Z]/.test(pw)) return 'Password must contain at least one letter';
  if (!/[0-9]/.test(pw)) return 'Password must contain at least one number';
  return null;
}

export type AuthPanelVariant = 'standalone' | 'embedded';

export default function AuthPanel({
  variant = 'standalone',
  showLogoSection = true,
}: {
  variant?: AuthPanelVariant;
  showLogoSection?: boolean;
}) {
  const router = useRouter();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // When set, we show the 6-digit code screen for this email (post-register, or
  // an unverified login). The chosen/typed `password` is reused to auto sign in.
  const [otpEmail, setOtpEmail] = useState<string | null>(null);
  const [code, setCode] = useState('');
  const [resendingCode, setResendingCode] = useState(false);
  const [codeResent, setCodeResent] = useState(false);

  const API_BASE_URL =
    typeof window !== 'undefined'
      ? process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin
      : '';

  const persistAuthAndRedirect = (data: AuthTokens) => {
    localStorage.setItem('access_token', data.token);
    clearLoggedOutMarker();
    localStorage.setItem('user_id', String(data.user_id));
    localStorage.setItem('user_key', data.user_key || '');
    localStorage.setItem('public_sqid', data.public_sqid || '');
    localStorage.setItem('user_handle', data.user_handle || '');
    // Dispatch custom event to trigger MQTT reconnection with new userId
    window.dispatchEvent(new Event('localStorageUpdated'));
    // First login of a new account → onboarding wizard (shown once; the page
    // itself redirects away once welcome_completed). Mirrors the OAuth path in
    // Layout.tsx and the native app.
    router.push(data.needs_welcome ? '/new-account-welcome' : '/');
  };

  const requestOtp = async (forEmail: string) => {
    await fetch(`${API_BASE_URL}/api/auth/email-otp/request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: forEmail }),
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedEmail = email.trim();
    const trimmedPassword = password.trim();

    if (!trimmedEmail) {
      setError('Email is required');
      return;
    }
    if (!trimmedPassword) {
      setError('Password is required');
      return;
    }
    if (mode === 'register') {
      const pwError = validatePasswordRules(trimmedPassword);
      if (pwError) {
        setError(pwError);
        return;
      }
    }

    setLoading(true);

    try {
      if (mode === 'register') {
        // Chosen-password flow: the server emails a single 6-digit code and we
        // verify in-page, matching the native app (no temp password, no link).
        const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: trimmedEmail, password: trimmedPassword }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: response.statusText }));
          throw new Error(parseApiError(errorData, 'Failed to register'));
        }

        // 201 (new) or 200 (resume) — either way a code was emailed.
        setCode('');
        setCodeResent(false);
        setOtpEmail(trimmedEmail);
      } else {
        const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
          method: 'POST',
          credentials: 'include', // CRITICAL: Include cookies to receive refresh token cookie
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: trimmedEmail, password: trimmedPassword }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: response.statusText }));
          const message = parseApiError(errorData, 'Failed to login');

          // Unverified account: send a fresh code and move to the verify step,
          // then we'll sign them in with the password they just entered.
          if (response.status === 403 && message.toLowerCase().includes('email not verified')) {
            await requestOtp(trimmedEmail).catch(() => {});
            setCode('');
            setCodeResent(false);
            setOtpEmail(trimmedEmail);
            setError(null);
            return;
          }

          throw new Error(message);
        }

        const data: AuthTokens = await response.json();
        persistAuthAndRedirect(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${mode}`);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!otpEmail) return;
    if (code.length !== 6) {
      setError('Enter the 6-digit code from your email');
      return;
    }

    setLoading(true);
    try {
      const verifyResponse = await fetch(`${API_BASE_URL}/api/auth/email-otp/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: otpEmail, code }),
      });

      if (!verifyResponse.ok) {
        const errorData = await verifyResponse.json().catch(() => ({ detail: verifyResponse.statusText }));
        throw new Error(parseApiError(errorData, 'Invalid or expired code'));
      }

      // Verified — sign in with the password the user just chose/typed.
      const loginResponse = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: otpEmail, password }),
      });

      if (!loginResponse.ok) {
        // Verified, but the auto sign-in failed — fall back to the login form.
        setOtpEmail(null);
        setMode('login');
        setEmail(otpEmail);
        setError('Email verified. Please sign in.');
        return;
      }

      const data: AuthTokens = await loginResponse.json();
      persistAuthAndRedirect(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed');
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    if (!otpEmail) return;
    setResendingCode(true);
    setCodeResent(false);
    try {
      await requestOtp(otpEmail);
      setCodeResent(true);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resend the code');
    } finally {
      setResendingCode(false);
    }
  };

  return (
    <div className={`auth-container ${variant}`}>
      {otpEmail ? (
        <div className="auth-card otp-card">
          {showLogoSection && (
            <div className="logo-section">
              <img src="/android-chrome-512x512.png" alt="Makapix Club" className="auth-logo" />
            </div>
          )}
          <div className="success-icon">✉️</div>
          <h2 className="otp-title">Enter your code</h2>
          <p className="otp-subtitle">
            We emailed a 6-digit code to <strong>{otpEmail}</strong>. Enter it to verify your account and sign in.
          </p>

          <form onSubmit={handleVerifyOtp} className="form">
            {codeResent && <div className="success-alert">A new code is on its way.</div>}
            {error && <div className="error-alert">{error}</div>}

            <div className="field">
              <label htmlFor="otp">6-digit code</label>
              <input
                id="otp"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]*"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000"
                className="otp-input"
              />
            </div>

            <button type="submit" disabled={loading || code.length !== 6} className="primary-button">
              {loading ? 'Verifying...' : 'Verify and sign in'}
            </button>
          </form>

          <div className="otp-actions">
            <button
              type="button"
              onClick={handleResendOtp}
              disabled={resendingCode}
              className="resend-link-button"
            >
              {resendingCode ? 'Sending...' : 'Resend the code'}
            </button>
            <button
              type="button"
              onClick={() => {
                setOtpEmail(null);
                setCode('');
                setError(null);
                setCodeResent(false);
              }}
              className="resend-link-button"
            >
              Use a different email
            </button>
          </div>
        </div>
      ) : (
        <div className="auth-card">
          {showLogoSection && (
            <div className="logo-section">
              <img src="/android-chrome-512x512.png" alt="Makapix Club" className="auth-logo" />
            </div>
          )}

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
            {error && <div className="error-alert">{error}</div>}

            <div className="field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                maxLength={255}
                placeholder="your@email.com"
              />
            </div>

            <div className="field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={mode === 'register' ? 8 : 1}
                placeholder={mode === 'register' ? 'Choose a password' : 'Enter your password'}
                autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              />
              {mode === 'register' && (
                <span className="field-hint">At least 8 characters, including a letter and a number.</span>
              )}
              {mode === 'login' && (
                <div className="help-links">
                  <Link href="/forgot-password" className="help-link">
                    Forgot your password?
                  </Link>
                </div>
              )}
            </div>

            <button type="submit" disabled={loading} className="primary-button">
              {loading ? 'Please wait...' : mode === 'login' ? 'Login' : 'Create Account'}
            </button>

            {mode === 'register' && (
              <p className="consent-note">
                By creating an account you agree to our{' '}
                <Link href="/privacy" className="consent-link">
                  Privacy Policy
                </Link>
                .
              </p>
            )}
          </form>

          <div className="divider">
            <span>or continue with</span>
          </div>

          <button
            onClick={() => {
              const apiBaseUrl =
                typeof window !== 'undefined' ? process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin : '';
              window.open(
                `${apiBaseUrl}/api/auth/github/login`,
                'oauth',
                'width=600,height=700,scrollbars=yes,resizable=yes'
              );
            }}
            className="github-button"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
            </svg>
            GitHub
          </button>
        </div>
      )}

      <style jsx>{`
        .auth-container.standalone {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 100%;
          padding: 24px;
        }

        .auth-container.embedded {
          display: block;
          padding: 0;
        }

        .auth-card,
        .success-card {
          width: 100%;
          max-width: 400px;
          background: var(--bg-secondary);
          border-radius: 16px;
          padding: 32px;
        }

        /* Standalone login/register page: make panel wider */
        .auth-container.standalone .auth-card,
        .auth-container.standalone .success-card {
          max-width: 520px;
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
        }

        .form > :global(* + *) {
          margin-top: 20px;
        }

        .field {
          display: flex;
          flex-direction: column;
        }

        .field > :global(* + *) {
          margin-top: 8px;
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
          margin-top: 8px;
        }

        .help-links > :global(* + *) {
          margin-top: 8px;
        }

        .help-link {
          font-size: 0.85rem;
          color: var(--accent-cyan);
          text-align: right;
        }

        .consent-note {
          margin: 12px 0 0 0;
          font-size: 0.8rem;
          color: var(--text-muted);
          text-align: center;
        }

        .consent-note :global(.consent-link) {
          color: var(--accent-cyan);
          text-decoration: none;
        }

        .consent-note :global(.consent-link:hover) {
          text-decoration: underline;
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

        .resend-link-button {
          background: none;
          border: none;
          color: var(--accent-cyan);
          font-size: 0.85rem;
          cursor: pointer;
          padding: 0;
          text-align: left;
        }

        .resend-link-button:hover:not(:disabled) {
          text-decoration: underline;
        }

        .resend-link-button:disabled {
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

        .divider::before {
          margin-right: 16px;
        }

        .divider::after {
          margin-left: 16px;
        }

        .github-button {
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 14px;
          background: #24292e;
          color: white;
          font-size: 1rem;
          font-weight: 600;
          border-radius: 10px;
          transition: all var(--transition-fast);
        }

        .github-button > :global(* + *) {
          margin-left: 10px;
        }

        .github-button:hover {
          background: #2f363d;
        }

        .otp-card {
          text-align: center;
        }

        .otp-card .form {
          text-align: left;
        }

        .success-icon {
          font-size: 4rem;
          margin-bottom: 16px;
        }

        .otp-title {
          font-size: 1.5rem;
          color: var(--text-primary);
          margin-bottom: 12px;
        }

        .otp-subtitle {
          color: var(--text-secondary);
          margin-bottom: 20px;
          font-size: 0.95rem;
        }

        .otp-input {
          text-align: center;
          letter-spacing: 0.4em;
          font-size: 1.4rem;
          font-variant-numeric: tabular-nums;
        }

        .otp-actions {
          display: flex;
          justify-content: space-between;
          margin-top: 16px;
        }
      `}</style>
    </div>
  );
}
