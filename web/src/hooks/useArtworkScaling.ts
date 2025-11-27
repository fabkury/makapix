import { useEffect, RefObject } from 'react';

/**
 * Hook to scale artworks to integer multiples of their native size
 * Reference size depends on Device Pixel Ratio:
 * - DPR < 2: 256px reference size
 * - DPR >= 2: 128px reference size
 * Each artwork scales to the largest integer multiple that fits within the card's available space
 * Grid is kept together with extra space only on the sides
 */
export function useArtworkScaling(gridRef: RefObject<HTMLDivElement>) {
  useEffect(() => {
    const grid = gridRef.current;
    if (!grid) return;

    const calculateScales = () => {
      const gridStyles = window.getComputedStyle(grid);
      const gridGap = parseFloat(gridStyles.gap) || 4;
      const gridWidth = grid.clientWidth;
      
      if (gridWidth === 0) return;
      
      // Determine reference size based on DPR
      // DPR < 2: 256px, DPR >= 2: 128px
      const dpr = window.devicePixelRatio || 1;
      const baseReferenceSize = dpr >= 2 ? 128 : 256;
      
      // Get the actual computed grid-template-columns value
      // The browser expands repeat() to individual values, so we count them
      const templateColumns = gridStyles.gridTemplateColumns;
      
      // Parse column count from computed value
      // Computed value will be like "256px 256px" (2 cols) or "256px 256px 256px" (3 cols)
      // Split by space and filter out empty strings
      const columns = templateColumns.split(' ').filter(col => col.trim().length > 0 && col.includes('px'));
      let columnCount = columns.length;
      
      // Fallback: if we can't parse, try to detect from window width
      if (columnCount === 0 || columnCount < 2) {
        if (gridWidth >= 1024) {
          columnCount = 4;
        } else if (gridWidth >= 768) {
          columnCount = 3;
        } else {
          columnCount = 2;
        }
      }
      
      // Calculate if we can fit double-size cards in this row
      // Need: (doubleSize * columnCount) + (gap * (columnCount - 1)) <= gridWidth
      const doubleSize = baseReferenceSize * 2;
      const requiredWidthForDouble = (doubleSize * columnCount) + (gridGap * (columnCount - 1));
      const useDoubleSizeCards = requiredWidthForDouble <= gridWidth;
      
      // Determine card size for this row
      const cardSize = useDoubleSizeCards ? doubleSize : baseReferenceSize;
      const availableSize = cardSize; // Inner space equals card size (no padding)
      
      // Update CSS custom property to control card size
      // CSS media queries will handle the column count
      grid.style.setProperty('--artwork-card-size', `${cardSize}px`);
      
      // Process each artwork card
      const artworkCards = grid.querySelectorAll('.artwork-card');
      artworkCards.forEach((card) => {
        const cardElement = card as HTMLElement;
        const imageContainer = card.querySelector('.artwork-image-container') as HTMLElement;
        const image = card.querySelector('.artwork-image') as HTMLImageElement;
        
        if (!imageContainer || !image) return;
        
        // Set card size (all cards in row get same size)
        cardElement.style.width = `${cardSize}px`;
        cardElement.style.height = `${cardSize}px`;
        
        // Get canvas dimensions from data attribute
        const canvasStr = image.getAttribute('data-canvas') || '';
        if (!canvasStr) return;
        
        // Parse canvas string (e.g., "64x64", "128x128", "256x256")
        const [widthStr, heightStr] = canvasStr.split('x');
        const nativeWidth = parseInt(widthStr, 10);
        const nativeHeight = parseInt(heightStr, 10);
        
        if (!nativeWidth || !nativeHeight || isNaN(nativeWidth) || isNaN(nativeHeight)) return;
        
        // Use the larger dimension to ensure it fits (for square artworks)
        const nativeSize = Math.max(nativeWidth, nativeHeight);
        
        // Calculate maximum integer scale that fits in available space
        const scale = Math.floor(availableSize / nativeSize);
        
        // Ensure minimum scale of 1 (native size)
        const finalScale = Math.max(1, scale);
        
        // Calculate display size at integer multiple
        const displayWidth = nativeWidth * finalScale;
        const displayHeight = nativeHeight * finalScale;
        
        // Apply size to image
        image.style.width = `${displayWidth}px`;
        image.style.height = `${displayHeight}px`;
        image.style.maxWidth = 'none';
        image.style.maxHeight = 'none';
        image.style.objectFit = 'contain';
      });
    };

    // Calculate on mount with a small delay to ensure DOM is ready
    const timeoutId = setTimeout(() => {
      calculateScales();
    }, 0);

    // Recalculate on window resize (which triggers media query changes)
    const resizeObserver = new ResizeObserver(() => {
      // Small delay to let CSS media queries apply first
      setTimeout(() => {
        calculateScales();
      }, 0);
    });

    resizeObserver.observe(grid);

    // Also listen to window resize as fallback
    const handleResize = () => {
      setTimeout(() => {
        calculateScales();
      }, 0);
    };
    
    window.addEventListener('resize', handleResize);

    return () => {
      clearTimeout(timeoutId);
      resizeObserver.disconnect();
      window.removeEventListener('resize', handleResize);
    };
  }, [gridRef]);
}
