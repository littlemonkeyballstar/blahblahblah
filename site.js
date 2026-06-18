/* Shared helpers for Shaykh Abdullah Faisal Archive */
const SITE_URL = 'https://shaykhabdullahfaisal.com';
const SITE_DISCLAIMER = `This is not an official website and is not affiliated with Shaykh Abdullah Faisal. This archive is maintained independently and is intended strictly for educational purposes.`;
const TELEGRAM_URL = 'https://t.me/ShaykhAbdullahFaisal';
const TELEGRAM_PDF_URL = 'https://t.me/Shaykh_faisal_pdf';
/** Paste your Cloudflare Web Analytics token from the dashboard to enable stats. */
const CLOUDFLARE_ANALYTICS_TOKEN = '';

const _lectureChunks = new Map();
const _lectureChunkLoads = new Map();
const _loadedScripts = new Set();

function registerLectureChunk(catId, items) {
  _lectureChunks.set(catId, items);
}

function getLoadedLectures() {
  return [..._lectureChunks.values()]
    .flat()
    .sort((a, b) => a.id - b.id);
}

function loadScriptOnce(src) {
  if (_loadedScripts.has(src)) {
    return _lectureChunkLoads.get(src) || Promise.resolve();
  }
  _loadedScripts.add(src);
  const promise = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(script);
  });
  _lectureChunkLoads.set(src, promise);
  return promise;
}

async function loadLectureChunk(catId) {
  if (_lectureChunks.has(catId)) return;
  const url = typeof LECTURE_CHUNK_URLS !== 'undefined' ? LECTURE_CHUNK_URLS[catId] : null;
  if (!url) return;
  await loadScriptOnce(url);
}

async function loadAllLectureChunks() {
  if (typeof LECTURE_CHUNK_URLS === 'undefined') return;
  await Promise.all(Object.keys(LECTURE_CHUNK_URLS).map(loadLectureChunk));
}

async function ensureLecturesForFilter(category, searchQuery) {
  if ((searchQuery || '').trim() || category === 'all') {
    await loadAllLectureChunks();
  } else {
    await loadLectureChunk(category);
  }
}

function initCloudflareAnalytics() {
  if (!CLOUDFLARE_ANALYTICS_TOKEN) return;
  const src = 'https://static.cloudflareinsights.com/beacon.min.js';
  if (document.querySelector(`script[data-cf-beacon][src="${src}"]`)) return;
  const script = document.createElement('script');
  script.defer = true;
  script.src = src;
  script.setAttribute('data-cf-beacon', JSON.stringify({ token: CLOUDFLARE_ANALYTICS_TOKEN }));
  document.head.appendChild(script);
}

function searchIndexHaystack(item) {
  return normalizeForSearch([item.title, item.sub || '', item.type || ''].join(' '));
}

function searchGlobalIndex(query, limit = 20) {
  if (typeof SEARCH_INDEX === 'undefined') return [];
  const words = normalizeForSearch(query).split(' ').filter(Boolean);
  if (!words.length) return [];
  const results = [];
  for (const item of SEARCH_INDEX) {
    const haystack = searchIndexHaystack(item);
    if (words.every(word => haystack.includes(word))) results.push(item);
    if (results.length >= limit) break;
  }
  return results;
}

const SEARCH_TYPE_META = {
  audio: { label: 'Audio', icon: 'fa-headphones', page: 'audio.html' },
  video: { label: 'Video', icon: 'fa-video', page: 'videos.html' },
  clip: { label: 'Clip', icon: 'fa-film', page: 'clips.html' },
};

function mountGlobalSearch({ inputId = 'globalSearch', resultsId = 'globalSearchResults' } = {}) {
  const input = document.getElementById(inputId);
  const results = document.getElementById(resultsId);
  if (!input || !results || typeof SEARCH_INDEX === 'undefined') return;

  let debounceTimer = null;

  const hideResults = () => {
    results.classList.add('hidden');
    results.innerHTML = '';
  };

  const renderResults = (items) => {
    if (!items.length) {
      results.innerHTML = '<p class="px-4 py-3 text-sm text-slate-500">No results found.</p>';
      results.classList.remove('hidden');
      return;
    }
    results.innerHTML = items.map(item => {
      const meta = SEARCH_TYPE_META[item.type] || SEARCH_TYPE_META.audio;
      return `
        <a href="${item.href}" class="global-search-result flex items-center gap-3 px-4 py-3 hover:bg-slate-800/80 transition border-b border-slate-800/80 last:border-0">
          <span class="w-9 h-9 rounded-lg bg-gold/10 border border-gold/20 flex items-center justify-center flex-shrink-0">
            <i class="fas ${meta.icon} text-gold text-sm"></i>
          </span>
          <span class="min-w-0 flex-1">
            <span class="block text-sm text-slate-100 leading-snug line-clamp-2">${escapeHtml(item.title)}</span>
            <span class="block text-xs text-slate-500 mt-0.5">${escapeHtml(meta.label)}${item.sub ? ` · ${escapeHtml(item.sub)}` : ''}</span>
          </span>
          <i class="fas fa-arrow-right text-gold/40 text-xs flex-shrink-0"></i>
        </a>`;
    }).join('');
    results.classList.remove('hidden');
  };

  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const query = input.value.trim();
      if (!query) {
        hideResults();
        return;
      }
      renderResults(searchGlobalIndex(query));
    }, 180);
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      input.blur();
      hideResults();
    }
  });

  document.addEventListener('click', (e) => {
    if (!results.contains(e.target) && e.target !== input) hideResults();
  });
}

