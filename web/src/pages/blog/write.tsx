import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Layout from '../../components/Layout';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { authenticatedFetch, authenticatedRequestJson, clearTokens } from '../../lib/api';

interface BlogPost {
  id: string;
  title: string;
  body: string;
  image_urls: string[];
}

export default function WriteBlogPostPage() {
  const router = useRouter();
  const { edit } = router.query;
  const isEditMode = !!edit && typeof edit === 'string';
  
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [imageUrls, setImageUrls] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<'write' | 'preview'>('write');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  // Load existing post if editing
  useEffect(() => {
    if (isEditMode && edit) {
      const fetchPost = async () => {
        setLoading(true);
        try {
          const response = await authenticatedFetch(`${API_BASE_URL}/api/blog-post/${edit}`);
          
          if (response.status === 401) {
            clearTokens();
            router.push('/auth');
            return;
          }
          
          if (response.ok) {
            const data: BlogPost = await response.json();
            setTitle(data.title);
            setBody(data.body);
            setImageUrls(data.image_urls || []);
          } else {
            setError('Failed to load blog post');
          }
        } catch (err) {
          setError('Failed to load blog post');
          console.error('Error fetching blog post:', err);
        } finally {
          setLoading(false);
        }
      };
      
      fetchPost();
    }
  }, [isEditMode, edit, API_BASE_URL, router]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = Array.from(e.dataTransfer.files);
    const imageFiles = files.filter(file => file.type.startsWith('image/'));
    
    if (imageFiles.length === 0) return;
    
    // Need a blog post ID to upload images
    if (!isEditMode) {
      alert('Please save your blog post first before uploading images.');
      return;
    }
    
    for (const file of imageFiles.slice(0, 10 - imageUrls.length)) {
      if (imageUrls.length >= 10) {
        alert('Maximum 10 images per blog post');
        break;
      }
      
      try {
        const formData = new FormData();
        formData.append('image', file);
        
        const response = await authenticatedFetch(`${API_BASE_URL}/api/blog-post/${edit}/images`, {
          method: 'POST',
          body: formData,
        });
        
        if (response.status === 401) {
          clearTokens();
          router.push('/auth');
          return;
        }
        
        if (response.ok) {
          const data = await response.json();
          const imageMarkdown = `![${file.name}](${data.image_url})`;
          setBody(prev => prev + '\n\n' + imageMarkdown);
          setImageUrls(prev => [...prev, data.image_url]);
        } else {
          const errorData = await response.json().catch(() => ({ detail: 'Failed to upload image' }));
          alert(errorData.detail || 'Failed to upload image');
        }
      } catch (err) {
        console.error('Error uploading image:', err);
        alert('Failed to upload image');
      }
    }
  };

  const handleFileInput = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    
    if (!isEditMode) {
      alert('Please save your blog post first before uploading images.');
      return;
    }
    
    for (const file of Array.from(files).slice(0, 10 - imageUrls.length)) {
      if (imageUrls.length >= 10) {
        alert('Maximum 10 images per blog post');
        break;
      }
      
      try {
        const formData = new FormData();
        formData.append('image', file);
        
        const response = await authenticatedFetch(`${API_BASE_URL}/api/blog-post/${edit}/images`, {
          method: 'POST',
          body: formData,
        });
        
        if (response.status === 401) {
          clearTokens();
          router.push('/auth');
          return;
        }
        
        if (response.ok) {
          const data = await response.json();
          const imageMarkdown = `![${file.name}](${data.image_url})`;
          setBody(prev => prev + '\n\n' + imageMarkdown);
          setImageUrls(prev => [...prev, data.image_url]);
        } else {
          const errorData = await response.json().catch(() => ({ detail: 'Failed to upload image' }));
          alert(errorData.detail || 'Failed to upload image');
        }
      } catch (err) {
        console.error('Error uploading image:', err);
        alert('Failed to upload image');
      }
    }
    
    // Reset input
    e.target.value = '';
  };

  const handlePublish = async () => {
    if (!title.trim()) {
      setError('Title is required');
      return;
    }
    
    if (!body.trim()) {
      setError('Body is required');
      return;
    }
    
    if (body.length > 10000) {
      setError('Blog post body exceeds maximum length of 10,000 characters');
      return;
    }
    
    setSaving(true);
    setError(null);
    
    try {
      const url = isEditMode 
        ? `/api/blog-post/${edit}`
        : `/api/blog-post`;
      
      const method = isEditMode ? 'PATCH' : 'POST';
      
      const data = await authenticatedRequestJson<{ public_sqid: string }>(
        url,
        {
          body: JSON.stringify({
            title: title.trim(),
            body: body.trim(),
          })
        },
        method as 'POST' | 'PATCH'
      );
      
      router.push(`/b/${data.public_sqid}`);
    } catch (err) {
      if (err instanceof Error && err.message.includes('401')) {
        clearTokens();
        router.push('/auth');
        return;
      }
      setError('Failed to save blog post');
      console.error('Error saving blog post:', err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Layout title="Loading...">
        <div className="loading-container">
          <div className="loading-spinner"></div>
        </div>
        <style jsx>{`
          .loading-container {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - var(--header-height));
          }
          .loading-spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--bg-tertiary);
            border-top-color: var(--accent-cyan);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
          }
          @keyframes spin { to { transform: rotate(360deg); } }
        `}</style>
      </Layout>
    );
  }

  return (
    <Layout title={isEditMode ? 'Edit Blog Post' : 'Write Blog Post'}>
      <div className="write-container">
        <div className="write-header">
          <Link href="/blog" className="back-link">← Back to Blog</Link>
          <button
            onClick={handlePublish}
            disabled={saving || !title.trim() || !body.trim()}
            className="publish-button"
          >
            {saving ? 'Publishing...' : isEditMode ? 'Update Post' : 'Publish'}
          </button>
        </div>

        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        <div className="title-input-container">
          <input
            type="text"
            placeholder="Blog post title..."
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="title-input"
            maxLength={200}
          />
        </div>

        <div className="editor-container">
          <div className="tabs">
            <button
              className={`tab ${activeTab === 'write' ? 'active' : ''}`}
              onClick={() => setActiveTab('write')}
            >
              Write
            </button>
            <button
              className={`tab ${activeTab === 'preview' ? 'active' : ''}`}
              onClick={() => setActiveTab('preview')}
            >
              Preview
            </button>
          </div>

          <div className="editor-content">
            {activeTab === 'write' ? (
              <div
                className="editor-area"
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
              >
                {isDragging && (
                  <div className="drag-overlay">
                    <span className="drag-icon">📎</span>
                    <p>Drop images here</p>
                  </div>
                )}
                <textarea
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  placeholder="Write your blog post in Markdown..."
                  className="markdown-editor"
                  maxLength={10000}
                />
                <div className="editor-footer">
                  <span className="char-count">
                    {body.length} / 10,000 characters
                  </span>
                  <span className="image-count">
                    {imageUrls.length} / 10 images
                  </span>
                  {isEditMode && (
                    <label className="upload-button-label">
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handleFileInput}
                        style={{ display: 'none' }}
                        multiple
                      />
                      📎 Upload Images
                    </label>
                  )}
                </div>
              </div>
            ) : (
              <div className="preview-area">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeSanitize]}
                  components={{
                    img: ({ src, alt }) => (
                      <img
                        src={src?.startsWith('http') ? src : `${API_BASE_URL}${src}`}
                        alt={alt}
                        className="preview-image"
                      />
                    ),
                  }}
                >
                  {body || '*Start writing to see preview...*'}
                </ReactMarkdown>
              </div>
            )}
          </div>
        </div>
      </div>

      <style jsx>{`
        .write-container {
          max-width: 1000px;
          margin: 0 auto;
          padding: 24px;
        }

        .write-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
        }

        .back-link {
          color: var(--accent-cyan);
          text-decoration: none;
        }

        .back-link:hover {
          color: var(--accent-pink);
        }

        .publish-button {
          padding: 12px 32px;
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          border: none;
          border-radius: 8px;
          font-weight: 600;
          font-size: 1rem;
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .publish-button:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: var(--glow-pink);
        }

        .publish-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .error-message {
          background: rgba(239, 68, 68, 0.2);
          color: #ef4444;
          padding: 12px 16px;
          border-radius: 8px;
          margin-bottom: 16px;
        }

        .title-input-container {
          margin-bottom: 24px;
        }

        .title-input {
          width: 100%;
          padding: 16px;
          font-size: 1.5rem;
          font-weight: 700;
          background: var(--bg-secondary);
          border: 2px solid var(--bg-tertiary);
          border-radius: 8px;
          color: var(--text-primary);
        }

        .title-input:focus {
          outline: none;
          border-color: var(--accent-cyan);
        }

        .editor-container {
          background: var(--bg-secondary);
          border-radius: 12px;
          overflow: hidden;
        }

        .tabs {
          display: flex;
          border-bottom: 1px solid var(--bg-tertiary);
        }

        .tab {
          flex: 1;
          padding: 16px;
          background: transparent;
          border: none;
          color: var(--text-secondary);
          font-weight: 600;
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .tab:hover {
          background: var(--bg-tertiary);
        }

        .tab.active {
          color: var(--accent-cyan);
          border-bottom: 2px solid var(--accent-cyan);
        }

        .editor-content {
          min-height: 500px;
        }

        .editor-area {
          position: relative;
          height: 100%;
        }

        .drag-overlay {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 212, 255, 0.1);
          border: 2px dashed var(--accent-cyan);
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          z-index: 10;
        }

        .drag-icon {
          font-size: 3rem;
          margin-bottom: 8px;
        }

        .markdown-editor {
          width: 100%;
          height: 500px;
          padding: 24px;
          background: var(--bg-primary);
          border: none;
          color: var(--text-primary);
          font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
          font-size: 0.95rem;
          line-height: 1.6;
          resize: vertical;
        }

        .markdown-editor:focus {
          outline: none;
        }

        .editor-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px 24px;
          border-top: 1px solid var(--bg-tertiary);
          font-size: 0.85rem;
          color: var(--text-muted);
        }

        .char-count,
        .image-count {
          margin-right: 16px;
        }

        .upload-button-label {
          cursor: pointer;
          color: var(--accent-cyan);
          padding: 6px 12px;
          border-radius: 6px;
          transition: all var(--transition-fast);
        }

        .upload-button-label:hover {
          background: var(--bg-tertiary);
        }

        .preview-area {
          padding: 32px;
          min-height: 500px;
          line-height: 1.8;
          color: var(--text-secondary);
        }

        .preview-area :global(h1),
        .preview-area :global(h2),
        .preview-area :global(h3) {
          color: var(--text-primary);
          margin-top: 24px;
          margin-bottom: 12px;
        }

        .preview-area :global(p) {
          margin-bottom: 16px;
        }

        .preview-area :global(ul),
        .preview-area :global(ol) {
          margin-bottom: 16px;
          padding-left: 24px;
        }

        .preview-area :global(code) {
          background: var(--bg-tertiary);
          padding: 2px 6px;
          border-radius: 4px;
          font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
        }

        .preview-area :global(pre) {
          background: var(--bg-tertiary);
          padding: 16px;
          border-radius: 8px;
          overflow-x: auto;
          margin-bottom: 16px;
        }

        .preview-area :global(pre code) {
          background: none;
          padding: 0;
        }

        .preview-area :global(blockquote) {
          border-left: 4px solid var(--accent-cyan);
          padding-left: 16px;
          margin-left: 0;
          margin-bottom: 16px;
        }

        .preview-area :global(a) {
          color: var(--accent-cyan);
          text-decoration: underline;
        }

        .preview-image {
          max-width: 100%;
          height: auto;
          border-radius: 8px;
          margin: 16px 0;
        }
      `}</style>
    </Layout>
  );
}

