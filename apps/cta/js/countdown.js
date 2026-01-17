(function() {
  'use strict';

  // Target: January 18, 2026 at 5:00 PM Eastern Time
  // Using America/New_York timezone for proper DST handling
  const TARGET_DATE = new Date('2026-01-18T17:00:00-05:00');

  const elements = {
    days: document.getElementById('countdown-days'),
    hours: document.getElementById('countdown-hours'),
    minutes: document.getElementById('countdown-minutes'),
    seconds: document.getElementById('countdown-seconds')
  };

  function padZero(num) {
    return String(num).padStart(2, '0');
  }

  function updateCountdown() {
    const now = new Date();
    const diff = TARGET_DATE - now;

    if (diff <= 0) {
      // Countdown complete
      elements.days.textContent = '00';
      elements.hours.textContent = '00';
      elements.minutes.textContent = '00';
      elements.seconds.textContent = '00';
      return;
    }

    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((diff % (1000 * 60)) / 1000);

    elements.days.textContent = padZero(days);
    elements.hours.textContent = padZero(hours);
    elements.minutes.textContent = padZero(minutes);
    elements.seconds.textContent = padZero(seconds);
  }

  // Initial update
  updateCountdown();

  // Update every second
  setInterval(updateCountdown, 1000);
})();
