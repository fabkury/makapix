import { useState, useEffect } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import Link from 'next/link';

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
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
    : '';

  useEffect(() => {
    const verifyEmail = async () => {
      if (!token || typeof token !== 'string') {
        // Wait for router to be ready
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
  }, [token, router.isReady, API_BASE_URL, router]);

  return (
    <>
      <Head>
        <title>Email Verification - Makapix</title>
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
          <div style={styles.box}>
            {status === 'loading' && (
              <>
                <div style={styles.icon}>⏳</div>
                <h2 style={styles.heading}>Verifying Your Email</h2>
                <p style={styles.text}>Please wait while we verify your email address...</p>
              </>
            )}

            {status === 'success' && (
              <>
                <div style={styles.iconSuccess}>✅</div>
                <h2 style={styles.heading}>Email Verified!</h2>
                <p style={styles.text}>{message}</p>
                
                {verifyData && (
                  <div style={styles.infoBox}>
                    <p style={styles.infoText}>
                      Your handle: <strong>{verifyData.handle}</strong>
                    </p>
                    <p style={styles.hintSmall}>
                      You can change your password and handle after logging in.
                    </p>
                  </div>
                )}
                
                <Link href="/auth" style={styles.button}>
                  Go to Login
                </Link>
              </>
            )}

            {status === 'error' && (
              <>
                <div style={styles.iconError}>❌</div>
                <h2 style={styles.heading}>Verification Failed</h2>
                <p style={styles.errorText}>{message}</p>
                <p style={styles.hint}>
                  The verification link may have expired or already been used.
                </p>
                <div style={styles.actions}>
                  <Link href="/auth" style={styles.button}>
                    Go to Login
                  </Link>
                  <Link href="/auth" style={styles.secondaryButton}>
                    Register Again
                  </Link>
                </div>
              </>
            )}
          </div>
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
  box: {
    backgroundColor: '#fff',
    borderRadius: '8px',
    padding: '3rem 2rem',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
    textAlign: 'center',
  },
  icon: {
    fontSize: '3rem',
    marginBottom: '1rem',
    animation: 'spin 1s linear infinite',
  },
  iconSuccess: {
    fontSize: '3rem',
    marginBottom: '1rem',
  },
  iconError: {
    fontSize: '3rem',
    marginBottom: '1rem',
  },
  heading: {
    fontSize: '1.5rem',
    fontWeight: 'bold',
    color: '#333',
    marginBottom: '1rem',
  },
  text: {
    color: '#666',
    marginBottom: '1rem',
  },
  errorText: {
    color: '#c00',
    marginBottom: '1rem',
  },
  hint: {
    fontSize: '0.9rem',
    color: '#888',
    marginBottom: '1.5rem',
  },
  hintSmall: {
    fontSize: '0.85rem',
    color: '#888',
    margin: '0.5rem 0 0 0',
  },
  infoBox: {
    backgroundColor: '#f8f9fa',
    border: '1px solid #e9ecef',
    borderRadius: '8px',
    padding: '1rem',
    marginBottom: '1.5rem',
  },
  infoText: {
    fontSize: '1rem',
    color: '#333',
    margin: 0,
  },
  button: {
    display: 'inline-block',
    padding: '0.75rem 1.5rem',
    backgroundColor: '#0070f3',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    fontSize: '1rem',
    fontWeight: '600',
    textDecoration: 'none',
    cursor: 'pointer',
    margin: '0.5rem',
  },
  secondaryButton: {
    display: 'inline-block',
    padding: '0.75rem 1.5rem',
    backgroundColor: 'transparent',
    color: '#0070f3',
    border: '1px solid #0070f3',
    borderRadius: '4px',
    fontSize: '1rem',
    fontWeight: '600',
    textDecoration: 'none',
    cursor: 'pointer',
    margin: '0.5rem',
  },
  actions: {
    display: 'flex',
    justifyContent: 'center',
    flexWrap: 'wrap',
    gap: '0.5rem',
  },
};
