import { useEffect } from 'react';
import { useRouter } from 'next/router';

export default function HashtagsPage() {
  const router = useRouter();

  // Redirect to search page with hashtags tab
  useEffect(() => {
    router.replace('/search?tab=hashtags');
  }, [router]);

  return null;
}