function mountMobileStyles() {
  if (document.getElementById('mobile-styles')) return;
  const style = document.createElement('style');
  style.id = 'mobile-styles';
  style.textContent = `
    html { -webkit-text-size-adjust: 100%; }
    body {
      padding-left: env(safe-area-inset-left);
      padding-right: env(safe-area-inset-right);
    }
    a, button { -webkit-tap-highlight-color: transparent; }

    @media (max-width: 639px) {
      input[type="search"], input[type="text"], select {
        font-size: 16px !important;
      }
      .site-header__inner { padding-top: 0.75rem; padding-bottom: 0.75rem; }
      .site-header__title { font-size: 1.25rem !important; line-height: 1.3; }
      .site-nav {
        display: flex;
        flex-wrap: nowrap;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: none;
        gap: 0.375rem;
        width: 100%;
        padding: 0.125rem 0 0.375rem;
        mask-image: linear-gradient(90deg, transparent, #000 0.5rem, #000 calc(100% - 0.5rem), transparent);
      }
      .site-nav::-webkit-scrollbar { display: none; }
      .site-nav a {
        flex-shrink: 0;
        white-space: nowrap;
        min-height: 2.75rem;
        padding: 0.5rem 0.875rem !important;
        font-size: 0.8125rem !important;
      }
      .nav-long { display: none; }
      .nav-short { display: inline; }

      .mobile-section-title { font-size: 1.25rem !important; }
      .mobile-preview-card {
        padding: 0.875rem !important;
        gap: 0.875rem !important;
        min-height: 4.25rem;
      }
      .mobile-preview-card .preview-thumb {
        width: 5.5rem !important;
        height: 3.25rem !important;
      }
      .mobile-preview-card .preview-title {
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        white-space: normal;
        line-height: 1.35;
      }

      #slideshow .slide-slide-content { padding: 1rem 1rem 1.25rem !important; }
      #slideshow .slide-slide-title { font-size: 1.125rem !important; line-height: 1.35; }
      #slideshow #prevBtn, #slideshow #nextBtn {
        width: 2.5rem; height: 2.5rem; font-size: 0.875rem;
        top: 8.5rem; background: rgba(212, 168, 83, 0.95);
      }
      .audio-category-panel {
        position: sticky;
        top: 4.25rem;
        z-index: 40;
        background: rgba(12, 18, 32, 0.96) !important;
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
      }
      .audio-cat-nav {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch;
        gap: 0.5rem !important;
        max-height: none !important;
        padding: 0.125rem 0.25rem 0.5rem;
        scroll-snap-type: x proximity;
        scrollbar-width: none;
      }
      .audio-cat-nav::-webkit-scrollbar { display: none; }
      .audio-cat-nav .cat-btn {
        width: auto !important;
        flex-shrink: 0;
        white-space: nowrap;
        min-height: 2.75rem;
        padding: 0.625rem 0.875rem !important;
        scroll-snap-align: center;
      }
      .cat-picker-btn.active {
        background: rgba(212, 168, 83, 0.15);
        color: #d4a853;
        border-color: rgba(212, 168, 83, 0.4);
      }

      #subcategoryChips {
        flex-wrap: nowrap !important;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        padding-bottom: 0.25rem;
        scrollbar-width: none;
      }
      #subcategoryChips::-webkit-scrollbar { display: none; }
      #subcategoryChips .sub-btn {
        flex-shrink: 0;
        min-height: 2.5rem;
        padding: 0.5rem 0.875rem !important;
      }

      #pagination button {
        min-width: 2.75rem;
        min-height: 2.75rem;
        display: inline-flex;
        align-items: center;
        justify-content: center;
      }
      .media-card { border-radius: 1rem; }
      .media-card h3 { font-size: 0.9375rem; line-height: 1.45; }
      .media-card video { min-height: 12rem; }

      .mobile-cta-btn {
        width: 100%;
        justify-content: center;
        padding: 1rem 1.5rem !important;
      }
      .footer-links { line-height: 1.8; }
    }

    @media (min-width: 640px) {
      .nav-long { display: inline; }
      .nav-short { display: none; }
    }

    @media (min-width: 1024px) {
      .audio-cat-nav {
        display: block !important;
        overflow-x: hidden !important;
        overflow-y: auto !important;
      }
      .audio-cat-nav .cat-btn { width: 100% !important; }
      #subcategoryChips {
        flex-wrap: wrap !important;
        overflow-x: visible !important;
      }
    }

    @media (hover: none) {
      .card-hover:hover, .lecture-card:hover, .media-card:hover {
        transform: none !important;
      }
    }

    .global-search-panel {
      box-shadow: 0 16px 40px rgba(0, 0, 0, 0.45);
    }
    .global-search-result:active {
      background: rgba(30, 41, 59, 0.9);
    }
  `;
  document.head.appendChild(style);
}

