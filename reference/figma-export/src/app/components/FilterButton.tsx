import { useState, useRef, useEffect } from "react";
import { Filter, X } from "lucide-react";
import { ScrollArea } from "./ui/scroll-area";
import { Label } from "./ui/label";
import { Input } from "./ui/input";
import { Checkbox } from "./ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Separator } from "./ui/separator";
import { Button } from "./ui/button";
import { Slider } from "./ui/slider";

export interface FilterConfig {
  // Numeric filters
  width?: { min?: number; max?: number };
  height?: { min?: number; max?: number };
  file_bytes?: { min?: number; max?: number };
  frame_count?: { min?: number; max?: number };
  unique_colors?: { min?: number; max?: number };
  reactions?: { min?: number; max?: number };
  comments?: { min?: number; max?: number };
  
  // Date filters
  creation_date?: { min?: string; max?: string };
  
  // Boolean filters
  has_transparency?: boolean | null;
  has_semitransparency?: boolean | null;
  
  // Array filters (multi-select)
  file_format?: string[];
  kind?: string[];
  
  // Sorting
  sortBy?: string;
  sortOrder?: "asc" | "desc";
}

interface FilterButtonProps {
  onFilterChange: (filters: FilterConfig) => void;
  initialFilters?: FilterConfig;
}

