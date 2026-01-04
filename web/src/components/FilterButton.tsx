import { useState, useRef, useEffect, useCallback } from "react";
import { Filter, X } from "lucide-react";
import { ScrollArea } from "./ui/ScrollArea";
import { Slider } from "./ui/Slider";
import { Select } from "./ui/Select";
import { FilterConfig } from "../hooks/useFilters";

// Same thresholds as Layout.tsx header hide/show
const HIDE_AT = 128 * 2; // ~2 rows
const SHOW_AT = 64; // hysteresis to avoid flicker near the top

interface FilterButtonProps {
  onFilterChange: (filters: FilterConfig) => void;
  initialFilters?: FilterConfig;
  isLoading?: boolean;
}

export function FilterButton({ onFilterChange, initialFilters = {}, isLoading = false }: FilterButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isHidden, setIsHidden] = useState(false);
  const [showLoadingMessage, setShowLoadingMessage] = useState(false);
  // Applied filters (what's actually being used for queries)
  const [appliedFilters, setAppliedFilters] = useState<FilterConfig>({
    file_format: ["png", "gif", "webp", "bmp"],
    kind: ["static", "animated"],
    sortBy: "created_at",
    sortOrder: "desc",
    ...initialFilters
  });
  // Draft filters (what the user is editing in the menu)
  const [draftFilters, setDraftFilters] = useState<FilterConfig>({
    file_format: ["png", "gif", "webp", "bmp"],
    kind: ["static", "animated"],
    sortBy: "created_at",
    sortOrder: "desc",
    ...initialFilters
  });
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Sync with initialFilters when they change
  useEffect(() => {
    const newFilters = {
      ...initialFilters,
      file_format: initialFilters.file_format || ["png", "gif", "webp", "bmp"],
      kind: initialFilters.kind || ["static", "animated"],
    };
    setAppliedFilters(prev => ({ ...prev, ...newFilters }));
    setDraftFilters(prev => ({ ...prev, ...newFilters }));
  }, [initialFilters]);

  // Apply draft filters and close the menu
  const closeAndApply = () => {
    setIsOpen(false);
    // Only trigger onFilterChange if filters actually changed
    if (JSON.stringify(draftFilters) !== JSON.stringify(appliedFilters)) {
      setAppliedFilters(draftFilters);
      setShowLoadingMessage(true);
      onFilterChange(draftFilters);
    }
  };

  // Hide loading message when loading completes
  useEffect(() => {
    if (!isLoading && showLoadingMessage) {
      setShowLoadingMessage(false);
    }
  }, [isLoading, showLoadingMessage]);

  // Click outside to close and apply
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        isOpen &&
        menuRef.current &&
        buttonRef.current &&
        !menuRef.current.contains(event.target as Node) &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        closeAndApply();
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen, draftFilters, appliedFilters]);

  // Track scroll to hide/show with header
  useEffect(() => {
    let rafId: number | null = null;

    const onScroll = () => {
      if (rafId !== null) return;
      rafId = window.requestAnimationFrame(() => {
        rafId = null;
        const y = window.scrollY || 0;
        setIsHidden((prev) => {
          if (!prev && y >= HIDE_AT) return true;
          if (prev && y <= SHOW_AT) return false;
          return prev;
        });
      });
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (rafId !== null) window.cancelAnimationFrame(rafId);
    };
  }, []);

  // Prevent scroll propagation from menu to page
  const handleMenuWheel = useCallback((e: React.WheelEvent) => {
    const target = e.currentTarget;
    const scrollTop = target.scrollTop;
    const scrollHeight = target.scrollHeight;
    const clientHeight = target.clientHeight;
    const atTop = scrollTop === 0 && e.deltaY < 0;
    const atBottom = scrollTop + clientHeight >= scrollHeight && e.deltaY > 0;

    // Only prevent if we're at bounds and trying to scroll further
    if (atTop || atBottom) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, []);

  // Update draft filter (does not apply until menu closes)
  const updateFilter = (key: string, value: unknown) => {
    setDraftFilters(prev => ({ ...prev, [key]: value }));
  };

  const updateSliderFilter = (field: string, values: number[]) => {
    const newFilter = { min: values[0], max: values[1] };
    updateFilter(field, newFilter);
  };

  // Convert slider position (0-100) to actual pixel value
  const sliderToPixelValue = (sliderValue: number): number => {
    if (sliderValue <= 50) {
      const discreteValues = [8, 16, 32, 64, 128];
      const segmentSize = 50 / (discreteValues.length - 1);
      const index = Math.round(sliderValue / segmentSize);
      return discreteValues[Math.min(index, discreteValues.length - 1)];
    } else {
      const normalizedValue = (sliderValue - 50) / 50;
      return Math.round(128 + normalizedValue * 128);
    }
  };

  // Convert pixel value to slider position (0-100)
  const pixelToSliderValue = (pixelValue: number): number => {
    if (pixelValue <= 128) {
      const discreteValues = [8, 16, 32, 64, 128];
      const index = discreteValues.findIndex(v => v >= pixelValue);
      const actualIndex = index === -1 ? discreteValues.length - 1 : index;
      const segmentSize = 50 / (discreteValues.length - 1);
      return actualIndex * segmentSize;
    } else {
      const normalizedValue = (pixelValue - 128) / 128;
      return 50 + normalizedValue * 50;
    }
  };

  const updateDimensionFilter = (field: string, sliderValues: number[]) => {
    const minPixels = sliderToPixelValue(sliderValues[0]);
    const maxPixels = sliderToPixelValue(sliderValues[1]);
    const newFilter = { min: minPixels, max: maxPixels };
    updateFilter(field, newFilter);
  };

  // Exponential slider conversion for easier small value selection
  // p=2.0 for moderate bias, p=5.0 for strong bias (file size)

  // Convert slider position (0-100) to actual value using exponential scaling
  const sliderToExpoValue = (slider: number, min: number, max: number, power: number = 2.0): number => {
    const normalized = slider / 100; // Convert 0-100 to 0-1
    const expValue = Math.pow(normalized, power);
    return Math.round(min + (max - min) * expValue);
  };

  // Convert actual value to slider position (0-100) using exponential scaling
  const expoValueToSlider = (value: number, min: number, max: number, power: number = 2.0): number => {
    const normalized = (value - min) / (max - min);
    const sliderNorm = Math.pow(normalized, 1 / power);
    return sliderNorm * 100;
  };

  // Update handlers for exponential sliders
  const updateExpoSliderFilter = (field: string, sliderValues: number[], min: number, max: number, power: number = 2.0) => {
    const minVal = sliderToExpoValue(sliderValues[0], min, max, power);
    const maxVal = sliderToExpoValue(sliderValues[1], min, max, power);
    updateFilter(field, { min: minVal, max: maxVal });
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
    const minDate = draftFilters.creation_date?.min
      ? dateToTimestamp(new Date(draftFilters.creation_date.min))
      : minTimestamp;
    const maxDate = draftFilters.creation_date?.max
      ? dateToTimestamp(new Date(draftFilters.creation_date.max))
      : maxTimestamp;
    return [minDate, maxDate];
  };

  const toggleMultiSelect = (field: "file_format" | "kind", value: string) => {
    const current = draftFilters[field] || [];
    const newValue = current.includes(value)
      ? current.filter(v => v !== value)
      : [...current, value];
    updateFilter(field, newValue.length > 0 ? newValue : undefined);
  };

  const clearFilters = () => {
    const defaultFilters: FilterConfig = {
      sortBy: "created_at",
      sortOrder: "desc",
      file_format: ["png", "gif", "webp", "bmp"],
      kind: ["static", "animated"]
    };
    setDraftFilters(defaultFilters);
  };

  // Check if any filters are active (based on applied filters, not draft)
  const hasActiveFilters = !!(
    appliedFilters.width ||
    appliedFilters.height ||
    appliedFilters.file_bytes ||
    appliedFilters.frame_count ||
    appliedFilters.unique_colors ||
    appliedFilters.reactions ||
    appliedFilters.comments ||
    appliedFilters.creation_date ||
    (appliedFilters.has_transparency !== null && appliedFilters.has_transparency !== undefined) ||
    (appliedFilters.has_semitransparency !== null && appliedFilters.has_semitransparency !== undefined) ||
    (appliedFilters.file_format && appliedFilters.file_format.length > 0 && appliedFilters.file_format.length < 4) ||
    (appliedFilters.kind && appliedFilters.kind.length > 0 && appliedFilters.kind.length < 2) ||
    (appliedFilters.sortBy && appliedFilters.sortBy !== 'created_at') ||
    (appliedFilters.sortOrder && appliedFilters.sortOrder !== 'desc')
  );

  const sortOptions = [
    { value: "created_at", label: "Creation Date" },
    { value: "width", label: "Width" },
    { value: "height", label: "Height" },
    { value: "file_bytes", label: "File Size" },
    { value: "frame_count", label: "Frame Count" },
    { value: "unique_colors", label: "Unique Colors" },
  ];

  const orderOptions = [
    { value: "desc", label: "Descending" },
    { value: "asc", label: "Ascending" },
  ];

  return (
    <>
      <div className={`filter-container ${isHidden && !isOpen ? 'is-hidden' : ''}`}>
        {/* Round Floating Button */}
        <button
          ref={buttonRef}
          onClick={() => setIsOpen(!isOpen)}
          className={`filter-toggle ${isOpen ? 'is-open' : ''}`}
          aria-label="Toggle filters"
        >
          {isOpen ? <X size={24} /> : <Filter size={24} />}
          {hasActiveFilters && !isOpen && <span className="filter-badge" />}
        </button>

        {/* Floating Menu */}
        {isOpen && (
          <div ref={menuRef} className="filter-menu" onWheel={handleMenuWheel}>
            <div className="filter-header">
              <h3>Filter & Sort</h3>
              <div className="filter-header-actions">
                <button className="filter-clear-btn" onClick={clearFilters}>
                  Clear All
                </button>
                <button
                  onClick={closeAndApply}
                  className="filter-close-btn"
                  aria-label="Close menu"
                >
                  <X size={20} />
                </button>
              </div>
            </div>

            <ScrollArea className="filter-scroll">
              <div className="filter-content">
                {/* Sorting Section */}
                <div className="filter-section">
                  <h4 className="filter-section-title">Sort By</h4>
                  <div className="filter-select-group">
                    <Select
                      value={draftFilters.sortBy || "created_at"}
                      onValueChange={(value) => updateFilter("sortBy", value)}
                      options={sortOptions}
                      placeholder="Select field"
                    />
                    <Select
                      value={draftFilters.sortOrder || "desc"}
                      onValueChange={(value) => updateFilter("sortOrder", value as "asc" | "desc")}
                      options={orderOptions}
                      placeholder="Order"
                    />
                  </div>
                </div>

                <div className="filter-separator" />

                {/* Dimension Filters */}
                <div className="filter-section">
                  <h4 className="filter-section-title">Dimensions</h4>

                  <div className="filter-slider-group">
                    <label className="filter-label">
                      Width: {draftFilters.width?.min || 8}px - {draftFilters.width?.max || 256}px
                    </label>
                    <Slider
                      min={0}
                      max={100}
                      step={1}
                      value={[
                        pixelToSliderValue(draftFilters.width?.min || 8),
                        pixelToSliderValue(draftFilters.width?.max || 256)
                      ]}
                      onValueChange={(values) => updateDimensionFilter("width", values)}
                    />
                  </div>

                  <div className="filter-slider-group">
                    <label className="filter-label">
                      Height: {draftFilters.height?.min || 8}px - {draftFilters.height?.max || 256}px
                    </label>
                    <Slider
                      min={0}
                      max={100}
                      step={1}
                      value={[
                        pixelToSliderValue(draftFilters.height?.min || 8),
                        pixelToSliderValue(draftFilters.height?.max || 256)
                      ]}
                      onValueChange={(values) => updateDimensionFilter("height", values)}
                    />
                  </div>
                </div>

                <div className="filter-separator" />

                {/* Technical Filters */}
                <div className="filter-section">
                  <h4 className="filter-section-title">Technical</h4>

                  <div className="filter-slider-group">
                    <label className="filter-label">
                      File Size: {formatFileSize(draftFilters.file_bytes?.min || 0)} - {formatFileSize(draftFilters.file_bytes?.max || 5242880)}
                    </label>
                    <Slider
                      min={0}
                      max={100}
                      step={0.5}
                      value={[
                        expoValueToSlider(draftFilters.file_bytes?.min || 0, 0, 5242880, 4.0),
                        expoValueToSlider(draftFilters.file_bytes?.max || 5242880, 0, 5242880, 4.0)
                      ]}
                      onValueChange={(values) => updateExpoSliderFilter("file_bytes", values, 0, 5242880, 4.0)}
                    />
                  </div>

                  <div className="filter-slider-group">
                    <label className="filter-label">
                      Frame Count: {draftFilters.frame_count?.min || 1} - {draftFilters.frame_count?.max === 256 || draftFilters.frame_count?.max === undefined ? "256+" : draftFilters.frame_count.max}
                    </label>
                    <Slider
                      min={0}
                      max={100}
                      step={0.5}
                      value={[
                        expoValueToSlider(draftFilters.frame_count?.min || 1, 1, 256),
                        expoValueToSlider(draftFilters.frame_count?.max || 256, 1, 256)
                      ]}
                      onValueChange={(values) => updateExpoSliderFilter("frame_count", values, 1, 256)}
                    />
                  </div>

                  <div className="filter-slider-group">
                    <label className="filter-label">
                      Colors: {draftFilters.unique_colors?.min || 1} - {draftFilters.unique_colors?.max === 256 || draftFilters.unique_colors?.max === undefined ? "256+" : draftFilters.unique_colors.max}
                    </label>
                    <Slider
                      min={0}
                      max={100}
                      step={0.5}
                      value={[
                        expoValueToSlider(draftFilters.unique_colors?.min || 1, 1, 256),
                        expoValueToSlider(draftFilters.unique_colors?.max || 256, 1, 256)
                      ]}
                      onValueChange={(values) => updateExpoSliderFilter("unique_colors", values, 1, 256)}
                    />
                  </div>
                </div>

                <div className="filter-separator" />

                {/* Transparency & Format */}
                <div className="filter-section">
                  <h4 className="filter-section-title">Transparency</h4>
                  <div className="filter-chips">
                    <button
                      onClick={() => updateFilter("has_transparency", draftFilters.has_transparency === true ? null : true)}
                      className={`filter-chip ${draftFilters.has_transparency === true ? 'active' : ''}`}
                    >
                      Has Transparency
                    </button>
                    <button
                      onClick={() => updateFilter("has_semitransparency", draftFilters.has_semitransparency === true ? null : true)}
                      className={`filter-chip ${draftFilters.has_semitransparency === true ? 'active' : ''}`}
                    >
                      Has Alpha
                    </button>
                  </div>
                </div>

                <div className="filter-section">
                  <h4 className="filter-section-title">File Format</h4>
                  <div className="filter-chips">
                    {["png", "gif", "webp", "bmp"].map((format) => (
                      <button
                        key={format}
                        onClick={() => toggleMultiSelect("file_format", format)}
                        className={`filter-chip ${draftFilters.file_format?.includes(format) ? 'active' : ''}`}
                      >
                        {format.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="filter-section">
                  <h4 className="filter-section-title">Animation</h4>
                  <div className="filter-chips">
                    {[
                      { value: "static", label: "Static" },
                      { value: "animated", label: "Animated" }
                    ].map((item) => (
                      <button
                        key={item.value}
                        onClick={() => toggleMultiSelect("kind", item.value)}
                        className={`filter-chip ${draftFilters.kind?.includes(item.value) ? 'active' : ''}`}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="filter-separator" />

                {/* Date & Engagement */}
                <div className="filter-section">
                  <h4 className="filter-section-title">Date Range</h4>
                  <div className="filter-slider-group">
                    <label className="filter-label">
                      {formatDate(timestampToDate(getCurrentDateRange()[0]))} - {formatDate(timestampToDate(getCurrentDateRange()[1]))}
                    </label>
                    <Slider
                      min={minTimestamp}
                      max={maxTimestamp}
                      step={86400000}
                      value={getCurrentDateRange()}
                      onValueChange={(values) => updateDateFilter(values)}
                    />
                  </div>
                </div>

                <div className="filter-section">
                  <h4 className="filter-section-title">Engagement</h4>
                  <div className="filter-slider-group">
                    <label className="filter-label">
                      Reactions: {draftFilters.reactions?.min || 0} - {draftFilters.reactions?.max === 256 || draftFilters.reactions?.max === undefined ? "256+" : draftFilters.reactions.max}
                    </label>
                    <Slider
                      min={0}
                      max={256}
                      step={1}
                      value={[draftFilters.reactions?.min || 0, draftFilters.reactions?.max || 256]}
                      onValueChange={(values) => updateSliderFilter("reactions", values)}
                    />
                  </div>

                  <div className="filter-slider-group">
                    <label className="filter-label">
                      Comments: {draftFilters.comments?.min || 0} - {draftFilters.comments?.max === 256 || draftFilters.comments?.max === undefined ? "256+" : draftFilters.comments.max}
                    </label>
                    <Slider
                      min={0}
                      max={256}
                      step={1}
                      value={[draftFilters.comments?.min || 0, draftFilters.comments?.max || 256]}
                      onValueChange={(values) => updateSliderFilter("comments", values)}
                    />
                  </div>
                </div>
              </div>
            </ScrollArea>
          </div>
        )}
      </div>

      <style jsx>{`
        .filter-container {
          position: fixed;
          top: calc(var(--header-height) + 16px);
          left: 16px;
          z-index: 50;
          transition: transform 200ms ease-out, opacity 200ms ease-out;
        }

        .filter-container.is-hidden {
          transform: translateY(calc(-100% - var(--header-height) - 32px));
          opacity: 0;
          pointer-events: none;
        }

        .filter-toggle {
          width: 56px;
          height: 56px;
          border-radius: 50%;
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          border: none;
          box-shadow: var(--glow-pink);
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: all var(--transition-fast);
          position: relative;
        }

        .filter-toggle:hover {
          transform: scale(1.05);
          box-shadow: 0 0 20px rgba(255, 110, 180, 0.8);
        }

        .filter-toggle.is-open {
          background: var(--bg-tertiary);
          box-shadow: none;
        }

        .filter-badge {
          position: absolute;
          top: 8px;
          right: 8px;
          width: 10px;
          height: 10px;
          background: var(--accent-cyan);
          border-radius: 50%;
          box-shadow: var(--glow-cyan);
        }

        .filter-menu {
          position: fixed;
          top: var(--header-height);
          left: 0;
          width: 320px;
          max-width: 80vw;
          max-height: 50vh;
          background: var(--bg-secondary);
          border-right: 1px solid rgba(255, 255, 255, 0.1);
          overflow: hidden;
          overflow-y: auto;
          overscroll-behavior: contain;
          box-shadow: 4px 0 20px rgba(0, 0, 0, 0.3);
        }

        .filter-header {
          padding: 16px;
          background: var(--bg-tertiary);
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .filter-header h3 {
          color: var(--text-primary);
          font-weight: 600;
          font-size: 1rem;
          margin: 0;
        }

        .filter-header-actions {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .filter-clear-btn {
          background: transparent;
          border: 1px solid var(--accent-cyan);
          color: var(--accent-cyan);
          padding: 6px 12px;
          border-radius: 6px;
          font-size: 0.8rem;
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .filter-clear-btn:hover {
          background: var(--accent-cyan);
          color: var(--bg-primary);
        }

        .filter-close-btn {
          padding: 4px;
          color: var(--text-secondary);
          cursor: pointer;
          border-radius: 4px;
          transition: all var(--transition-fast);
        }

        .filter-close-btn:hover {
          background: var(--bg-card);
          color: var(--text-primary);
        }

        .filter-scroll {
          /* Menu max-height (50vh) minus filter-header (~60px) */
          max-height: calc(50vh - 60px);
          overscroll-behavior: contain;
        }

        .filter-content {
          padding: 16px;
        }

        .filter-section {
          margin-bottom: 20px;
        }

        .filter-section-title {
          color: var(--text-secondary);
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 12px;
        }

        .filter-separator {
          height: 1px;
          background: rgba(255, 255, 255, 0.05);
          margin: 20px 0;
        }

        .filter-select-group {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .filter-slider-group {
          margin-bottom: 16px;
        }

        .filter-label {
          color: var(--text-secondary);
          font-size: 0.85rem;
          margin-bottom: 8px;
          display: block;
        }

        .filter-chips {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }

        .filter-chip {
          padding: 8px 14px;
          border-radius: 20px;
          font-size: 0.8rem;
          border: 1px solid rgba(255, 255, 255, 0.1);
          cursor: pointer;
          transition: all var(--transition-fast);
          background: var(--bg-tertiary);
          color: var(--text-secondary);
        }

        .filter-chip:hover {
          background: var(--bg-card);
          color: var(--text-primary);
          border-color: rgba(255, 255, 255, 0.2);
        }

        .filter-chip.active {
          background: var(--accent-cyan);
          color: var(--bg-primary);
          border-color: var(--accent-cyan);
        }

        /* Mobile responsive */
        @media (max-width: 640px) {
          .filter-container {
            top: calc(var(--header-height) + 8px);
            left: 8px;
          }

          .filter-toggle {
            width: 48px;
            height: 48px;
          }

          .filter-menu {
            width: 100%;
            max-width: 80vw;
          }
        }
      `}</style>
    </>
  );
}

export type { FilterConfig };
