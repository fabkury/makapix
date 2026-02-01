import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { 
  Heart, 
  MessageCircle, 
  Eye, 
  User, 
  Gift, 
  CheckCircle, 
  Star,
  Sparkles
} from 'lucide-react';

// Mock data for highlights
const highlights = [
  {
    id: 1,
    title: 'Neon Dreams',
    image: 'https://images.unsplash.com/photo-1764258560286-b3aa856c8ff0?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxkaWdpdGFsJTIwYXJ0JTIwbmVvbnxlbnwxfHx8fDE3NjgyNTIzMTR8MA&ixlib=rb-4.1.0&q=80&w=1080',
    reactions: 1234,
    comments: 89,
    views: 5678
  },
  {
    id: 2,
    title: 'Cyberpunk City',
    image: 'https://images.unsplash.com/photo-1563089145-599997674d42?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxjeWJlcnB1bmslMjBhZXN0aGV0aWN8ZW58MXx8fHwxNzY4MjYzNTczfDA&ixlib=rb-4.1.0&q=80&w=1080',
    reactions: 2341,
    comments: 156,
    views: 8901
  },
  {
    id: 3,
    title: 'Abstract Flow',
    image: 'https://images.unsplash.com/photo-1604079628040-94301bb21b91?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxhYnN0cmFjdCUyMGdyYWRpZW50fGVufDF8fHx8MTc2ODE4MTk5Nnww&ixlib=rb-4.1.0&q=80&w=1080',
    reactions: 987,
    comments: 45,
    views: 3456
  },
  {
    id: 4,
    title: 'Urban Architecture',
    image: 'https://images.unsplash.com/photo-1519662978799-2f05096d3636?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxtb2Rlcm4lMjBhcmNoaXRlY3R1cmV8ZW58MXx8fHwxNzY4MTkyMjc1fDA&ixlib=rb-4.1.0&q=80&w=1080',
    reactions: 1567,
    comments: 92,
    views: 6789
  },
  {
    id: 5,
    title: 'Vaporwave Dreams',
    image: 'https://images.unsplash.com/photo-1764561842859-91d52bffc52d?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxkaWdpdGFsJTIwYXJ0JTIwdmFwb3J3YXZlfGVufDF8fHx8MTc2ODI2NDMzNnww&ixlib=rb-4.1.0&q=80&w=1080',
    reactions: 1890,
    comments: 134,
    views: 7234
  },
  {
    id: 6,
    title: 'Neon Portrait',
    image: 'https://images.unsplash.com/photo-1615276884890-2f2ffdab7b43?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxuZW9uJTIwbGlnaHRzJTIwcG9ydHJhaXR8ZW58MXx8fHwxNzY4MjY0MzM2fDA&ixlib=rb-4.1.0&q=80&w=1080',
    reactions: 2145,
    comments: 178,
    views: 9567
  },
  {
    id: 7,
    title: 'Geometric Patterns',
    image: 'https://images.unsplash.com/photo-1743965127369-6e28d86e2460?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxhYnN0cmFjdCUyMGdlb21ldHJpYyUyMGFydHxlbnwxfHx8fDE3NjgxODUwMDl8MA&ixlib=rb-4.1.0&q=80&w=1080',
    reactions: 1456,
    comments: 98,
    views: 6123
  },
  {
    id: 8,
    title: 'Synthwave Sunset',
    image: 'https://images.unsplash.com/photo-1704700792025-c72f5a543b56?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxzeW50aHdhdmUlMjBzdW5zZXR8ZW58MXx8fHwxNzY4MjU4Nzg0fDA&ixlib=rb-4.1.0&q=80&w=1080',
    reactions: 1678,
    comments: 112,
    views: 7891
  },
  {
    id: 9,
    title: 'Future Tech',
    image: 'https://images.unsplash.com/photo-1672581437674-3186b17b405a?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxmdXR1cmlzdGljJTIwdGVjaG5vbG9neXxlbnwxfHx8fDE3NjgyMTI3NzF8MA&ixlib=rb-4.1.0&q=80&w=1080',
    reactions: 2234,
    comments: 189,
    views: 10234
  },
  {
    id: 10,
    title: 'Minimalist Art',
    image: 'https://images.unsplash.com/photo-1761156254622-7b66649b1f69?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxtb2Rlcm4lMjBtaW5pbWFsaXN0JTIwYXJ0fGVufDF8fHx8MTc2ODI2NDMzOHww&ixlib=rb-4.1.0&q=80&w=1080',
    reactions: 1123,
    comments: 76,
    views: 5234
  },
  {
    id: 11,
    title: 'Space Odyssey',
    image: 'https://images.unsplash.com/photo-1644331064965-bce2645dd1e0?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxkaWdpdGFsJTIwaWxsdXN0cmF0aW9uJTIwc3BhY2V8ZW58MXx8fHwxNzY4MjY0MzM4fDA&ixlib=rb-4.1.0&q=80&w=1080',
    reactions: 1987,
    comments: 145,
    views: 8456
  },
  {
    id: 12,
    title: 'Digital Fusion',
    image: 'https://images.unsplash.com/photo-1764258560286-b3aa856c8ff0?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxkaWdpdGFsJTIwYXJ0JTIwbmVvbnxlbnwxfHx8fDE3NjgyNTIzMTR8MA&ixlib=rb-4.1.0&q=80&w=1080',
    reactions: 1345,
    comments: 89,
    views: 6789
  }
];

