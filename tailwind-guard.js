/* Safe Tailwind CDN bootstrap — avoids ReferenceError when Brave Shields blocks cdn.tailwindcss.com */
(function () {
  const THEME = {
    theme: {
      extend: {
        colors: {
          gold: { DEFAULT: '#d4a853', light: '#e8c97a', dark: '#b8923f' },
          slate: { 850: '#1a2332', 925: '#0c1220', 950: '#080d18' }
        },
        fontFamily: {
          display: ['"Playfair Display"', 'Georgia', 'serif'],
          body: ['Inter', 'system-ui', 'sans-serif']
        }
      }
    }
  };

  function markNoTailwind() {
    document.documentElement.classList.add('no-tailwind');
  }

  if (typeof tailwind !== 'undefined') {
    tailwind.config = THEME;
  } else {
    markNoTailwind();
  }

  setTimeout(function () {
    if (typeof tailwind === 'undefined') markNoTailwind();
  }, 1200);
})();