(function() {
  'use strict';

  const track = document.getElementById('carousel-track');
  if (!track) return;

  // Check for reduced motion preference
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Duplicate images for seamless infinite loop
  const originalImages = track.innerHTML;
  track.innerHTML = originalImages + originalImages;

  // Calculate animation duration based on content width
  // Each image is 256px + 24px gap = 280px, 16 images = 4480px
  // Speed ~50px/s means 4480px / 50 = ~90 seconds for one set
  const imageCount = 16;
  const imageWidth = 256;
  const gap = 24;
  const totalWidth = imageCount * (imageWidth + gap);
  const speed = 50; // pixels per second
  const duration = totalWidth / speed;

  // Set CSS custom property for animation duration
  track.style.setProperty('--carousel-duration', duration + 's');

  // Only animate if user hasn't requested reduced motion
  if (!prefersReducedMotion) {
    track.classList.add('animate');
  }

  // Pause on hover for accessibility
  track.addEventListener('mouseenter', function() {
    track.style.animationPlayState = 'paused';
  });

  track.addEventListener('mouseleave', function() {
    track.style.animationPlayState = 'running';
  });

  // Listen for changes in motion preference
  window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', function(e) {
    if (e.matches) {
      track.classList.remove('animate');
    } else {
      track.classList.add('animate');
    }
  });
})();