// Generate mock gallery data
const generateGalleryItems = (count: number) => {
  const images = [
    'https://images.unsplash.com/photo-1764258560286-b3aa856c8ff0?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxkaWdpdGFsJTIwYXJ0JTIwbmVvbnxlbnwxfHx8fDE3NjgyNTIzMTR8MA&ixlib=rb-4.1.0&q=80&w=400',
    'https://images.unsplash.com/photo-1563089145-599997674d42?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxjeWJlcnB1bmslMjBhZXN0aGV0aWN8ZW58MXx8fHwxNzY4MjYzNTczfDA&ixlib=rb-4.1.0&q=80&w=400',
    'https://images.unsplash.com/photo-1604079628040-94301bb21b91?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxhYnN0cmFjdCUyMGdyYWRpZW50fGVufDF8fHx8MTc2ODE4MTk5Nnww&ixlib=rb-4.1.0&q=80&w=400',
    'https://images.unsplash.com/photo-1519662978799-2f05096d3636?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxtb2Rlcm4lMjBhcmNoaXRlY3R1cmV8ZW58MXx8fHwxNzY4MTkyMjc1fDA&ixlib=rb-4.1.0&q=80&w=400',
    'https://images.unsplash.com/photo-1663408490081-b1edfbe1b2e9?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHx1cmJhbiUyMGNpdHklMjBuaWdodHxlbnwxfHx8fDE3NjgyNjM1NzJ8MA&ixlib=rb-4.1.0&q=80&w=400',
  ];
  
  return Array.from({ length: count }, (_, i) => ({
    id: i + 1,
    image: images[i % images.length],
    likes: Math.floor(Math.random() * 2000) + 100,
    comments: Math.floor(Math.random() * 200) + 10
  }));
};

