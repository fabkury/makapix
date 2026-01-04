import { useState } from "react";
import { FilterButton, FilterConfig } from "./components/FilterButton";

// Mock artwork data
interface Artwork {
  id: number;
  title: string;
  width: number;
  height: number;
  file_bytes: number;
  frame_count: number;
  unique_colors: number | null;
  has_transparency: boolean;
  has_semitransparency: boolean;
  file_format: string;
  kind: string;
  creation_date: string;
  imageUrl: string;
}

const mockArtworks: Artwork[] = [
  {
    id: 1,
    title: "Abstract Waves",
    width: 192,
    height: 108,
    file_bytes: 245600,
    frame_count: 1,
    unique_colors: 15432,
    has_transparency: false,
    has_semitransparency: false,
    file_format: "PNG",
    kind: "static",
    creation_date: "2025-12-15",
    imageUrl: "https://images.unsplash.com/photo-1541701494587-cb58502866ab?w=400",
  },
  {
    id: 2,
    title: "Mountain Landscape",
    width: 256,
    height: 144,
    file_bytes: 512000,
    frame_count: 1,
    unique_colors: 23456,
    has_transparency: false,
    has_semitransparency: false,
    file_format: "PNG",
    kind: "static",
    creation_date: "2025-11-20",
    imageUrl: "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400",
  },
  {
    id: 3,
    title: "Urban Night",
    width: 128,
    height: 72,
    file_bytes: 156800,
    frame_count: 1,
    unique_colors: 8765,
    has_transparency: true,
    has_semitransparency: true,
    file_format: "PNG",
    kind: "static",
    creation_date: "2026-01-02",
    imageUrl: "https://images.unsplash.com/photo-1480714378408-67cf0d13bc1b?w=400",
  },
  {
    id: 4,
    title: "Animated Logo",
    width: 80,
    height: 60,
    file_bytes: 89600,
    frame_count: 24,
    unique_colors: 256,
    has_transparency: true,
    has_semitransparency: true,
    file_format: "GIF",
    kind: "animated",
    creation_date: "2025-10-10",
    imageUrl: "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400",
  },
  {
    id: 5,
    title: "Gradient Design",
    width: 160,
    height: 90,
    file_bytes: 72000,
    frame_count: 1,
    unique_colors: 65536,
    has_transparency: false,
    has_semitransparency: false,
    file_format: "WEBP",
    kind: "static",
    creation_date: "2025-12-28",
    imageUrl: "https://images.unsplash.com/photo-1557672172-298e090bd0f1?w=400",
  },
  {
    id: 6,
    title: "Simple Icon",
    width: 64,
    height: 64,
    file_bytes: 4096,
    frame_count: 1,
    unique_colors: 8,
    has_transparency: true,
    has_semitransparency: true,
    file_format: "PNG",
    kind: "static",
    creation_date: "2025-09-05",
    imageUrl: "https://images.unsplash.com/photo-1618005198919-d3d4b5a92ead?w=400",
  },
  {
    id: 7,
    title: "Nature Photo",
    width: 240,
    height: 180,
    file_bytes: 1024000,
    frame_count: 1,
    unique_colors: 45678,
    has_transparency: false,
    has_semitransparency: false,
    file_format: "PNG",
    kind: "static",
    creation_date: "2026-01-01",
    imageUrl: "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=400",
  },
  {
    id: 8,
    title: "Digital Art",
    width: 200,
    height: 200,
    file_bytes: 524288,
    frame_count: 1,
    unique_colors: 32768,
    has_transparency: true,
    has_semitransparency: false,
    file_format: "PNG",
    kind: "static",
    creation_date: "2025-08-14",
    imageUrl: "https://images.unsplash.com/photo-1550859492-d5da9d8e45f3?w=400",
  },
];

