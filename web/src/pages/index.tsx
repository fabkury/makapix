import { useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';

/**
 * Home: visitors go to the Welcome page, members land on Pulse (docs/pulse/).
 * The Recent feed that used to live here is at /recent.
 */
export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    router.replace(token ? '/pulse' : '/welcome');
  }, [router]);

  return (
    <Layout title="Makapix Club">
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
        <div style={{ width: 40, height: 40, border: '3px solid var(--bg-tertiary)', borderTopColor: 'var(--accent-cyan)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }}></div>
      </div>
    </Layout>
  );
}