export default function App() {
  const [activeTab, setActiveTab] = useState<'gallery' | 'favourites'>('gallery');
  const [selectedHighlight, setSelectedHighlight] = useState(1);
  const [galleryItems, setGalleryItems] = useState(generateGalleryItems(12));
  const [isLoading, setIsLoading] = useState(false);
  const [isOwnProfile, setIsOwnProfile] = useState(true); // Toggle to simulate viewing own profile
  const observerRef = useRef<IntersectionObserver | null>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  // Infinite scroll effect
  useEffect(() => {
    if (observerRef.current) observerRef.current.disconnect();

    observerRef.current = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !isLoading) {
          setIsLoading(true);
          // Simulate loading more items
          setTimeout(() => {
            setGalleryItems(prev => [...prev, ...generateGalleryItems(6)]);
            setIsLoading(false);
          }, 1000);
        }
      },
      { threshold: 0.1 }
    );

    if (loadMoreRef.current) {
      observerRef.current.observe(loadMoreRef.current);
    }

    return () => {
      if (observerRef.current) observerRef.current.disconnect();
    };
  }, [isLoading]);

  return (
    <div className="min-h-screen bg-black text-white">
      {/* Profile Content Container */}
      <div className="max-w-5xl mx-auto px-4 md:px-6 pt-6 relative z-10">
        {/* Identity Section */}
        <div className="mb-6">
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
            {/* Avatar and Info */}
            <div className="flex items-end gap-4">
              {/* Avatar */}
              <button 
                className="relative shrink-0 group"
                aria-label="View profile picture"
              >
                <div className="w-24 h-24 md:w-32 md:h-32 rounded-full border-2 border-white overflow-hidden bg-black transition-transform group-hover:scale-105">
                  <img
                    src="https://images.unsplash.com/photo-1580489944761-15a19d654956?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxwb3J0cmFpdCUyMHdvbWFufGVufDF8fHx8MTc2ODIyMjgxMHww&ixlib=rb-4.1.0&q=80&w=400"
                    alt="Profile"
                    className="w-full h-full object-cover"
                  />
                </div>
              </button>

              {/* Name and Bio */}
              <div className="pb-2">
                <h1 className="text-xl md:text-2xl mb-1">lunastarlight</h1>
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-[#00F5FF]" />
                  <Star className="w-4 h-4 text-[#FF006E]" fill="#FF006E" />
                </div>
                <p className="text-sm text-white/80 mt-1 max-w-md">
                  Digital artist • Neon dreamer • Creating the future
                </p>
              </div>
            </div>

            {/* Action Buttons - Desktop */}
            <div className="hidden md:flex items-center gap-2">
              <button className="flex-1 px-6 py-2.5 border border-white/20 rounded-md hover:bg-white/10 transition-colors text-xl">
                <span style={{ filter: 'drop-shadow(0 0 8px rgba(0, 245, 255, 0.8))' }}>👣</span>
              </button>
              <button 
                className="p-2 border border-white/20 rounded-md hover:bg-white/10 transition-colors"
                aria-label="Send gift"
              >
                <Gift className="w-5 h-5 text-[#00F5FF]" />
              </button>
            </div>
          </div>

          {/* Stats */}
          <div className="flex flex-wrap items-center gap-4 md:gap-6 mt-4 text-sm md:text-base">
            <div className="flex items-center gap-1.5">
              <User className="w-4 h-4 text-white/70" />
              <span className="text-white/90">24.5K</span>
            </div>
            <div className="w-px h-4 bg-white/20" />
            <div className="flex items-center gap-1.5">
              <span className="text-white/70">🖼️</span>
              <span className="text-white/90">342</span>
            </div>
            <div className="w-px h-4 bg-white/20" />
            <div className="flex items-center gap-1.5">
              <Eye className="w-4 h-4 text-white/70" />
              <span className="text-white/90">1.2M</span>
            </div>
            <div className="w-px h-4 bg-white/20" />
            <div className="flex items-center gap-1.5">
              <span className="text-white/70">🧮</span>
              <span className="text-white/90">18.3K</span>
            </div>
          </div>

          {/* Own User Panel - Only visible on own profile */}
          {isOwnProfile && (
            <div className="flex flex-wrap gap-2 mt-4">
              <button 
                className="px-3 py-2 border border-white/20 rounded-md hover:bg-white/10 hover:border-[#00F5FF]/50 transition-colors text-lg"
                aria-label="Artist dashboard"
              >
                📊
              </button>
              <button 
                className="px-3 py-2 border border-white/20 rounded-md hover:bg-white/10 hover:border-[#FF006E]/50 transition-colors text-lg"
                aria-label="Post management dashboard"
              >
                🗂️
              </button>
              <button 
                className="px-3 py-2 border border-white/20 rounded-md hover:bg-white/10 hover:border-[#00F5FF]/50 transition-colors text-lg"
                aria-label="Manage players"
              >
                📺
              </button>
              <div className="w-4" />
              <button 
                className="px-3 py-2 border border-white/20 rounded-md hover:bg-white/10 hover:border-[#00F5FF]/50 transition-colors text-lg"
                aria-label="Edit profile"
              >
                ✏️
              </button>
              <button 
                className="px-3 py-2 border border-white/20 rounded-md hover:bg-white/10 hover:border-[#FF006E]/50 transition-colors text-lg"
                aria-label="Logout from profile"
              >
                🚪
              </button>
            </div>
          )}

          {/* Bio Section */}
          <div className="-mx-4 md:mx-0 mt-4 py-4 px-0 md:px-4 border border-white/10 !rounded-none md:!rounded-md bg-white/5">
            <div className="prose prose-invert prose-sm max-w-none text-white/80 px-4 md:px-0">
              <ReactMarkdown 
                components={{
                  p: ({ node, ...props }) => <p className="mb-2 last:mb-0" {...props} />,
                  strong: ({ node, ...props }) => <strong className="text-white font-semibold" {...props} />,
                  em: ({ node, ...props }) => <em className="text-[#00F5FF]" {...props} />,
                  a: ({ node, ...props }) => <a className="text-[#FF006E] hover:underline" {...props} />,
                  code: ({ node, ...props }) => <code className="text-[#00F5FF] bg-white/10 px-1 rounded" {...props} />,
                }}
              >
                {`Exploring the intersection of **digital art** and *cyberpunk aesthetics*. 
              
Commissions: [Open](https://example.com) | Tools: \`Blender\`, \`Photoshop\`, \`Procreate\`

*"Creating worlds that exist between reality and imagination."*`}
              </ReactMarkdown>
            </div>
          </div>

          {/* Action Buttons - Mobile */}
          <div className="flex md:hidden items-center gap-2 mt-4">
            <button className="flex-1 px-6 py-2.5 border border-white/20 rounded-md hover:bg-white/10 transition-colors text-xl">
              <span style={{ filter: 'drop-shadow(0 0 8px rgba(0, 245, 255, 0.8))' }}>👣</span>
            </button>
            <button 
              className="p-2.5 border border-white/20 rounded-md hover:bg-white/10 transition-colors"
              aria-label="Send gift"
            >
              <Gift className="w-5 h-5 text-[#00F5FF]" />
            </button>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="border-b border-white/20 mb-6">
          <div className="flex gap-8">
            <button
              onClick={() => setActiveTab('gallery')}
              className={`pb-3 px-1 relative transition-colors ${
                activeTab === 'gallery' ? 'text-white' : 'text-white/50 hover:text-white/80'
              }`}
              style={activeTab === 'gallery' ? { filter: 'drop-shadow(0 4px 12px rgba(255, 255, 255, 0.6))' } : undefined}
            >
              🖼️
              {activeTab === 'gallery' && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-[#FF006E] to-[#00F5FF]" />
              )}
            </button>
            <button
              onClick={() => setActiveTab('favourites')}
              className={`pb-3 px-1 relative transition-colors ${
                activeTab === 'favourites' ? 'text-white' : 'text-white/50 hover:text-white/80'
              }`}
              style={activeTab === 'favourites' ? { filter: 'drop-shadow(0 4px 12px rgba(255, 255, 255, 0.6))' } : undefined}
            >
              ⚡
              {activeTab === 'favourites' && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-gradient-to-r from-[#FF006E] to-[#00F5FF]" />
              )}
            </button>
          </div>
        </div>

        {/* Highlights Section */}
        <div className="mb-8">
          <h2 className="text-lg mb-4" style={{ filter: 'drop-shadow(0 4px 12px rgba(255, 255, 255, 0.6))' }}>💎</h2>
          <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-hide">
            {highlights.map((highlight) => (
              <button
                key={highlight.id}
                onClick={() => setSelectedHighlight(highlight.id)}
                className={`flex-shrink-0 group ${
                  selectedHighlight === highlight.id ? 'ring-2 ring-[#FF006E]' : ''
                }`}
              >
                <div className="relative w-32 h-32 overflow-hidden mb-2">
                  <img
                    src={highlight.image}
                    alt={highlight.title}
                    className="w-full h-full object-cover transition-transform group-hover:scale-105"
                  />
                  {selectedHighlight === highlight.id && (
                    <div className="absolute inset-0 bg-gradient-to-t from-[#FF006E]/20 to-transparent" />
                  )}
                </div>
                <div className="text-left px-1 w-32">
                  <h3 className="text-sm mb-1 truncate">{highlight.title}</h3>
                  <div className="flex items-center gap-3 text-xs text-white/60">
                    <div className="flex items-center gap-1">
                      <Heart className="w-3 h-3" />
                      <span>{(highlight.reactions / 1000).toFixed(1)}K</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <MessageCircle className="w-3 h-3" />
                      <span>{highlight.comments}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Eye className="w-3 h-3" />
                      <span>{(highlight.views / 1000).toFixed(1)}K</span>
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Content Grid */}
        <div className="pb-8">
          <div className="flex flex-wrap">
            {galleryItems.map((item) => (
              <button
                key={item.id}
                className="relative w-32 h-32 group overflow-hidden border border-white/10 hover:border-[#00F5FF]/50 transition-colors"
              >
                <img
                  src={item.image}
                  alt={`Gallery item ${item.id}`}
                  className="w-full h-full object-cover transition-transform group-hover:scale-110"
                />
                {/* Hover overlay */}
                <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-4">
                  <div className="flex items-center gap-1 text-white">
                    <Heart className="w-4 h-4" />
                    <span className="text-sm">{item.likes}</span>
                  </div>
                  <div className="flex items-center gap-1 text-white">
                    <MessageCircle className="w-4 h-4" />
                    <span className="text-sm">{item.comments}</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Custom scrollbar hiding */}
      <style>{`
        .scrollbar-hide::-webkit-scrollbar {
          display: none;
        }
        .scrollbar-hide {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
      `}</style>
    </div>
  );
}