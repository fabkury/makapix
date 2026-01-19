import { useState, useRef, useEffect } from "react";
import { Filter, X } from "lucide-react";
import { Slider } from "./ui/Slider";
import { Select } from "./ui/Select";
import { FilterConfig } from "../hooks/useFilters";

// Same thresholds as Layout.tsx header hide/show
const HIDE_AT = 128 * 2; // ~2 rows
const SHOW_AT = 64; // hysteresis to avoid flicker near the top

// Badge values for base and size
const BADGE_VALUES = [8, 16, 32, 64, 128] as const;
const MAX_SIZE_SELECTIONS = 3;

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
    kind: ["static", "animated"],
    sortBy: "created_at",
    sortOrder: "desc",
    ...initialFilters
  });
  // Draft filters (what the user is editing in the menu)
  const [draftFilters, setDraftFilters] = useState<FilterConfig>({
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
      const target = event.target as HTMLElement;

      // Check if click is inside Radix UI portal content (Select dropdown, etc.)
      // Radix portals have data-radix-* attributes on their content
      const isRadixPortalContent = target.closest('[data-radix-select-content]') ||
        target.closest('[data-radix-popper-content-wrapper]') ||
        target.closest('.select-content');

      if (
        isOpen &&
        menuRef.current &&
        buttonRef.current &&
        !menuRef.current.contains(target) &&
        !buttonRef.current.contains(target) &&
        !isRadixPortalContent
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


  // Update draft filter (does not apply until menu closes)
  const updateFilter = (key: string, value: unknown) => {
    setDraftFilters(prev => ({ ...prev, [key]: value }));
  };

  // Exponential slider conversion for file size
  const sliderToExpoValue = (slider: number, min: number, max: number, power: number = 2.0): number => {
    const normalized = slider / 100;
    const expValue = Math.pow(normalized, power);
    return Math.round(min + (max - min) * expValue);
  };

  const expoValueToSlider = (value: number, min: number, max: number, power: number = 2.0): number => {
    const normalized = (value - min) / (max - min);
    const sliderNorm = Math.pow(normalized, 1 / power);
    return sliderNorm * 100;
  };

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

  // Base badge selection (single select)
  const toggleBaseBadge = (value: number) => {
    if (draftFilters.base === value) {
      // Deselect if already selected
      updateFilter("base", undefined);
    } else {
      updateFilter("base", value);
    }
  };

  // Size badge selection (multi-select, max 3)
  const toggleSizeBadge = (value: number) => {
    const current = draftFilters.size || [];
    if (current.includes(value)) {
      // Remove from selection
      const newValue = current.filter(v => v !== value);
      updateFilter("size", newValue.length > 0 ? newValue : undefined);
    } else if (current.length < MAX_SIZE_SELECTIONS) {
      // Add to selection (if under max)
      updateFilter("size", [...current, value]);
    }
    // If at max, clicking another badge does nothing
  };

  // Animation kind selection (simplified single-select style)
  const toggleKind = (value: string) => {
    const current = draftFilters.kind || ["static", "animated"];
    if (current.includes(value)) {
      // If both are selected and we click one, show only the other
      // If only one is selected and we click it, show both
      if (current.length === 2) {
        updateFilter("kind", [value === "static" ? "animated" : "static"]);
      } else {
        updateFilter("kind", ["static", "animated"]);
      }
    } else {
      // Add back the deselected one
      updateFilter("kind", [...current, value]);
    }
  };

  const clearFilters = () => {
    const defaultFilters: FilterConfig = {
      sortBy: "created_at",
      sortOrder: "desc",
      kind: ["static", "animated"]
    };
    setDraftFilters(defaultFilters);
  };

  // Check if any filters are active (based on applied filters, not draft)
  const hasActiveFilters = !!(
    appliedFilters.base !== undefined ||
    (appliedFilters.size && appliedFilters.size.length > 0) ||
    appliedFilters.file_bytes ||
    (appliedFilters.kind && appliedFilters.kind.length > 0 && appliedFilters.kind.length < 2) ||
    (appliedFilters.sortBy && appliedFilters.sortBy !== 'created_at') ||
    (appliedFilters.sortOrder && appliedFilters.sortOrder !== 'desc')
  );

  // Simplified sort options
  const sortOptions = [
    { value: "created_at", label: "Creation Date" },
    { value: "reactions", label: "Reactions" },
    { value: "file_bytes", label: "File Size" },
  ];

  const orderOptions = [
    { value: "desc", label: "Descending" },
    { value: "asc", label: "Ascending" },
  ];

  // Get badge label
  const getBadgeLabel = (value: number) => {
    return value >= 128 ? "128+" : String(value);
  };

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
          <div ref={menuRef} className="filter-menu">
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

            <div className="filter-scroll">
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

                {/* Base Dimension (single-select badges) */}
                <div className="filter-section">
                  <h4 className="filter-section-title">Base (min dimension)</h4>
                  <div className="filter-badges">
                    {BADGE_VALUES.map((value) => (
                      <button
                        key={`base-${value}`}
                        onClick={() => toggleBaseBadge(value)}
                        className={`filter-badge-btn ${draftFilters.base === value ? 'active' : ''}`}
                      >
                        {getBadgeLabel(value)}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Size Dimension (multi-select badges, max 3) */}
                <div className="filter-section">
                  <h4 className="filter-section-title">
                    Size (max dimension)
                    <span className="filter-hint">
                      {draftFilters.size?.length || 0}/{MAX_SIZE_SELECTIONS}
                    </span>
                  </h4>
                  <div className="filter-badges">
                    {BADGE_VALUES.map((value) => {
                      const isSelected = draftFilters.size?.includes(value);
                      const atMax = (draftFilters.size?.length || 0) >= MAX_SIZE_SELECTIONS;
                      return (
                        <button
                          key={`size-${value}`}
                          onClick={() => toggleSizeBadge(value)}
                          className={`filter-badge-btn ${isSelected ? 'active' : ''} ${atMax && !isSelected ? 'disabled' : ''}`}
                          disabled={atMax && !isSelected}
                        >
                          {getBadgeLabel(value)}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="filter-separator" />

                {/* File Size Slider */}
                <div className="filter-section">
                  <h4 className="filter-section-title">File Size</h4>
                  <div className="filter-slider-group">
                    <label className="filter-label">
                      {formatFileSize(draftFilters.file_bytes?.min || 0)} - {formatFileSize(draftFilters.file_bytes?.max || 5242880)}
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
                </div>

                <div className="filter-separator" />

                {/* Animation Type (simplified single-select style) */}
                <div className="filter-section">
                  <h4 className="filter-section-title">Animation</h4>
                  <div className="filter-badges">
                    <button
                      onClick={() => toggleKind("static")}
                      className={`filter-badge-btn ${!draftFilters.kind?.includes("animated") ? 'active' : draftFilters.kind?.includes("static") ? 'semi-active' : ''}`}
                    >
                      Static
                    </button>
                    <button
                      onClick={() => toggleKind("animated")}
                      className={`filter-badge-btn ${!draftFilters.kind?.includes("static") ? 'active' : draftFilters.kind?.includes("animated") ? 'semi-active' : ''}`}
                    >
                      Animated
                    </button>
                  </div>
                </div>
              </div>
            </div>
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
          box-shadow: 4px 0 20px rgba(0, 0, 0, 0.3);
          display: flex;
          flex-direction: column;
        }

        .filter-header {
          padding: 16px;
          background: var(--bg-tertiary);
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex-shrink: 0;
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
          flex: 1;
          overflow-y: auto;
          overflow-x: hidden;
          overscroll-behavior: contain;
          -webkit-overflow-scrolling: touch;
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
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .filter-hint {
          font-size: 0.7rem;
          color: var(--text-muted);
          font-weight: 400;
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

        .filter-badges {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }

        .filter-badge-btn {
          padding: 8px 16px;
          border-radius: 20px;
          font-size: 0.85rem;
          font-weight: 500;
          border: 1px solid rgba(255, 255, 255, 0.15);
          cursor: pointer;
          transition: all var(--transition-fast);
          background: var(--bg-tertiary);
          color: var(--text-secondary);
        }

        .filter-badge-btn:hover:not(.disabled) {
          background: var(--bg-card);
          color: var(--text-primary);
          border-color: rgba(255, 255, 255, 0.25);
        }

        .filter-badge-btn.active {
          background: var(--accent-cyan);
          color: var(--bg-primary);
          border-color: var(--accent-cyan);
        }

        .filter-badge-btn.semi-active {
          background: rgba(0, 255, 255, 0.15);
          color: var(--accent-cyan);
          border-color: var(--accent-cyan);
        }

        .filter-badge-btn.disabled {
          opacity: 0.4;
          cursor: not-allowed;
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
