import { useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const API_BASE_URL = typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
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
    <>
      <Head>
        <title>Reset Password - Makapix</title>
      </Head>
      <div style={styles.container}>
        <header style={styles.header}>
          <h1 style={styles.title}>Makapix</h1>
          <nav style={styles.nav}>
            <Link href="/" style={styles.navLink}>Home</Link>
            <Link href="/auth" style={styles.navLink}>Login</Link>
          </nav>
        </header>

        <main style={styles.main}>
          {success ? (
            <div style={styles.successBox}>
              <div style={styles.successIcon}>📧</div>
              <h2 style={styles.successTitle}>Check Your Email</h2>
              <p style={styles.successMessage}>
                If an account exists with the email <strong>{email}</strong>, 
                we've sent a password reset link.
              </p>
              <p style={styles.successHint}>
                The link will expire in 1 hour. If you don't see the email, 
                check your spam folder.
              </p>
              <Link href="/auth" style={styles.backLink}>
                Back to Login
              </Link>
            </div>
          ) : (
            <div style={styles.formBox}>
              <h2 style={styles.formTitle}>Reset Your Password</h2>
              <p style={styles.formDescription}>
                Enter the email address associated with your account, 
                and we'll send you a link to reset your password.
              </p>

              <form onSubmit={handleSubmit} style={styles.form}>
                {error && (
                  <div style={styles.error}>
                    {error}
                  </div>
                )}

                <div style={styles.field}>
                  <label style={styles.label}>Email Address</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    style={styles.input}
                    placeholder="your@email.com"
                    autoFocus
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  style={{
                    ...styles.submitButton,
                    ...(loading ? styles.submitButtonDisabled : {}),
                  }}
                >
                  {loading ? 'Sending...' : 'Send Reset Link'}
                </button>
              </form>

              <div style={styles.linkSection}>
                <Link href="/auth" style={styles.backToLogin}>
                  ← Back to Login
                </Link>
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
    maxWidth: '450px',
    margin: '3rem auto',
    padding: '0 2rem',
  },
  formBox: {
    backgroundColor: '#fff',
    borderRadius: '8px',
    padding: '2rem',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
  },
  formTitle: {
    fontSize: '1.5rem',
    fontWeight: 'bold',
    color: '#333',
    marginTop: 0,
    marginBottom: '0.75rem',
  },
  formDescription: {
    fontSize: '0.95rem',
    color: '#666',
    marginBottom: '1.5rem',
    lineHeight: '1.5',
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
  linkSection: {
    marginTop: '1.5rem',
    paddingTop: '1.5rem',
    borderTop: '1px solid #e0e0e0',
    textAlign: 'center',
  },
  backToLogin: {
    color: '#0070f3',
    textDecoration: 'none',
    fontSize: '0.95rem',
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
    lineHeight: '1.5',
  },
  successHint: {
    fontSize: '0.9rem',
    color: '#888',
    marginBottom: '1.5rem',
  },
  backLink: {
    display: 'inline-block',
    padding: '0.75rem 1.5rem',
    backgroundColor: '#0070f3',
    color: 'white',
    textDecoration: 'none',
    borderRadius: '4px',
    fontSize: '1rem',
    fontWeight: '600',
  },
};

