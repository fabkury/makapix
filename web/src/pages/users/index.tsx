import { useEffect } from 'react';
import { useRouter } from 'next/router';

export default function UsersDirectoryPage() {
  const router = useRouter();

  // Redirect to search page with users tab
  useEffect(() => {
    router.replace('/search?tab=users');
  }, [router]);

  return null;
}
