import { useState, useEffect, useRef } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Script from 'next/script';

interface Post {
  id: string;
  title: string;
  description?: string;
  hashtags?: string[];
  art_url: string;
  canvas: string;
  owner_id: string;
  created_at: string;
  kind?: string;
  owner?: {
    id: string;
    handle: string;
    display_name: string;
  };
}

interface ArtworkSize {
  width: number;
  height: number;
}

export default function PostPage() {
  const router = useRouter();
  const { id } = router.query;
  const [post, setPost] = useState<Post | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imageSize, setImageSize] = useState<ArtworkSize | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
    : '';

  useEffect(() => {
    if (!id || typeof id !== 'string') return;

    const fetchPost = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const response = await fetch(`${API_BASE_URL}/api/posts/${id}`);
        
        if (!response.ok) {
          if (response.status === 404) {
            setError('Post not found');
          } else {
            setError(`Failed to load post: ${response.statusText}`);
          }
          setLoading(false);
          return;
        }
        
        const data = await response.json();
        setPost(data);
      } catch (err) {
        setError('Failed to load post');
        console.error('Error fetching post:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchPost();
  }, [id, API_BASE_URL]);

  // Calculate pixel art scaling
  useEffect(() => {
    if (!post || !containerRef.current || !imageRef.current) return;

    const parseCanvas = (canvas: string): ArtworkSize | null => {
      const match = canvas.match(/(\d+)x(\d+)/);
      if (!match) return null;
      return {
        width: parseInt(match[1], 10),
        height: parseInt(match[2], 10),
      };
    };

    const calculateScaledSize = (
      originalSize: ArtworkSize,
      containerWidth: number,
      containerHeight: number,
      padding: number = 120
    ): ArtworkSize => {
      const availableWidth = containerWidth - padding;
      const availableHeight = containerHeight - padding;

      // Calculate scale factors
      const scaleX = Math.floor(availableWidth / originalSize.width);
      const scaleY = Math.floor(availableHeight / originalSize.height);

      // Use the smaller scale factor to ensure it fits both dimensions
      const scale = Math.max(1, Math.min(scaleX, scaleY));

      return {
        width: originalSize.width * scale,
        height: originalSize.height * scale,
      };
    };

    const updateSize = () => {
      const container = containerRef.current;
      const image = imageRef.current;
      if (!container || !image) return;

      const originalSize = parseCanvas(post.canvas);
      if (!originalSize) return;

      const containerRect = container.getBoundingClientRect();
      const scaledSize = calculateScaledSize(
        originalSize,
        containerRect.width,
        window.innerHeight * 0.7, // Use 70% of viewport height as max
        120 // 120px padding (80px from container + 40px extra)
      );

      setImageSize(scaledSize);
    };

    // Update size initially and on resize
    updateSize();
    window.addEventListener('resize', updateSize);
    
    // Also update when image loads
    const image = imageRef.current;
    if (image) {
      image.addEventListener('load', updateSize);
    }

    return () => {
      window.removeEventListener('resize', updateSize);
      if (image) {
        image.removeEventListener('load', updateSize);
      }
    };
  }, [post]);

  // Set API URL for widget (only once)
  useEffect(() => {
    if (typeof window === 'undefined') return;
    
    // Set API URL for widget before script loads
    if (window.MAKAPIX_API_URL === undefined) {
      (window as any).MAKAPIX_API_URL = `${API_BASE_URL}/api`;
    }
  }, [API_BASE_URL]);

  if (loading) {
    return (
      <>
        <Head>
          <title>Loading Post - Makapix</title>
        </Head>
        <div style={{ 
          minHeight: '100vh', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          background: '#f5f5f5'
        }}>
          <p style={{ fontSize: '18px', color: '#666' }}>Loading post...</p>
        </div>
      </>
    );
  }

  if (error || !post) {
    return (
      <>
        <Head>
          <title>Post Not Found - Makapix</title>
        </Head>
        <div style={{ 
          minHeight: '100vh', 
          display: 'flex', 
          flexDirection: 'column',
          alignItems: 'center', 
          justifyContent: 'center',
          background: '#f5f5f5',
          padding: '2rem'
        }}>
          <h1 style={{ fontSize: '24px', marginBottom: '1rem', color: '#333' }}>
            {error || 'Post not found'}
          </h1>
          <Link href="/" style={{ 
            color: '#0070f3', 
            textDecoration: 'none',
            fontSize: '16px'
          }}>
            ← Back to Home
          </Link>
        </div>
      </>
    );
  }

  const styles = {
    container: {
      minHeight: '100vh',
      background: '#f5f5f5',
    },
    header: {
      background: '#fff',
      borderBottom: '1px solid #e0e0e0',
      padding: '1rem 2rem',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
    },
    headerTitle: {
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
      maxWidth: '1200px',
      margin: '0 auto',
      padding: '2rem',
    },
    artworkContainer: {
      background: '#fff',
      borderRadius: '8px',
      padding: '80px',
      marginBottom: '2rem',
      boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
      display: 'flex',
      flexDirection: 'column' as const,
      alignItems: 'center',
    },
    artworkImage: {
      maxWidth: '100%',
      display: 'block',
    },
    postTitle: {
      fontSize: '2rem',
      fontWeight: 'bold',
      margin: '1.5rem 0 0.5rem 0',
      color: '#333',
      textAlign: 'center' as const,
    },
    postMeta: {
      display: 'flex',
      gap: '1rem',
      justifyContent: 'center',
      marginBottom: '1rem',
      fontSize: '0.9rem',
      color: '#666',
    },
    postDescription: {
      fontSize: '1rem',
      lineHeight: '1.6',
      color: '#555',
      marginTop: '1rem',
      textAlign: 'center' as const,
      maxWidth: '800px',
    },
    hashtags: {
      display: 'flex',
      flexWrap: 'wrap' as const,
      gap: '0.5rem',
      justifyContent: 'center',
      marginTop: '1rem',
    },
    hashtag: {
      background: '#e3f2fd',
      color: '#1976d2',
      padding: '0.25rem 0.75rem',
      borderRadius: '16px',
      fontSize: '0.875rem',
      textDecoration: 'none',
    },
    widgetContainer: {
      background: '#fff',
      borderRadius: '8px',
      padding: '2rem',
      boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
    },
  };

  return (
    <>
      <Head>
        <title>{post.title} - Makapix</title>
        <meta name="description" content={post.description || post.title} />
      </Head>

      <div style={styles.container}>
        <header style={styles.header}>
          <h1 style={styles.headerTitle}>Makapix</h1>
          <nav style={styles.nav}>
            <Link href="/" style={styles.navLink}>Home</Link>
            <Link href="/recent" style={styles.navLink}>Recent</Link>
            <Link href="/search" style={styles.navLink}>Search</Link>
            <Link href="/publish" style={styles.navLink}>Publish</Link>
          </nav>
        </header>

        <main style={styles.main}>
          <div style={styles.artworkContainer} ref={containerRef}>
            <style dangerouslySetInnerHTML={{
              __html: `
                .pixel-art-image {
                  /* Safari - vendor prefix */
                  image-rendering: -webkit-optimize-contrast;
                  /* Firefox - vendor prefix */
                  image-rendering: -moz-crisp-edges;
                  /* Standard - Firefox */
                  image-rendering: crisp-edges;
                  /* Standard - Chrome/Edge */
                  image-rendering: pixelated;
                  /* IE/Edge legacy */
                  -ms-interpolation-mode: nearest-neighbor;
                }
              `
            }} />
            <img
              ref={imageRef}
              src={post.art_url}
              alt={post.title}
              className="pixel-art-image"
              style={{
                ...styles.artworkImage,
                width: imageSize ? `${imageSize.width}px` : 'auto',
                height: imageSize ? `${imageSize.height}px` : 'auto',
                // Force pixelated for Chrome/Edge - this must be set inline
                imageRendering: 'pixelated' as any,
                // Also set msInterpolationMode for IE/Edge legacy
                msInterpolationMode: 'nearest-neighbor' as any,
              }}
              onLoad={(e) => {
                // Force pixel rendering on load for Chrome/Edge
                const img = e.currentTarget;
                if (img.style) {
                  img.style.imageRendering = 'pixelated';
                  (img.style as any).imageRendering = 'crisp-edges';
                  (img.style as any).imageRendering = 'pixelated';
                }
              }}
            />
            <h1 style={styles.postTitle}>{post.title}</h1>
            
            <div style={styles.postMeta}>
              {post.owner && (
                <Link href={`/users/${post.owner.id}`} style={{ color: '#666', textDecoration: 'none' }}>
                  by {post.owner.display_name || post.owner.handle}
                </Link>
              )}
              <span>•</span>
              <span>{new Date(post.created_at).toLocaleDateString()}</span>
            </div>

            {post.description && (
              <div style={styles.postDescription}>
                {post.description.split('\n').map((line, i) => (
                  <p key={i} style={{ margin: i > 0 ? '0.5rem 0' : 0 }}>{line}</p>
                ))}
              </div>
            )}

            {post.hashtags && post.hashtags.length > 0 && (
              <div style={styles.hashtags}>
                {post.hashtags.map((tag) => (
                  <Link
                    key={tag}
                    href={`/hashtags/${encodeURIComponent(tag)}`}
                    style={styles.hashtag}
                  >
                    #{tag}
                  </Link>
                ))}
              </div>
            )}
          </div>

          <div style={styles.widgetContainer}>
            <div id={`makapix-widget-${post.id}`} data-post-id={post.id}></div>
          </div>
        </main>
      </div>

      {/* Load Makapix Widget Script */}
      {/* The script auto-initializes widgets on load, so we don't need manual initialization */}
      <Script
        src={`${API_BASE_URL}/makapix-widget.js`}
        strategy="afterInteractive"
      />
    </>
  );
}