function mountTopBar() {
  initCloudflareAnalytics();
  mountMobileStyles();
  if (!document.getElementById('top-bar-styles')) {
    const style = document.createElement('style');
    style.id = 'top-bar-styles';
    style.textContent = `
      .site-top-bar {
        background: linear-gradient(135deg, #0a1628 0%, #131b2a 50%, #0d1612 100%);
        border-bottom: 1px solid rgba(180, 130, 50, 0.12);
      }
      .site-top-bar__inner {
        max-width: 80rem;
        margin: 0 auto;
        padding: 0.625rem 1rem;
        text-align: center;
      }
      @media (min-width: 640px) {
        .site-top-bar__inner { padding: 0.5rem 2rem; }
      }
      .site-top-bar__grid {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
      }
      @media (min-width: 768px) {
        .site-top-bar__grid {
          flex-direction: row;
          gap: 1.25rem;
        }
      }
      .site-top-bar__block { line-height: 1.35; }
      .site-top-bar__ar {
        color: rgba(252, 211, 140, 0.92);
        font-size: 0.8125rem;
        font-weight: 500;
        letter-spacing: 0.02em;
      }
      .site-top-bar__en {
        color: rgba(148, 163, 184, 0.85);
        font-size: 0.6875rem;
        letter-spacing: 0.05em;
        margin-top: 0.1rem;
      }
      .site-top-bar__block:first-child .site-top-bar__en {
        text-transform: uppercase;
      }
      .site-top-bar__block--dua .site-top-bar__en {
        font-style: italic;
        letter-spacing: 0.01em;
        font-size: 0.7rem;
      }
      .site-top-bar__divider {
        color: rgba(212, 168, 83, 0.35);
        font-size: 0.75rem;
        line-height: 1;
        user-select: none;
      }
      @media (min-width: 768px) {
        .site-top-bar__divider {
          width: 1px;
          height: 2rem;
          background: linear-gradient(180deg, transparent, rgba(212,168,83,0.25), transparent);
          font-size: 0;
        }
      }
    `;
    document.head.appendChild(style);
  }

  const el = document.getElementById('siteTopBar');
  if (!el) return;
  el.className = 'site-top-bar';
  el.innerHTML = `
    <div class="site-top-bar__inner">
      <div class="site-top-bar__grid">
        <div class="site-top-bar__block">
          <p class="site-top-bar__ar" dir="rtl" lang="ar">الموقع الأرشيفي</p>
          <p class="site-top-bar__en">Educational Archive</p>
        </div>
        <div class="site-top-bar__divider" aria-hidden="true">·</div>
        <div class="site-top-bar__block site-top-bar__block--dua">
          <p class="site-top-bar__ar" dir="rtl" lang="ar">اللهم حرر شيخنا الحبيب</p>
          <p class="site-top-bar__en">May Allah free our beloved Shaykh</p>
        </div>
      </div>
    </div>`;
}

function mountTelegramLink(id = 'siteTelegram') {
  const el = document.getElementById(id);
  if (!el) return;
  const linkClass = 'inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-slate-700 text-slate-300 hover:border-gold/40 hover:text-gold transition text-sm';
  el.innerHTML = `
    <div class="flex flex-col sm:flex-row items-center justify-center gap-3 flex-wrap">
      <a href="${TELEGRAM_URL}" class="${linkClass}" target="_blank" rel="noopener">
        <i class="fa-brands fa-telegram text-lg"></i> @ShaykhAbdullahFaisal
      </a>
      <a href="${TELEGRAM_PDF_URL}" class="${linkClass}" target="_blank" rel="noopener">
        <i class="fa-brands fa-telegram text-lg"></i> PDFs — @Shaykh_faisal_pdf
      </a>
    </div>`;
}

function archiveStreamUrl(base, path) {
  return base + encodeURI(path).replace(/%2F/g, '/');
}

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

