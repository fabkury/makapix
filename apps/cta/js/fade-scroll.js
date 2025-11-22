(function() {
  'use strict';

  // Intersection Observer for fade-in/fade-out animations
  function initFadeScroll() {
    const fadeElements = document.querySelectorAll('.fade-text');

    if (!fadeElements.length) return;

    const observerOptions = {
      root: null,
      rootMargin: '0px',
      threshold: [0, 0.2, 0.5, 0.8, 1.0]
    };

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        const element = entry.target;
        const ratio = entry.intersectionRatio;

        // Element is entering viewport (coming into view)
        if (entry.isIntersecting && ratio > 0.2) {
          element.classList.add('visible');
          element.classList.remove('fade-out');
        }
        // Element is leaving viewport (scrolling past)
        else if (!entry.isIntersecting && ratio === 0) {
          // Check if we scrolled past (element is above viewport)
          const rect = element.getBoundingClientRect();
          if (rect.bottom < 0) {
            element.classList.add('fade-out');
            element.classList.remove('visible');
          }
          // Element hasn't reached viewport yet (below)
          else {
            element.classList.remove('visible');
            element.classList.remove('fade-out');
          }
        }
        // Element is partially visible but fading out
        else if (entry.isIntersecting && ratio < 0.2) {
          element.classList.remove('visible');
        }
      });
    }, observerOptions);

    fadeElements.forEach(element => {
      observer.observe(element);
    });
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initFadeScroll);
  } else {
    initFadeScroll();
  }
})();
