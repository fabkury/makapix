(function() {
  'use strict';

  function applyScale() {
    const maxContent = Math.min(window.innerWidth * 0.9, 680); // px

    document.querySelectorAll('.pixel').forEach(img => {
      const base = parseInt(img.dataset.base, 10);
      if (!base) return;

      // Design caps to keep layout elegant
      const maxScaleByDesign = base === 16 ? 16 : base === 32 ? 10 : base === 64 ? 6 : 4;

      // Calculate the largest integer scale that fits
      const scale = Math.max(1, Math.min(Math.floor(maxContent / base), maxScaleByDesign));

      // Enforce intrinsic box + transform scale for crisp pixels
      img.style.width = base + 'px';
      img.style.height = base + 'px';
      img.style.transformOrigin = 'top left';
      img.style.transform = 'scale(' + scale + ')';

      // Ensure outer wrap reserves space to prevent layout shift
      const wrap = img.closest('.pixel-wrap');
      if (wrap) {
        wrap.style.width = (base * scale) + 'px';
        wrap.style.height = (base * scale) + 'px';
      }
    });
  }

  window.addEventListener('resize', applyScale, { passive: true });
  window.addEventListener('DOMContentLoaded', applyScale);

  // Call immediately in case DOM is already loaded
  if (document.readyState === 'loading') {
    // Still loading, wait for DOMContentLoaded
  } else {
    // DOM already loaded, apply immediately
    applyScale();
  }
})();
