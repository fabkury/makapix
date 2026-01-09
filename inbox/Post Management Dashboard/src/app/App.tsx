import { useState } from 'react';
import { ArtworkTable } from './components/ArtworkTable';
import { BulkActionsPanel } from './components/BulkActionsPanel';
import { DownloadRequestsPanel, DownloadRequest } from './components/DownloadRequestsPanel';
import { Toaster } from './components/ui/sonner';
import { toast } from 'sonner';

// Mock artwork data
const generateMockArtworks = () => {
  const artworks = [
    {
      id: '1',
      imageUrl: 'https://images.unsplash.com/photo-1681235014294-588fea095706?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Abstract Harmony',
      description: 'A vibrant exploration of color and form, this abstract piece captures the essence of modern artistic expression.',
      uploadDate: '2025-12-15',
      reactions: 127,
      comments: 34,
      views: 3240,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 450, // 450 KiB
      width: 1920,
      height: 1080
    },
    {
      id: '2',
      imageUrl: 'https://images.unsplash.com/photo-1544954617-f5c6b0d16164?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Mountain Serenity',
      description: 'Breathtaking landscape capturing the majestic beauty of mountain ranges during golden hour.',
      uploadDate: '2025-12-10',
      reactions: 89,
      comments: 21,
      views: 1820,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'webp',
      fileSize: 1024 * 320, // 320 KiB
      width: 3840,
      height: 2160
    },
    {
      id: '3',
      imageUrl: 'https://images.unsplash.com/photo-1544124094-8aea0374da93?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Portrait in Light',
      description: 'A stunning portrait that demonstrates the interplay between natural light and human emotion.',
      uploadDate: '2025-12-08',
      reactions: 203,
      comments: 67,
      views: 5670,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 1024 * 2.3, // 2.3 MiB
      width: 1080,
      height: 1920
    },
    {
      id: '4',
      imageUrl: 'https://images.unsplash.com/photo-1587120511358-98f9104cc096?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Digital Dreams',
      description: 'Contemporary digital illustration merging fantasy and reality in a unique visual narrative.',
      uploadDate: '2025-12-05',
      reactions: 1560,
      comments: 420,
      views: 125000,
      isHidden: true,
      frameCount: 48,
      fileFormat: 'gif',
      fileSize: 1024 * 1024 * 4.8, // 4.8 MiB
      width: 1920,
      height: 1080
    },
    {
      id: '5',
      imageUrl: 'https://images.unsplash.com/photo-1720303429758-92e2123800cc?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Sculptural Form',
      description: 'Three-dimensional artwork exploring the relationship between space, mass, and negative space.',
      uploadDate: '2025-12-01',
      reactions: 940,
      comments: 280,
      views: 45600,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 890, // 890 KiB
      width: 1200,
      height: 1200
    },
    {
      id: '6',
      imageUrl: 'https://images.unsplash.com/photo-1558522195-e1201b090344?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Modern Perspective',
      description: 'Bold contemporary art piece that challenges traditional perspectives and invites viewer interpretation.',
      uploadDate: '2025-11-28',
      reactions: 178,
      comments: 51,
      views: 8920,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'bmp',
      fileSize: 1024 * 1024 * 3.2, // 3.2 MiB
      width: 2560,
      height: 1440
    },
    {
      id: '7',
      imageUrl: 'https://images.unsplash.com/photo-1681235014294-588fea095706?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Color Symphony',
      description: 'An energetic composition where colors dance together creating a visual symphony of expression.',
      uploadDate: '2025-11-25',
      reactions: 14200,
      comments: 3900,
      views: 1240000,
      isHidden: false,
      frameCount: 120,
      fileFormat: 'webp',
      fileSize: 1024 * 1024 * 3.5, // 3.5 MiB
      width: 1920,
      height: 1080
    },
    {
      id: '8',
      imageUrl: 'https://images.unsplash.com/photo-1544954617-f5c6b0d16164?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Coastal Sunset',
      description: 'Dramatic seascape photography showcasing the raw power and beauty of ocean waves at dusk.',
      uploadDate: '2025-11-22',
      reactions: 2110,
      comments: 730,
      views: 234000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 780, // 780 KiB
      width: 3840,
      height: 2160
    },
    {
      id: '9',
      imageUrl: 'https://images.unsplash.com/photo-1544124094-8aea0374da93?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Human Connection',
      description: 'Intimate portrait series exploring themes of identity, vulnerability, and authentic human connection.',
      uploadDate: '2025-11-18',
      reactions: 18700,
      comments: 6200,
      views: 2500000,
      isHidden: true,
      frameCount: 30,
      fileFormat: 'gif',
      fileSize: 1024 * 1024 * 4.1, // 4.1 MiB
      width: 1080,
      height: 1920
    },
    {
      id: '10',
      imageUrl: 'https://images.unsplash.com/photo-1587120511358-98f9104cc096?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Pixel Perfect',
      description: 'Meticulously crafted digital artwork combining traditional techniques with cutting-edge technology.',
      uploadDate: '2025-11-15',
      reactions: 1650,
      comments: 480,
      views: 89500,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 1024 * 1.2, // 1.2 MiB
      width: 1600,
      height: 900
    },
    {
      id: '11',
      imageUrl: 'https://images.unsplash.com/photo-1720303429758-92e2123800cc?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Material Study',
      description: 'Sculptural exploration of texture, material properties, and the boundaries of physical form.',
      uploadDate: '2025-11-12',
      reactions: 103,
      comments: 31,
      views: 4560,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'webp',
      fileSize: 1024 * 250, // 250 KiB
      width: 1080,
      height: 1080
    },
    {
      id: '12',
      imageUrl: 'https://images.unsplash.com/photo-1558522195-e1201b090344?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Urban Canvas',
      description: 'Contemporary street art piece that transforms public spaces into galleries of social commentary.',
      uploadDate: '2025-11-08',
      reactions: 22900,
      comments: 8100,
      views: 3750000,
      isHidden: false,
      frameCount: 60,
      fileFormat: 'webp',
      fileSize: 1024 * 1024 * 2.9, // 2.9 MiB
      width: 1920,
      height: 1080
    },
    {
      id: '13',
      imageUrl: 'https://images.unsplash.com/photo-1681235014294-588fea095706?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Fluid Motion',
      description: 'Dynamic abstract work capturing movement and energy through sweeping brushstrokes and color gradients.',
      uploadDate: '2025-11-05',
      reactions: 1340,
      comments: 440,
      views: 156000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 1024 * 1.8, // 1.8 MiB
      width: 2160,
      height: 3840
    },
    {
      id: '14',
      imageUrl: 'https://images.unsplash.com/photo-1544954617-f5c6b0d16164?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Nature\'s Architecture',
      description: 'Landscape photography revealing the geometric patterns and structures hidden within natural environments.',
      uploadDate: '2025-11-01',
      reactions: 1980,
      comments: 590,
      views: 298000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'bmp',
      fileSize: 1024 * 1024 * 4.5, // 4.5 MiB
      width: 3840,
      height: 2160
    },
    {
      id: '15',
      imageUrl: 'https://images.unsplash.com/photo-1544124094-8aea0374da93?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Silent Stories',
      description: 'Evocative portrait series that tells stories through expression, lighting, and careful composition.',
      uploadDate: '2025-10-28',
      reactions: 17600,
      comments: 5500,
      views: 1850000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 1024 * 2.1, // 2.1 MiB
      width: 1080,
      height: 1920
    },
    {
      id: '16',
      imageUrl: 'https://images.unsplash.com/photo-1587120511358-98f9104cc096?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Neon Dreams',
      description: 'Futuristic digital art combining vibrant neon colors with cyberpunk aesthetics.',
      uploadDate: '2025-10-25',
      reactions: 3240,
      comments: 890,
      views: 567000,
      isHidden: false,
      frameCount: 24,
      fileFormat: 'gif',
      fileSize: 1024 * 1024 * 3.7, // 3.7 MiB
      width: 1920,
      height: 1080
    },
    {
      id: '17',
      imageUrl: 'https://images.unsplash.com/photo-1720303429758-92e2123800cc?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Organic Forms',
      description: 'Abstract sculpture inspired by natural shapes and biological patterns found in nature.',
      uploadDate: '2025-10-22',
      reactions: 890,
      comments: 210,
      views: 78900,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 920, // 920 KiB
      width: 1200,
      height: 1200
    },
    {
      id: '18',
      imageUrl: 'https://images.unsplash.com/photo-1558522195-e1201b090344?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Geometric Balance',
      description: 'Minimalist composition exploring the relationship between geometric shapes and color theory.',
      uploadDate: '2025-10-19',
      reactions: 4560,
      comments: 1200,
      views: 892000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'webp',
      fileSize: 1024 * 450, // 450 KiB
      width: 1600,
      height: 900
    },
    {
      id: '19',
      imageUrl: 'https://images.unsplash.com/photo-1681235014294-588fea095706?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Chromatic Chaos',
      description: 'Explosive abstract expressionism with layers of contrasting colors and textures.',
      uploadDate: '2025-10-16',
      reactions: 12300,
      comments: 3400,
      views: 1450000,
      isHidden: true,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 1024 * 2.8, // 2.8 MiB
      width: 1920,
      height: 1080
    },
    {
      id: '20',
      imageUrl: 'https://images.unsplash.com/photo-1544954617-f5c6b0d16164?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Alpine Majesty',
      description: 'Breathtaking mountain landscape showcasing the pristine beauty of high-altitude environments.',
      uploadDate: '2025-10-13',
      reactions: 2780,
      comments: 720,
      views: 456000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 680, // 680 KiB
      width: 3840,
      height: 2160
    },
    {
      id: '21',
      imageUrl: 'https://images.unsplash.com/photo-1544124094-8aea0374da93?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Emotional Depth',
      description: 'Powerful portrait capturing raw human emotion through masterful use of light and shadow.',
      uploadDate: '2025-10-10',
      reactions: 8900,
      comments: 2100,
      views: 980000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 1024 * 1.9, // 1.9 MiB
      width: 1080,
      height: 1920
    },
    {
      id: '22',
      imageUrl: 'https://images.unsplash.com/photo-1587120511358-98f9104cc096?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Digital Frontier',
      description: 'Cutting-edge digital illustration exploring the intersection of art and technology.',
      uploadDate: '2025-10-07',
      reactions: 5670,
      comments: 1450,
      views: 723000,
      isHidden: false,
      frameCount: 72,
      fileFormat: 'webp',
      fileSize: 1024 * 1024 * 4.2, // 4.2 MiB
      width: 1920,
      height: 1080
    },
    {
      id: '23',
      imageUrl: 'https://images.unsplash.com/photo-1720303429758-92e2123800cc?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Spatial Awareness',
      description: 'Three-dimensional exploration of space, volume, and the boundaries between positive and negative.',
      uploadDate: '2025-10-04',
      reactions: 1120,
      comments: 340,
      views: 123000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'bmp',
      fileSize: 1024 * 1024 * 3.4, // 3.4 MiB
      width: 1080,
      height: 1080
    },
    {
      id: '24',
      imageUrl: 'https://images.unsplash.com/photo-1558522195-e1201b090344?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Street Poetry',
      description: 'Urban art installation that transforms city walls into canvases for visual storytelling.',
      uploadDate: '2025-10-01',
      reactions: 19800,
      comments: 6700,
      views: 2890000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 1024 * 2.6, // 2.6 MiB
      width: 2560,
      height: 1440
    },
    {
      id: '25',
      imageUrl: 'https://images.unsplash.com/photo-1681235014294-588fea095706?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Rainbow Cascade',
      description: 'Vibrant abstract work featuring flowing colors that blend and merge in organic patterns.',
      uploadDate: '2025-09-28',
      reactions: 3450,
      comments: 980,
      views: 567000,
      isHidden: false,
      frameCount: 96,
      fileFormat: 'gif',
      fileSize: 1024 * 1024 * 5.1, // 5.1 MiB
      width: 1920,
      height: 1080
    },
    {
      id: '26',
      imageUrl: 'https://images.unsplash.com/photo-1544954617-f5c6b0d16164?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Tidal Rhythms',
      description: 'Seascape photography exploring the perpetual motion and power of ocean waves.',
      uploadDate: '2025-09-25',
      reactions: 1890,
      comments: 520,
      views: 234000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'webp',
      fileSize: 1024 * 580, // 580 KiB
      width: 3840,
      height: 2160
    },
    {
      id: '27',
      imageUrl: 'https://images.unsplash.com/photo-1544124094-8aea0374da93?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Inner Reflections',
      description: 'Contemplative portrait series examining themes of introspection and self-discovery.',
      uploadDate: '2025-09-22',
      reactions: 15600,
      comments: 4800,
      views: 1670000,
      isHidden: true,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 1024 * 2.4, // 2.4 MiB
      width: 1080,
      height: 1920
    },
    {
      id: '28',
      imageUrl: 'https://images.unsplash.com/photo-1587120511358-98f9104cc096?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Virtual Realms',
      description: 'Immersive digital artwork that blurs the line between physical and virtual reality.',
      uploadDate: '2025-09-19',
      reactions: 7800,
      comments: 2300,
      views: 945000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 1024 * 1.7, // 1.7 MiB
      width: 1920,
      height: 1080
    },
    {
      id: '29',
      imageUrl: 'https://images.unsplash.com/photo-1720303429758-92e2123800cc?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Sculptural Poetry',
      description: 'Contemporary sculpture that speaks through form, texture, and the interplay of light.',
      uploadDate: '2025-09-16',
      reactions: 2340,
      comments: 670,
      views: 345000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 780, // 780 KiB
      width: 1200,
      height: 1200
    },
    {
      id: '30',
      imageUrl: 'https://images.unsplash.com/photo-1558522195-e1201b090344?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Minimalist Vision',
      description: 'Clean, bold composition that proves less is more through careful use of space and color.',
      uploadDate: '2025-09-13',
      reactions: 6780,
      comments: 1890,
      views: 823000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'webp',
      fileSize: 1024 * 390, // 390 KiB
      width: 1600,
      height: 900
    },
    {
      id: '31',
      imageUrl: 'https://images.unsplash.com/photo-1681235014294-588fea095706?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Color Explosion',
      description: 'Dynamic abstract piece bursting with energy and vibrant color combinations.',
      uploadDate: '2025-09-10',
      reactions: 9870,
      comments: 2890,
      views: 1120000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 1024 * 2.2, // 2.2 MiB
      width: 1920,
      height: 1080
    },
    {
      id: '32',
      imageUrl: 'https://images.unsplash.com/photo-1544954617-f5c6b0d16164?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Wilderness Echo',
      description: 'Raw landscape photography celebrating the untamed beauty of wild natural spaces.',
      uploadDate: '2025-09-07',
      reactions: 3210,
      comments: 890,
      views: 512000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'bmp',
      fileSize: 1024 * 1024 * 4.3, // 4.3 MiB
      width: 3840,
      height: 2160
    },
    {
      id: '33',
      imageUrl: 'https://images.unsplash.com/photo-1544124094-8aea0374da93?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Timeless Faces',
      description: 'Classic portrait photography that captures the essence and character of each subject.',
      uploadDate: '2025-09-04',
      reactions: 11200,
      comments: 3400,
      views: 1340000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 1024 * 1.5, // 1.5 MiB
      width: 1080,
      height: 1920
    },
    {
      id: '34',
      imageUrl: 'https://images.unsplash.com/photo-1587120511358-98f9104cc096?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Cyber Aesthetics',
      description: 'Digital art exploring themes of technology, connectivity, and our digital future.',
      uploadDate: '2025-09-01',
      reactions: 8760,
      comments: 2450,
      views: 987000,
      isHidden: false,
      frameCount: 144,
      fileFormat: 'webp',
      fileSize: 1024 * 1024 * 5.6, // 5.6 MiB
      width: 1920,
      height: 1080
    },
    {
      id: '35',
      imageUrl: 'https://images.unsplash.com/photo-1720303429758-92e2123800cc?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Material Essence',
      description: 'Sculptural study focusing on the inherent qualities and characteristics of different materials.',
      uploadDate: '2025-08-29',
      reactions: 1560,
      comments: 430,
      views: 189000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 820, // 820 KiB
      width: 1080,
      height: 1080
    },
    {
      id: '36',
      imageUrl: 'https://images.unsplash.com/photo-1558522195-e1201b090344?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Urban Patterns',
      description: 'Contemporary art piece revealing hidden patterns and symmetries in urban environments.',
      uploadDate: '2025-08-26',
      reactions: 13400,
      comments: 4200,
      views: 1780000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 1024 * 2.7, // 2.7 MiB
      width: 2560,
      height: 1440
    },
    {
      id: '37',
      imageUrl: 'https://images.unsplash.com/photo-1681235014294-588fea095706?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Paint Waves',
      description: 'Abstract expressionism featuring sweeping brushstrokes that evoke motion and fluidity.',
      uploadDate: '2025-08-23',
      reactions: 5430,
      comments: 1560,
      views: 678000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'webp',
      fileSize: 1024 * 510, // 510 KiB
      width: 1920,
      height: 1080
    },
    {
      id: '38',
      imageUrl: 'https://images.unsplash.com/photo-1544954617-f5c6b0d16164?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Mountain Whispers',
      description: 'Serene landscape capturing the quiet majesty and timeless beauty of mountain peaks.',
      uploadDate: '2025-08-20',
      reactions: 2890,
      comments: 780,
      views: 423000,
      isHidden: true,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 720, // 720 KiB
      width: 3840,
      height: 2160
    },
    {
      id: '39',
      imageUrl: 'https://images.unsplash.com/photo-1544124094-8aea0374da93?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Soul Portraits',
      description: 'Deeply personal portrait series exploring the inner world of each unique individual.',
      uploadDate: '2025-08-17',
      reactions: 16700,
      comments: 5100,
      views: 2010000,
      isHidden: false,
      frameCount: 1,
      fileFormat: 'png',
      fileSize: 1024 * 1024 * 2.0, // 2.0 MiB
      width: 1080,
      height: 1920
    },
    {
      id: '40',
      imageUrl: 'https://images.unsplash.com/photo-1587120511358-98f9104cc096?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&w=100',
      title: 'Digital Symphony',
      description: 'Multi-layered digital artwork that creates a visual symphony of colors and forms.',
      uploadDate: '2025-08-14',
      reactions: 10200,
      comments: 3100,
      views: 1230000,
      isHidden: false,
      frameCount: 60,
      fileFormat: 'gif',
      fileSize: 1024 * 1024 * 4.9, // 4.9 MiB
      width: 1920,
      height: 1080
    }
  ];
  
  return artworks;
};

