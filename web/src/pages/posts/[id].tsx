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
  hidden_by_user?: boolean;
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
  const updateSizeRef = useRef<(() => void) | null>(null);
  const [currentUser, setCurrentUser] = useState<{ id: string } | null>(null);
  const [isOwner, setIsOwner] = useState(false);
  
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
        
        // Check if current user is the owner
        const accessToken = localStorage.getItem('access_token');
        if (accessToken) {
          try {
            const userResponse = await fetch(`${API_BASE_URL}/api/auth/me`, {
              headers: {
                'Authorization': `Bearer ${accessToken}`
              }
            });
            if (userResponse.ok) {
              const userData = await userResponse.json();
              setCurrentUser({ id: userData.user.id });
              setIsOwner(userData.user.id === data.owner_id);
            }
          } catch (err) {
            // User not authenticated or token expired
            setCurrentUser(null);
            setIsOwner(false);
          }
        }
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
    if (!post) return;

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
      maxHeight: number,
      padding: number = 120
    ): ArtworkSize => {
      const availableWidth = containerWidth - padding;
      const availableHeight = maxHeight - padding;

      const scaleX = Math.floor(availableWidth / originalSize.width);
      const scaleY = Math.floor(availableHeight / originalSize.height);
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
      if (containerRect.width === 0) {
        setTimeout(updateSize, 50);
        return;
      }

      const maxHeight = window.innerHeight * 0.7;
      const scaledSize = calculateScaledSize(originalSize, containerRect.width, maxHeight, 120);

      if (scaledSize.width > 0 && scaledSize.height > 0) {
        setImageSize(scaledSize);
      }
    };

    updateSizeRef.current = updateSize;

    // Wait for refs to be set
    const timer = setTimeout(() => {
      updateSize();
    }, 0);

    const handleResize = () => {
      updateSize();
    };

    window.addEventListener('resize', handleResize);
    
    return () => {
      clearTimeout(timer);
      window.removeEventListener('resize', handleResize);
      updateSizeRef.current = null;
    };
  }, [post]);

  // Set API URL for widget (only once)
  useEffect(() => {
    if (typeof window === 'undefined') return;
    
    // Set API URL for widget before script loads
    if ((window as any).MAKAPIX_API_URL === undefined) {
      (window as any).MAKAPIX_API_URL = `${API_BASE_URL}/api`;
    }
  }, [API_BASE_URL]);

  // Initialize widget after component mounts and script loads
  useEffect(() => {
    if (!post || !id || typeof id !== 'string') return;

    // Function to initialize widget
    const initializeWidget = () => {
      // Check if widget script is loaded
      if (typeof (window as any).MakapixWidget === 'undefined') {
        // Script not loaded yet, try again after a short delay
        setTimeout(initializeWidget, 100);
        return;
      }

      // Find the widget container
      const container = document.getElementById(`makapix-widget-${post.id}`);
      if (!container) {
        // Container not found, try again after a short delay
        setTimeout(initializeWidget, 100);
        return;
      }

      // Check if already initialized
      if ((container as any).__makapix_initialized) {
        return;
      }

      // Initialize the widget
      try {
        new (window as any).MakapixWidget(container);
        (container as any).__makapix_initialized = true;
        console.log('Makapix widget initialized for post:', post.id);
      } catch (error) {
        console.error('Failed to initialize Makapix widget:', error);
      }
    };

    // Start initialization after a short delay to ensure DOM is ready
    const timer = setTimeout(initializeWidget, 100);

    return () => {
      clearTimeout(timer);
    };
  }, [post, id]);

  const handleDelete = async () => {
    if (!post || !id || typeof id !== 'string') return;
    
    const confirmed = confirm(
      'Are you sure you want to delete this post?\n\n' +
      'This action cannot be undone. The post will be permanently removed from all feeds and searches.'
    );
    
    if (!confirmed) return;
    
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
      alert('You must be logged in to delete posts.');
      return;
    }
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/posts/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      });
      
      if (response.ok || response.status === 204) {
        alert('Post deleted successfully.');
        router.push('/');
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to delete post' }));
        alert(errorData.detail || 'Failed to delete post. Please try again.');
      }
    } catch (err) {
      console.error('Error deleting post:', err);
      alert('Failed to delete post. Please try again.');
    }
  };

  const handleHide = async () => {
    if (!post || !id || typeof id !== 'string') return;
    
    const isHidden = post.hidden_by_user;
    const action = isHidden ? 'unhide' : 'hide';
    const confirmed = confirm(
      isHidden
        ? 'Are you sure you want to unhide this post? It will become visible again in feeds.'
        : 'Are you sure you want to hide this post? It will be removed from feeds temporarily but can be unhidden later.'
    );
    
    if (!confirmed) return;
    
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
      alert('You must be logged in to hide/unhide posts.');
      return;
    }
    
    try {
      const url = `${API_BASE_URL}/api/posts/${id}/hide`;
      const method = isHidden ? 'DELETE' : 'POST';
      
      const response = await fetch(url, {
        method: method,
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok || response.status === 201 || response.status === 204) {
        // Refresh the post to get updated hidden_by_user status
        const refreshResponse = await fetch(`${API_BASE_URL}/api/posts/${id}`);
        if (refreshResponse.ok) {
          const updatedPost = await refreshResponse.json();
          setPost(updatedPost);
        }
        alert(`Post ${isHidden ? 'unhidden' : 'hidden'} successfully.`);
      } else {
        const errorData = await response.json().catch(() => ({ detail: `Failed to ${action} post` }));
        alert(errorData.detail || `Failed to ${action} post. Please try again.`);
      }
    } catch (err) {
      console.error(`Error ${action}ing post:`, err);
      alert(`Failed to ${action} post. Please try again.`);
    }
  };

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
                width: imageSize ? `${imageSize.width}px` : undefined,
                height: imageSize ? `${imageSize.height}px` : undefined,
                // Force pixelated for Chrome/Edge - this must be set inline
                imageRendering: 'pixelated' as any,
                // Also set msInterpolationMode for IE/Edge legacy
                msInterpolationMode: 'nearest-neighbor' as any,
              }}
              onLoad={(e) => {
                const img = e.currentTarget;
                img.style.imageRendering = 'pixelated';
                if (updateSizeRef.current) {
                  updateSizeRef.current();
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

          {isOwner && (
            <div style={{
              background: '#fff',
              borderRadius: '8px',
              padding: '1.5rem',
              marginBottom: '2rem',
              boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
              border: '1px solid #e0e0e0'
            }}>
              <h3 style={{ fontSize: '1.2rem', marginBottom: '1rem', color: '#333' }}>Post Management</h3>
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                {post.hidden_by_user ? (
                  <button
                    onClick={handleHide}
                    style={{
                      padding: '0.75rem 1.5rem',
                      backgroundColor: '#10b981',
                      color: 'white',
                      border: 'none',
                      borderRadius: '6px',
                      fontSize: '0.9rem',
                      fontWeight: '600',
                      cursor: 'pointer',
                      transition: 'background-color 0.2s'
                    }}
                    onMouseOver={(e) => (e.currentTarget.style.backgroundColor = '#059669')}
                    onMouseOut={(e) => (e.currentTarget.style.backgroundColor = '#10b981')}
                  >
                    Unhide Post
                  </button>
                ) : (
                  <button
                    onClick={handleHide}
                    style={{
                      padding: '0.75rem 1.5rem',
                      backgroundColor: '#f59e0b',
                      color: 'white',
                      border: 'none',
                      borderRadius: '6px',
                      fontSize: '0.9rem',
                      fontWeight: '600',
                      cursor: 'pointer',
                      transition: 'background-color 0.2s'
                    }}
                    onMouseOver={(e) => (e.currentTarget.style.backgroundColor = '#d97706')}
                    onMouseOut={(e) => (e.currentTarget.style.backgroundColor = '#f59e0b')}
                  >
                    Hide Post
                  </button>
                )}
                <button
                  onClick={handleDelete}
                  style={{
                    padding: '0.75rem 1.5rem',
                    backgroundColor: '#ef4444',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    fontSize: '0.9rem',
                    fontWeight: '600',
                    cursor: 'pointer',
                    transition: 'background-color 0.2s'
                  }}
                  onMouseOver={(e) => (e.currentTarget.style.backgroundColor = '#dc2626')}
                  onMouseOut={(e) => (e.currentTarget.style.backgroundColor = '#ef4444')}
                >
                  Delete Post
                </button>
              </div>
              <p style={{ fontSize: '0.75rem', color: '#666', marginTop: '0.75rem' }}>
                {post.hidden_by_user 
                  ? 'This post is currently hidden. Click "Unhide Post" to make it visible again.'
                  : 'Hide removes the post from feeds temporarily. Delete permanently removes it (cannot be undone).'}
              </p>
            </div>
          )}

          <div style={styles.widgetContainer}>
            <div id={`makapix-widget-${post.id}`} data-post-id={post.id}></div>
          </div>
        </main>
      </div>

      {/* Load Makapix Widget Script */}
      <Script
        src={`${API_BASE_URL}/makapix-widget.js`}
        strategy="afterInteractive"
        onLoad={() => {
          // Script loaded, trigger widget initialization
          if (post && id && typeof id === 'string') {
            setTimeout(() => {
              const container = document.getElementById(`makapix-widget-${post.id}`);
              if (container && typeof (window as any).MakapixWidget !== 'undefined') {
                if (!(container as any).__makapix_initialized) {
                  try {
                    new (window as any).MakapixWidget(container);
                    (container as any).__makapix_initialized = true;
                    console.log('Makapix widget initialized via script onLoad');
                  } catch (error) {
                    console.error('Failed to initialize Makapix widget:', error);
                  }
                }
              }
            }, 100);
          }
        }}
      />
    </>
  );
}