/** Lowercase + fold accents/apostrophes for reliable client-side search. */
function normalizeForSearch(text) {
  return (text || '')
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[''`´]/g, "'")
    .replace(/[^a-z0-9\s]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function lectureSearchHaystack(lecture) {
  return normalizeForSearch([
    lecture.title,
    lecture.categoryLabel,
    lecture.subcategoryLabel || '',
    lecture.category || '',
  ].join(' '));
}

function matchesLectureSearch(lecture, rawQuery) {
  const words = normalizeForSearch(rawQuery).split(' ').filter(Boolean);
  if (!words.length) return true;
  const haystack = lectureSearchHaystack(lecture);
  return words.every(word => haystack.includes(word));
}

function isValidThumb(src) {
  return src && !src.includes('__ia_thumb');
}

/** True when thumbnail lives in Website/thumb/ root (featured slideshow pool). */
function isFlatThumb(src) {
  if (!isValidThumb(src) || !src.startsWith('thumb/')) return false;
  const sub = src.slice('thumb/'.length);
  if (!sub.length || sub.includes('/')) return false;
  return !/_thumb\.(jpe?g|png|webp)$/i.test(sub);
}

/** Fisher–Yates shuffle — new random order every page load */
function shuffleArray(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function randomPick(arr, count) {
  return shuffleArray(arr).slice(0, Math.min(count, arr.length));
}

function thumbMarkup(src, alt, className = 'max-w-full max-h-full object-contain') {
  if (!isValidThumb(src)) {
    return `<div class="thumb-box w-full h-full flex items-center justify-center ${className}"><i class="fas fa-book-quran text-3xl text-gold/25"></i></div>`;
  }
  return `<img src="${thumbSrc(src)}" alt="${escapeHtml(alt)}" class="${className}" loading="lazy" onerror="this.outerHTML='<div class=\\'thumb-box w-full h-full flex items-center justify-center\\'><i class=\\'fas fa-book-quran text-3xl text-gold/25\\'></i></div>'">`;
}

function thumbSrc(src) {
  if (!isValidThumb(src)) return '';
  if (src.startsWith('http://') || src.startsWith('https://')) return src;
  return src.split('/').map((part, i) => (i === 0 ? part : encodeURIComponent(part))).join('/');
}

function mediaCard({ id, thumb, title, badge, stream, posterOnly = false, hideThumbImage = false }) {
  const encThumb = thumbSrc(thumb);
  const poster = encThumb ? `poster="${encThumb}"` : '';
  const imgBlock = encThumb
    ? `<img src="${encThumb}" alt="" class="relative z-[1] max-w-full max-h-full object-contain" loading="lazy" onerror="this.style.display='none'">`
    : `<i class="fas fa-play-circle text-4xl text-gold/25"></i>`;
  const badgeHtml = badge ? `<span class="absolute top-2 left-2 z-10 px-2 py-0.5 rounded-md bg-slate-950/85 text-gold text-[10px] font-semibold uppercase tracking-wider">${escapeHtml(badge)}</span>` : '';
  const videoBlock = posterOnly ? '' : `
    <video controls preload="none" playsinline class="w-full rounded-lg bg-black ${hideThumbImage ? 'aspect-video' : 'mt-auto'}" ${poster}>
      <source src="${stream}" type="video/mp4">
    </video>`;

  const thumbSection = hideThumbImage ? '' : `
      <div class="media-thumb relative flex items-center justify-center p-3 overflow-hidden">
        <div class="absolute inset-0 thumb-box"></div>
        ${imgBlock}
        ${badgeHtml}
      </div>`;

  return `
    <article id="${id || ''}" class="media-card bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden flex flex-col hover:border-gold/30 transition-all hover:-translate-y-0.5 sm:hover:-translate-y-0.5">
      ${thumbSection}
      <div class="p-4 sm:p-4 flex flex-col flex-1 min-w-0">
        <h3 class="font-medium text-sm sm:text-sm text-slate-100 leading-snug ${hideThumbImage ? 'mb-3 sm:mb-4' : 'mb-3'} line-clamp-4 sm:line-clamp-3" title="${escapeHtml(title)}">${escapeHtml(title)}</h3>
        ${videoBlock}
      </div>
    </article>`;
}

function setActiveNav(page) {
  document.querySelectorAll('[data-nav]').forEach(link => {
    const active = link.dataset.nav === page;
    link.classList.toggle('bg-gold', active);
    link.classList.toggle('text-slate-950', active);
    link.classList.toggle('font-semibold', active);
    link.classList.toggle('shadow-sm', active);
    link.classList.toggle('shadow-gold/20', active);
    link.classList.toggle('text-slate-300', !active);
    link.classList.toggle('hover:bg-gold/15', !active);
    link.classList.toggle('hover:text-gold', !active);
  });
}