export default function App() {
  const [artworks, setArtworks] = useState(generateMockArtworks());
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [currentPage, setCurrentPage] = useState(0);
  const itemsPerPage = 16;
  
  // Initialize with mock download requests
  const [downloadRequests, setDownloadRequests] = useState<DownloadRequest[]>([
    {
      id: 'req-001',
      date: '2026-01-05T14:30:00',
      artworkCount: 8,
      status: 'expired'
    },
    {
      id: 'req-002',
      date: '2026-01-06T09:15:00',
      artworkCount: 5,
      status: 'expired'
    },
    {
      id: 'req-003',
      date: '2026-01-07T11:20:00',
      artworkCount: 12,
      status: 'ready',
      expiresAt: '2026-01-09T11:20:00'
    }
  ]);

  const handleToggleHide = (id: string) => {
    setArtworks(prev => prev.map(artwork => 
      artwork.id === id ? { ...artwork, isHidden: !artwork.isHidden } : artwork
    ));
  };

  const handleDelete = (id: string) => {
    setArtworks(prev => prev.filter(artwork => artwork.id !== id));
    setSelectedIds(prev => {
      const newSet = new Set(prev);
      newSet.delete(id);
      return newSet;
    });
  };

  const handleBulkHideUnhide = () => {
    const selectedArtworks = artworks.filter(a => selectedIds.has(a.id));
    const allHidden = selectedArtworks.every(a => a.isHidden);
    
    setArtworks(prev => prev.map(artwork => 
      selectedIds.has(artwork.id) ? { ...artwork, isHidden: !allHidden } : artwork
    ));
  };

  const handleBulkHide = () => {
    setArtworks(prev => prev.map(artwork => 
      selectedIds.has(artwork.id) ? { ...artwork, isHidden: true } : artwork
    ));
  };

  const handleBulkUnhide = () => {
    setArtworks(prev => prev.map(artwork => 
      selectedIds.has(artwork.id) ? { ...artwork, isHidden: false } : artwork
    ));
  };

  const handleBulkDownload = () => {
    // Create new download request
    const newRequest: DownloadRequest = {
      id: `req-${Date.now()}`,
      date: new Date().toISOString(),
      artworkCount: selectedIds.size,
      status: 'ready',
      expiresAt: new Date(Date.now() + 48 * 60 * 60 * 1000).toISOString() // 48 hours from now
    };
    
    setDownloadRequests(prev => [newRequest, ...prev]);
    
    // Show toast notification
    toast.success('Your request has been received. When your download is ready, it will appear in the panel below.');
  };

  const handleBulkDelete = () => {
    // Delete all selected artworks
    setArtworks(prev => prev.filter(artwork => !selectedIds.has(artwork.id)));
    
    // Clear selection
    setSelectedIds(new Set());
    
    // Show toast notification
    toast.success('Selected artworks have been deleted.');
  };

  const totalPages = Math.ceil(artworks.length / itemsPerPage);

  return (
    <div className="min-h-screen bg-gray-50 lg:p-8">
      <div className="max-w-[1024px] mx-auto">
        <h1 className="mb-6 lg:px-0 px-4 pt-4 lg:pt-0">Post Management Dashboard</h1>
        
        <div className="bg-white lg:rounded-lg shadow">
          <ArtworkTable
            artworks={artworks}
            selectedIds={selectedIds}
            setSelectedIds={setSelectedIds}
            currentPage={currentPage}
            setCurrentPage={setCurrentPage}
            itemsPerPage={itemsPerPage}
            totalPages={totalPages}
            onToggleHide={handleToggleHide}
            onDelete={handleDelete}
          />
          
          <BulkActionsPanel
            selectedCount={selectedIds.size}
            onDownload={handleBulkDownload}
            onHide={handleBulkHide}
            onUnhide={handleBulkUnhide}
            onDelete={handleBulkDelete}
          />
        </div>
        
        <DownloadRequestsPanel requests={downloadRequests} />
        
        <Toaster />
      </div>
    </div>
  );
}
