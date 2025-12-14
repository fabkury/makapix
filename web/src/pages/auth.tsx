import { useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';
import AuthPanel from '../components/AuthPanel';

export default function AuthPage() {
  const router = useRouter();

  // Check if already logged in
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      router.push('/');
    }
  }, [router]);

  return (
    <Layout title="Login">
      <AuthPanel variant="standalone" showLogoSection />
    </Layout>
  );
}