export default function App() {
  const [filters, setFilters] = useState<FilterConfig>({ sortBy: "creation_date", sortOrder: "desc" });

  // Apply filters to artworks
  const filteredArtworks = mockArtworks.filter((artwork) => {
    // Numeric filters
    if (filters.width?.min && artwork.width < filters.width.min) return false;
    if (filters.width?.max && artwork.width > filters.width.max) return false;
    if (filters.height?.min && artwork.height < filters.height.min) return false;
    if (filters.height?.max && artwork.height > filters.height.max) return false;
    if (filters.file_bytes?.min && artwork.file_bytes < filters.file_bytes.min) return false;
    if (filters.file_bytes?.max && artwork.file_bytes > filters.file_bytes.max) return false;
    if (filters.frame_count?.min && artwork.frame_count < filters.frame_count.min) return false;
    if (filters.frame_count?.max && artwork.frame_count > filters.frame_count.max) return false;
    
    if (filters.unique_colors?.min && artwork.unique_colors !== null && artwork.unique_colors < filters.unique_colors.min) return false;
    if (filters.unique_colors?.max && artwork.unique_colors !== null && artwork.unique_colors > filters.unique_colors.max) return false;

    // Date filters
    if (filters.creation_date?.min && artwork.creation_date < filters.creation_date.min) return false;
    if (filters.creation_date?.max && artwork.creation_date > filters.creation_date.max) return false;

    // Boolean filters
    if (filters.has_transparency !== undefined && filters.has_transparency !== null && artwork.has_transparency !== filters.has_transparency) return false;
    if (filters.has_semitransparency !== undefined && filters.has_semitransparency !== null && artwork.has_semitransparency !== filters.has_semitransparency) return false;

    // Enum filters
    if (filters.file_format && filters.file_format !== "null" && artwork.file_format !== filters.file_format) return false;
    if (filters.kind && filters.kind !== "null" && artwork.kind !== filters.kind) return false;

    return true;
  });

  // Apply sorting
  const sortedArtworks = [...filteredArtworks].sort((a, b) => {
    if (!filters.sortBy) return 0;
    
    const aVal = (a as any)[filters.sortBy];
    const bVal = (b as any)[filters.sortBy];
    
    if (aVal === null || bVal === null) return 0;
    
    const order = filters.sortOrder === "desc" ? -1 : 1;
    
    // For strings (like dates), use localeCompare
    if (typeof aVal === "string" && typeof bVal === "string") {
      return aVal.localeCompare(bVal) * order;
    }
    
    return aVal > bVal ? order : -order;
  });

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <h1 className="text-gray-900">Artwork Gallery</h1>
          <p className="text-gray-600">Browse and filter artwork collection</p>
        </div>
      </header>

      {/* Filter Button */}
      <FilterButton onFilterChange={setFilters} initialFilters={filters} />

      {/* Gallery */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="mb-4">
          <p className="text-gray-600">
            Showing {sortedArtworks.length} of {mockArtworks.length} artworks
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
          {sortedArtworks.map((artwork) => (
            <div
              key={artwork.id}
              className="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow"
            >
              <div className="aspect-square bg-gray-200">
                <img
                  src={artwork.imageUrl}
                  alt={artwork.title}
                  className="w-full h-full object-cover"
                />
              </div>
              <div className="p-4">
                <h3 className="text-gray-900 mb-2">{artwork.title}</h3>
                <div className="space-y-1 text-sm text-gray-600">
                  <p>
                    {artwork.width} × {artwork.height} px
                  </p>
                  <p>{(artwork.file_bytes / 1024).toFixed(1)} KB</p>
                  <p className="text-xs">
                    {artwork.file_format} • {artwork.kind}
                  </p>
                  {artwork.frame_count > 1 && (
                    <p className="text-xs text-blue-600">{artwork.frame_count} frames</p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {sortedArtworks.length === 0 && (
          <div className="text-center py-12">
            <p className="text-gray-500">No artworks match the selected filters.</p>
          </div>
        )}
      </main>
    </div>
  );
}