export function FilterButton({ onFilterChange, initialFilters = {} }: FilterButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [filters, setFilters] = useState<FilterConfig>({
    file_format: ["PNG", "GIF", "WEBP", "BMP"],
    kind: ["static", "animated"],
    ...initialFilters
  });
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Click outside to close
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        isOpen &&
        menuRef.current &&
        buttonRef.current &&
        !menuRef.current.contains(event.target as Node) &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  const updateFilter = (key: string, value: any) => {
    const newFilters = { ...filters, [key]: value };
    setFilters(newFilters);
    onFilterChange(newFilters);
  };

  const updateNumericFilter = (field: string, type: "min" | "max", value: string) => {
    const numValue = value === "" ? undefined : Number(value);
    const currentFilter = (filters as any)[field] || {};
    const newFilter = { ...currentFilter, [type]: numValue };
    updateFilter(field, newFilter);
  };

  const updateSliderFilter = (field: string, values: number[]) => {
    const newFilter = { min: values[0], max: values[1] };
    updateFilter(field, newFilter);
  };

  // Convert slider position (0-100) to actual pixel value
  const sliderToPixelValue = (sliderValue: number): number => {
    if (sliderValue <= 50) {
      // Left half: evenly distributed among 8, 16, 32, 64, 128
      const discreteValues = [8, 16, 32, 64, 128];
      const segmentSize = 50 / (discreteValues.length - 1); // 12.5
      const index = Math.round(sliderValue / segmentSize);
      return discreteValues[Math.min(index, discreteValues.length - 1)];
    } else {
      // Right half: linear from 128 to 256
      const normalizedValue = (sliderValue - 50) / 50; // 0 to 1
      return Math.round(128 + normalizedValue * 128);
    }
  };

  // Convert pixel value to slider position (0-100)
  const pixelToSliderValue = (pixelValue: number): number => {
    if (pixelValue <= 128) {
      // Map to discrete positions
      const discreteValues = [8, 16, 32, 64, 128];
      const index = discreteValues.findIndex(v => v >= pixelValue);
      const actualIndex = index === -1 ? discreteValues.length - 1 : index;
      const segmentSize = 50 / (discreteValues.length - 1); // 12.5
      return actualIndex * segmentSize;
    } else {
      // Linear mapping from 128-256 to 50-100
      const normalizedValue = (pixelValue - 128) / 128;
      return 50 + normalizedValue * 50;
    }
  };

  const updateDimensionFilter = (field: string, sliderValues: number[]) => {
    // Convert slider values to actual pixel values
    const minPixels = sliderToPixelValue(sliderValues[0]);
    const maxPixels = sliderToPixelValue(sliderValues[1]);
    
    const newFilter = { min: minPixels, max: maxPixels };
    updateFilter(field, newFilter);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes >= 1024 * 1024) {
      return `${(bytes / (1024 * 1024)).toFixed(2)} MiB`;
    }
    return `${(bytes / 1024).toFixed(0)} KiB`;
  };

  // Date utilities
  const today = new Date();
  const sixMonthsAgo = new Date();
  sixMonthsAgo.setMonth(today.getMonth() - 6);

  const dateToTimestamp = (date: Date): number => date.getTime();
  const timestampToDate = (timestamp: number): Date => new Date(timestamp);

  const minTimestamp = dateToTimestamp(sixMonthsAgo);
  const maxTimestamp = dateToTimestamp(today);

  const formatDate = (date: Date): string => {
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const updateDateFilter = (timestamps: number[]) => {
    const minDate = timestampToDate(timestamps[0]).toISOString().split('T')[0];
    const maxDate = timestampToDate(timestamps[1]).toISOString().split('T')[0];
    updateFilter("creation_date", { min: minDate, max: maxDate });
  };

  const getCurrentDateRange = (): [number, number] => {
    const minDate = filters.creation_date?.min 
      ? dateToTimestamp(new Date(filters.creation_date.min))
      : minTimestamp;
    const maxDate = filters.creation_date?.max
      ? dateToTimestamp(new Date(filters.creation_date.max))
      : maxTimestamp;
    return [minDate, maxDate];
  };

  const toggleMultiSelect = (field: "file_format" | "kind", value: string) => {
    const current = filters[field] || [];
    const newValue = current.includes(value)
      ? current.filter(v => v !== value)
      : [...current, value];
    updateFilter(field, newValue.length > 0 ? newValue : undefined);
  };

  const clearFilters = () => {
    const defaultFilters = { 
      sortBy: "creation_date", 
      sortOrder: "desc" as "desc",
      file_format: ["PNG", "GIF", "WEBP", "BMP"],
      kind: ["static", "animated"]
    };
    setFilters(defaultFilters);
    onFilterChange(defaultFilters);
  };

  return (
    <div className="fixed top-20 left-6 z-50">
      {/* Round Floating Button */}
      <button
        ref={buttonRef}
        onClick={() => setIsOpen(!isOpen)}
        className={`w-14 h-14 rounded-full bg-blue-600 hover:bg-blue-700 text-white shadow-lg flex items-center justify-center transition-all duration-200 hover:scale-105 ${isOpen ? 'opacity-0 pointer-events-none md:opacity-100 md:pointer-events-auto' : ''}`}
        aria-label="Toggle filters"
      >
        {isOpen ? <X size={24} /> : <Filter size={24} />}
      </button>

      {/* Floating Menu */}
      {isOpen && (
        <div
          ref={menuRef}
          className="fixed top-20 left-0 md:absolute md:top-0 md:left-16 w-[80%] max-w-sm md:max-w-xs bg-white rounded-r-lg shadow-2xl border-r border-t border-b border-gray-200 overflow-hidden max-h-[calc(100vh-5rem)]"
        >
          <div className="p-4 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">Filter & Sort</h3>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                Clear All
              </Button>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 hover:bg-gray-200 rounded transition-colors"
                aria-label="Close menu"
              >
                <X size={20} className="text-gray-600" />
              </button>
            </div>
          </div>

          <ScrollArea className="h-[calc(100vh-12rem)] md:h-[500px]">
            <div className="p-4 space-y-6">
              {/* Sorting Section */}
              <div className="space-y-3">
                <h4 className="font-medium text-gray-900">Sort By</h4>
                <div className="space-y-2">
                  <Select
                    value={filters.sortBy || "creation_date"}
                    onValueChange={(value) => updateFilter("sortBy", value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select field" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="creation_date">Creation Date</SelectItem>
                      <SelectItem value="width">Width</SelectItem>
                      <SelectItem value="height">Height</SelectItem>
                      <SelectItem value="file_bytes">File Size</SelectItem>
                      <SelectItem value="frame_count">Frame Count</SelectItem>
                      <SelectItem value="unique_colors">Unique Colors</SelectItem>
                      <SelectItem value="reactions">Reactions</SelectItem>
                      <SelectItem value="comments">Comments</SelectItem>
                    </SelectContent>
                  </Select>
                  
                  <Select
                    value={filters.sortOrder || "desc"}
                    onValueChange={(value: "asc" | "desc") => updateFilter("sortOrder", value)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Order" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="asc">Ascending</SelectItem>
                      <SelectItem value="desc">Descending</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <Separator />

              {/* Numeric Filters */}
              <div className="space-y-4">
                {/* Width */}
                <div className="space-y-2">
                  <Label>Width (px): {filters.width?.min || 8} - {filters.width?.max || 256}</Label>
                  <Slider
                    min={0}
                    max={100}
                    step={1}
                    value={[
                      pixelToSliderValue(filters.width?.min || 8),
                      pixelToSliderValue(filters.width?.max || 256)
                    ]}
                    onValueChange={(values) => updateDimensionFilter("width", values)}
                  />
                </div>

                {/* Height */}
                <div className="space-y-2">
                  <Label>Height (px): {filters.height?.min || 8} - {filters.height?.max || 256}</Label>
                  <Slider
                    min={0}
                    max={100}
                    step={1}
                    value={[
                      pixelToSliderValue(filters.height?.min || 8),
                      pixelToSliderValue(filters.height?.max || 256)
                    ]}
                    onValueChange={(values) => updateDimensionFilter("height", values)}
                  />
                </div>

                {/* File Bytes */}
                <div className="space-y-2">
                  <Label>File Size: {formatFileSize(filters.file_bytes?.min || 0)} - {formatFileSize(filters.file_bytes?.max || 5242880)}</Label>
                  <Slider
                    min={0}
                    max={5242880}
                    step={1024}
                    value={[filters.file_bytes?.min || 0, filters.file_bytes?.max || 5242880]}
                    onValueChange={(values) => updateSliderFilter("file_bytes", values)}
                  />
                </div>

                {/* Frame Count */}
                <div className="space-y-2">
                  <Label>
                    Frame Count: {filters.frame_count?.min || 1} - {filters.frame_count?.max === 256 || filters.frame_count?.max === undefined ? "256+" : filters.frame_count.max}
                  </Label>
                  <Slider
                    min={1}
                    max={256}
                    step={1}
                    value={[filters.frame_count?.min || 1, filters.frame_count?.max || 256]}
                    onValueChange={(values) => updateSliderFilter("frame_count", values)}
                  />
                </div>

                {/* Unique Colors Per Frame */}
                <div className="space-y-2">
                  <Label>
                    Unique Colors Per Frame: {filters.unique_colors?.min || 1} - {filters.unique_colors?.max === 256 || filters.unique_colors?.max === undefined ? "256+" : filters.unique_colors.max}
                  </Label>
                  <Slider
                    min={1}
                    max={256}
                    step={1}
                    value={[filters.unique_colors?.min || 1, filters.unique_colors?.max || 256]}
                    onValueChange={(values) => updateSliderFilter("unique_colors", values)}
                  />
                </div>
              </div>

              <Separator />

              {/* Boolean Filters */}
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>Transparency</Label>
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => updateFilter("has_transparency", filters.has_transparency === true ? null : true)}
                      className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
                        filters.has_transparency === true
                          ? "bg-blue-600 text-white"
                          : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                      }`}
                    >
                      Has Transparency
                    </button>
                    <button
                      onClick={() => updateFilter("has_semitransparency", filters.has_semitransparency === true ? null : true)}
                      className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
                        filters.has_semitransparency === true
                          ? "bg-blue-600 text-white"
                          : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                      }`}
                    >
                      Has Semitransparency
                    </button>
                  </div>
                </div>

                {/* File Format */}
                <div className="space-y-2">
                  <Label>File Format</Label>
                  <div className="flex flex-wrap gap-2">
                    {["PNG", "GIF", "WEBP", "BMP"].map((format) => (
                      <button
                        key={format}
                        onClick={() => toggleMultiSelect("file_format", format)}
                        className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
                          filters.file_format?.includes(format)
                            ? "bg-blue-600 text-white"
                            : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                        }`}
                      >
                        {format}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Kind */}
                <div className="space-y-2">
                  <Label>Animation</Label>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { value: "static", label: "Static" },
                      { value: "animated", label: "Animated" }
                    ].map((kind) => (
                      <button
                        key={kind.value}
                        onClick={() => toggleMultiSelect("kind", kind.value)}
                        className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
                          filters.kind?.includes(kind.value)
                            ? "bg-blue-600 text-white"
                            : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                        }`}
                      >
                        {kind.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <Separator />

              {/* Engagement Metrics */}
              <div className="space-y-4">
                {/* Creation Date */}
                <div className="space-y-2">
                  <Label>
                    Creation Date: {formatDate(timestampToDate(getCurrentDateRange()[0]))} - {formatDate(timestampToDate(getCurrentDateRange()[1]))}
                  </Label>
                  <Slider
                    min={minTimestamp}
                    max={maxTimestamp}
                    step={86400000} // 1 day in milliseconds
                    value={getCurrentDateRange()}
                    onValueChange={(values) => updateDateFilter(values)}
                  />
                </div>

                {/* Reactions */}
                <div className="space-y-2">
                  <Label>
                    Reactions: {filters.reactions?.min || 0} - {filters.reactions?.max === 256 || filters.reactions?.max === undefined ? "256+" : filters.reactions.max}
                  </Label>
                  <Slider
                    min={0}
                    max={256}
                    step={1}
                    value={[filters.reactions?.min || 0, filters.reactions?.max || 256]}
                    onValueChange={(values) => updateSliderFilter("reactions", values)}
                  />
                </div>

                {/* Comments */}
                <div className="space-y-2">
                  <Label>
                    Comments: {filters.comments?.min || 0} - {filters.comments?.max === 256 || filters.comments?.max === undefined ? "256+" : filters.comments.max}
                  </Label>
                  <Slider
                    min={0}
                    max={256}
                    step={1}
                    value={[filters.comments?.min || 0, filters.comments?.max || 256]}
                    onValueChange={(values) => updateSliderFilter("comments", values)}
                  />
                </div>
              </div>
            </div>
          </ScrollArea>
        </div>
      )}
    </div>
  );
}