import { useState, useEffect } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import Link from 'next/link';

interface AuthTokens {
  token: string;
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
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
    : '';

  // Check if already logged in
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      router.push('/');
    }
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (mode === 'register') {
        // Registration - only needs email
        const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ email }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: response.statusText }));
          throw new Error(errorData.detail || 'Failed to register');
        }

        const data: RegisterResponse = await response.json();
        setRegistrationSuccess(data);
      } else {
        // Login - email and password
        const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ email, password }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ detail: response.statusText }));
          throw new Error(errorData.detail || 'Failed to login');
        }

        const data: AuthTokens = await response.json();
        localStorage.setItem('access_token', data.token);
        localStorage.setItem('user_id', data.user_id);
        router.push('/');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${mode}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Head>
        <title>{mode === 'login' ? 'Login' : 'Register'} - Makapix</title>
      </Head>
      <div style={styles.container}>
        <header style={styles.header}>
          <h1 style={styles.title}>Makapix</h1>
          <nav style={styles.nav}>
            <Link href="/" style={styles.navLink}>Home</Link>
          </nav>
        </header>

        <main style={styles.main}>
          {registrationSuccess ? (
            <div style={styles.successBox}>
              <div style={styles.successIcon}>✉️</div>
              <h2 style={styles.successTitle}>Check Your Email</h2>
              <p style={styles.successMessage}>{registrationSuccess.message}</p>
              <div style={styles.credentialsBox}>
                <p style={styles.credentialsLabel}>Your account:</p>
                <p style={styles.credentialsValue}>
                  <strong>Email:</strong> {registrationSuccess.email}
                </p>
                <p style={styles.credentialsValue}>
                  <strong>Handle:</strong> {registrationSuccess.handle}
                </p>
              </div>
              <p style={styles.successHint}>
                We've sent you an email with your temporary password and a verification link.
                Click the link to verify your account, then log in with your email and password.
              </p>
              <p style={styles.successHint}>
                After verification, you can change your password and handle.
              </p>
              <button
                onClick={() => {
                  setRegistrationSuccess(null);
                  setMode('login');
                  setEmail(registrationSuccess.email);
                }}
                style={styles.backToLogin}
              >
                Go to Login
              </button>
            </div>
          ) : (
          <div style={styles.authBox}>
            <div style={styles.tabs}>
              <button
                style={{
                  ...styles.tab,
                  ...(mode === 'login' ? styles.tabActive : {}),
                }}
                onClick={() => {
                  setMode('login');
                  setError(null);
                }}
              >
                Login
              </button>
              <button
                style={{
                  ...styles.tab,
                  ...(mode === 'register' ? styles.tabActive : {}),
                }}
                onClick={() => {
                  setMode('register');
                  setError(null);
                }}
              >
                Register
              </button>
            </div>

            <form onSubmit={handleSubmit} style={styles.form}>
              {error && (
                <div style={styles.error}>
                  {error}
                </div>
              )}

              <div style={styles.field}>
                <label style={styles.label}>Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  style={styles.input}
                  maxLength={255}
                  placeholder="your@email.com"
                />
                {mode === 'register' && (
                  <small style={styles.fieldHint}>
                    A password will be generated and sent to this email
                  </small>
                )}
              </div>

              {mode === 'login' && (
                <div style={styles.field}>
                  <label style={styles.label}>Password</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    style={styles.input}
                    minLength={1}
                    placeholder="Enter your password"
                  />
                  <Link href="/forgot-password" style={styles.forgotPasswordLink}>
                    Forgot your password?
                  </Link>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                style={{
                  ...styles.submitButton,
                  ...(loading ? styles.submitButtonDisabled : {}),
                }}
              >
                {loading 
                  ? 'Please wait...' 
                  : mode === 'login' 
                    ? 'Login' 
                    : 'Create Account'
                }
              </button>

              {mode === 'register' && (
                <p style={styles.registerNote}>
                  By registering, you'll receive an email with your login credentials.
                  You can change your password and handle after verifying your email.
                </p>
              )}
            </form>

            <div style={styles.oauthSection}>
              <div style={styles.divider}>
                <span>or continue with</span>
              </div>
              <button
                onClick={() => {
                  const apiBaseUrl = typeof window !== 'undefined' 
                    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
                    : '';
                  window.open(`${apiBaseUrl}/api/auth/github/login`, 'oauth', 'width=600,height=700,scrollbars=yes,resizable=yes');
                }}
                style={styles.githubButton}
              >
                <span style={styles.githubIcon}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                  </svg>
                </span>
                GitHub
              </button>
              <p style={styles.oauthHint}>
                No email verification required with GitHub
              </p>
            </div>
          </div>
          )}
        </main>
      </div>
    </>
  );
}

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    minHeight: '100vh',
    backgroundColor: '#f5f5f5',
  },
  header: {
    backgroundColor: '#fff',
    borderBottom: '1px solid #e0e0e0',
    padding: '1rem 2rem',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  title: {
    fontSize: '1.5rem',
    fontWeight: 'bold',
    margin: 0,
    color: '#333',
  },
  nav: {
    display: 'flex',
    gap: '1.5rem',
  },
  navLink: {
    color: '#666',
    textDecoration: 'none',
    fontSize: '0.9rem',
  },
  main: {
    maxWidth: '500px',
    margin: '3rem auto',
    padding: '0 2rem',
  },
  authBox: {
    backgroundColor: '#fff',
    borderRadius: '8px',
    padding: '2rem',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
  },
  tabs: {
    display: 'flex',
    borderBottom: '1px solid #e0e0e0',
    marginBottom: '2rem',
  },
  tab: {
    flex: 1,
    padding: '1rem',
    border: 'none',
    backgroundColor: 'transparent',
    cursor: 'pointer',
    fontSize: '1rem',
    color: '#666',
    borderBottom: '2px solid transparent',
  },
  tabActive: {
    color: '#0070f3',
    borderBottomColor: '#0070f3',
    fontWeight: '600',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1.5rem',
  },
  field: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
  },
  label: {
    fontSize: '0.9rem',
    fontWeight: '500',
    color: '#333',
  },
  input: {
    padding: '0.75rem',
    border: '1px solid #e0e0e0',
    borderRadius: '4px',
    fontSize: '1rem',
  },
  error: {
    padding: '0.75rem',
    backgroundColor: '#fee',
    border: '1px solid #fcc',
    borderRadius: '4px',
    color: '#c00',
    fontSize: '0.9rem',
  },
  submitButton: {
    padding: '0.75rem',
    backgroundColor: '#0070f3',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    fontSize: '1rem',
    fontWeight: '600',
    cursor: 'pointer',
  },
  submitButtonDisabled: {
    opacity: 0.6,
    cursor: 'not-allowed',
  },
  registerNote: {
    fontSize: '0.85rem',
    color: '#666',
    textAlign: 'center',
    margin: 0,
  },
  oauthSection: {
    marginTop: '2rem',
    paddingTop: '2rem',
    borderTop: '1px solid #e0e0e0',
  },
  divider: {
    textAlign: 'center',
    margin: '1rem 0',
    color: '#666',
    fontSize: '0.9rem',
  },
  githubButton: {
    width: '100%',
    padding: '0.75rem',
    backgroundColor: '#24292e',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    fontSize: '1rem',
    fontWeight: '600',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '0.5rem',
  },
  githubIcon: {
    display: 'flex',
    alignItems: 'center',
  },
  oauthHint: {
    fontSize: '0.8rem',
    color: '#888',
    textAlign: 'center',
    marginTop: '0.75rem',
  },
  fieldHint: {
    fontSize: '0.8rem',
    color: '#888',
  },
  forgotPasswordLink: {
    fontSize: '0.85rem',
    color: '#0070f3',
    textDecoration: 'none',
    textAlign: 'right',
    marginTop: '0.25rem',
  },
  successBox: {
    backgroundColor: '#fff',
    borderRadius: '8px',
    padding: '2rem',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
    textAlign: 'center',
  },
  successIcon: {
    fontSize: '3rem',
    marginBottom: '1rem',
  },
  successTitle: {
    fontSize: '1.5rem',
    fontWeight: 'bold',
    color: '#333',
    marginBottom: '1rem',
  },
  successMessage: {
    color: '#666',
    marginBottom: '1rem',
  },
  credentialsBox: {
    backgroundColor: '#f8f9fa',
    border: '1px solid #e9ecef',
    borderRadius: '8px',
    padding: '1rem',
    marginBottom: '1rem',
    textAlign: 'left',
  },
  credentialsLabel: {
    fontSize: '0.85rem',
    fontWeight: '600',
    color: '#666',
    marginBottom: '0.5rem',
    marginTop: 0,
  },
  credentialsValue: {
    fontSize: '0.95rem',
    color: '#333',
    margin: '0.25rem 0',
  },
  successHint: {
    fontSize: '0.9rem',
    color: '#666',
    marginBottom: '1rem',
  },
  backToLogin: {
    padding: '0.75rem 1.5rem',
    backgroundColor: '#0070f3',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    fontSize: '1rem',
    fontWeight: '600',
    cursor: 'pointer',
  },
};
