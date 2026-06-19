/* Shared helpers for Shaykh Abdullah Faisal Archive */
const SITE_URL = 'https://shaykhabdullahfaisal.com';
const SITE_DISCLAIMER = `This is not an official website and is not affiliated with Shaykh Abdullah Faisal. This archive is maintained independently and is intended strictly for educational purposes.`;
const TELEGRAM_URL = 'https://t.me/ShaykhAbdullahFaisal';
const TELEGRAM_PDF_URL = 'https://t.me/Shaykh_faisal_pdf';
/** Paste your Cloudflare Web Analytics token from the dashboard to enable stats. */
const CLOUDFLARE_ANALYTICS_TOKEN = 'c26870c8f6414600ac3e8e0df17d47bb';

const AUDIO_PROGRESS_KEY = 'shaf-audio-progress';
const AUDIO_PROGRESS_MIN_SAVE_SEC = 3;
const AUDIO_PROGRESS_END_MARGIN_SEC = 15;

function readAudioProgressStore() {
  try {
    const raw = localStorage.getItem(AUDIO_PROGRESS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function writeAudioProgressStore(store) {
  try {
    localStorage.setItem(AUDIO_PROGRESS_KEY, JSON.stringify(store));
  } catch {}
}

function lectureIdFromAudio(audio) {
  const fromData = audio.dataset.lectureId;
  if (fromData) return parseInt(fromData, 10);
  const card = audio.closest('[id^="lecture-"]');
  if (!card) return null;
  const match = card.id.match(/^lecture-(\d+)$/);
  return match ? parseInt(match[1], 10) : null;
}

function parseAudioProgressEntry(value) {
  if (typeof value === 'number' && value > 0) {
    return { seconds: value, at: 0 };
  }
  if (value && typeof value === 'object' && typeof value.t === 'number' && value.t > 0) {
    return { seconds: value.t, at: typeof value.at === 'number' ? value.at : 0 };
  }
  return null;
}

function saveAudioProgress(lectureId, currentTime, duration) {
  if (!Number.isFinite(lectureId) || !Number.isFinite(currentTime)) return;
  const store = readAudioProgressStore();
  const key = String(lectureId);
  if (duration && currentTime >= duration - AUDIO_PROGRESS_END_MARGIN_SEC) {
    delete store[key];
  } else if (currentTime < AUDIO_PROGRESS_MIN_SAVE_SEC) {
    delete store[key];
  } else {
    store[key] = {
      t: Math.round(currentTime * 10) / 10,
      at: Date.now(),
    };
  }
  writeAudioProgressStore(store);
}

function loadAudioProgress(lectureId) {
  const parsed = parseAudioProgressEntry(readAudioProgressStore()[String(lectureId)]);
  return parsed ? parsed.seconds : 0;
}

function getContinueListeningEntries(limit = 3) {
  const store = readAudioProgressStore();
  return Object.entries(store)
    .map(([id, value]) => {
      const parsed = parseAudioProgressEntry(value);
      if (!parsed) return null;
      const lectureId = parseInt(id, 10);
      if (!Number.isFinite(lectureId)) return null;
      return { id: lectureId, seconds: parsed.seconds, at: parsed.at };
    })
    .filter(Boolean)
    .sort((a, b) => b.at - a.at)
    .slice(0, limit);
}

function formatAudioTimestamp(seconds) {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }
  return `${m}:${String(s).padStart(2, '0')}`;
}

function tryRestoreAudioProgress(audio, lectureId) {
  const saved = loadAudioProgress(lectureId);
  if (saved <= 0) return false;
  const duration = audio.duration;
  if (!Number.isFinite(duration) || duration <= 0) return false;
  if (saved >= duration - AUDIO_PROGRESS_END_MARGIN_SEC) {
    saveAudioProgress(lectureId, duration, duration);
    return false;
  }
  if (Math.abs(audio.currentTime - saved) > 1) {
    audio.currentTime = saved;
  }
  return true;
}

function bindAudioProgress(audio) {
  const lectureId = lectureIdFromAudio(audio);
  if (!Number.isFinite(lectureId)) return;

  let saveTimer = null;
  let restored = false;

  const attemptRestore = () => {
    if (restored) return;
    if (tryRestoreAudioProgress(audio, lectureId)) restored = true;
  };

  const persist = () => saveAudioProgress(lectureId, audio.currentTime, audio.duration);

  const scheduleSave = () => {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      if (!audio.paused && !audio.ended) persist();
    }, 2000);
  };

  audio.addEventListener('loadedmetadata', attemptRestore);
  audio.addEventListener('durationchange', attemptRestore);
  audio.addEventListener('play', attemptRestore);
  audio.addEventListener('timeupdate', scheduleSave);
  audio.addEventListener('pause', () => {
    clearTimeout(saveTimer);
    persist();
  });
  audio.addEventListener('ended', () => {
    clearTimeout(saveTimer);
    persist();
  });
}

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

let searchIndexLoadPromise = null;

function loadScriptOnce(src) {
  if (document.querySelector(`script[src="${src}"]`)) {
    return typeof SEARCH_INDEX !== 'undefined'
      ? Promise.resolve()
      : new Promise((resolve) => {
          const check = () => {
            if (typeof SEARCH_INDEX !== 'undefined') resolve();
            else setTimeout(check, 40);
          };
          check();
        });
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(script);
  });
}

function ensureSearchIndexLoaded() {
  if (typeof SEARCH_INDEX !== 'undefined') return Promise.resolve();
  if (!searchIndexLoadPromise) {
    searchIndexLoadPromise = loadScriptOnce('search-index.js');
  }
  return searchIndexLoadPromise;
}

const externalScriptPromises = new Map();

function loadExternalScript(src) {
  if (externalScriptPromises.has(src)) return externalScriptPromises.get(src);
  const promise = document.querySelector(`script[src="${src}"]`)
    ? Promise.resolve()
    : new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = src;
        script.async = true;
        script.onload = () => resolve();
        script.onerror = () => reject(new Error(`Failed to load ${src}`));
        document.head.appendChild(script);
      });
  externalScriptPromises.set(src, promise);
  return promise;
}

function homePreviewSkeleton(count = 4) {
  return Array.from({ length: count }, () => `
    <div class="home-skeleton-card" aria-hidden="true">
      <div class="home-skeleton-thumb"></div>
      <div class="home-skeleton-lines">
        <div class="home-skeleton-line home-skeleton-line--wide"></div>
        <div class="home-skeleton-line"></div>
      </div>
    </div>`).join('');
}

function homeSlideSkeleton() {
  return `<div class="home-skeleton-slide" aria-hidden="true">
    <div class="home-skeleton-slide-thumb"></div>
    <div class="home-skeleton-slide-body">
      <div class="home-skeleton-line home-skeleton-line--short"></div>
      <div class="home-skeleton-line home-skeleton-line--wide"></div>
      <div class="home-skeleton-line home-skeleton-line--medium"></div>
    </div>
  </div>`;
}

function dismissHomeBootScreen() {
  const screen = document.getElementById('homeBootScreen');
  if (!screen) return;
  screen.classList.add('is-done');
  window.setTimeout(() => screen.remove(), 450);
}

function revealHomeContent() {
  document.getElementById('homeMain')?.classList.add('is-ready');
  dismissHomeBootScreen();
}

let contentSwapReady = false;
let pageTransitionOverlay = null;

function prefersReducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function enableContentSwapSoon() {
  window.setTimeout(() => { contentSwapReady = true; }, 500);
}

function isInternalPageLink(anchor) {
  if (!anchor || anchor.target === '_blank' || anchor.hasAttribute('download')) return false;
  const href = anchor.getAttribute('href');
  if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) return false;
  try {
    const url = new URL(href, location.href);
    if (url.origin !== location.origin) return false;
    if (url.pathname === location.pathname) return false;
    return /\.html$/.test(url.pathname) || url.pathname.endsWith('/');
  } catch {
    return false;
  }
}

function getPageTransitionOverlay() {
  if (pageTransitionOverlay) return pageTransitionOverlay;
  pageTransitionOverlay = document.createElement('div');
  pageTransitionOverlay.className = 'page-transition-overlay';
  pageTransitionOverlay.setAttribute('aria-hidden', 'true');
  document.body.appendChild(pageTransitionOverlay);
  return pageTransitionOverlay;
}

function navigateWithTransition(href) {
  if (prefersReducedMotion()) {
    location.href = href;
    return;
  }
  const overlay = getPageTransitionOverlay();
  document.documentElement.classList.add('is-exiting');
  overlay.classList.add('page-transition-overlay--active');
  window.setTimeout(() => { location.href = href; }, 220);
}

function bindPageExitTransitions() {
  document.addEventListener('click', (e) => {
    const link = e.target.closest('a[href]');
    if (!link || e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (!isInternalPageLink(link)) return;
    e.preventDefault();
    navigateWithTransition(link.href);
  }, true);
}

function preparePageEnter() {
  const main = document.getElementById('homeMain') || document.querySelector('main');
  if (!main || main.id === 'homeMain') return;
  main.classList.add('site-page');
  requestAnimationFrame(() => {
    requestAnimationFrame(() => main.classList.add('site-page-ready'));
  });
}

function enhanceNavLinks() {
  document.querySelectorAll('[data-nav]').forEach((link) => {
    link.classList.add('site-nav-pill');
  });
}

function mountMotionStyles() {
  if (document.getElementById('site-motion-styles')) return;
  const style = document.createElement('style');
  style.id = 'site-motion-styles';
  style.textContent = `
    .page-transition-overlay {
      position: fixed;
      inset: 0;
      z-index: 200;
      pointer-events: none;
      opacity: 0;
      background: rgba(8, 13, 24, 0.55);
      backdrop-filter: blur(4px);
      -webkit-backdrop-filter: blur(4px);
      transition: opacity 0.22s ease;
    }
    .page-transition-overlay--active {
      opacity: 1;
      pointer-events: auto;
    }
    html.is-exiting body {
      pointer-events: none;
    }

    main.site-page {
      opacity: 0;
      transform: translateY(12px);
      transition: opacity 0.5s cubic-bezier(0.22, 1, 0.36, 1),
                  transform 0.5s cubic-bezier(0.22, 1, 0.36, 1);
    }
    main.site-page.site-page-ready {
      opacity: 1;
      transform: none;
    }

    .global-search-section {
      opacity: 0;
      transform: translateY(6px);
      transition: opacity 0.4s ease, transform 0.4s ease;
    }
    .global-search-section.site-search-enter--ready {
      opacity: 1;
      transform: none;
    }

    .site-nav-pill {
      transition: background-color 0.22s ease, color 0.22s ease,
                  box-shadow 0.22s ease, transform 0.15s ease;
    }
    .site-nav-pill:active {
      transform: scale(0.96);
    }

    .content-swap {
      transition: opacity 0.18s ease, transform 0.18s ease;
    }
    .content-swap-out {
      opacity: 0;
      transform: translateY(6px);
    }
    .content-swap-in {
      opacity: 1;
      transform: none;
    }

    .stagger-item {
      animation: site-stagger-in 0.38s cubic-bezier(0.22, 1, 0.36, 1) both;
      animation-delay: calc(var(--stagger-i, 0) * 45ms);
    }
    @keyframes site-stagger-in {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: none; }
    }

    .cat-btn, .sub-btn, .cat-picker-btn,
    #categoryChips button, #pagination button {
      transition: background-color 0.2s ease, color 0.2s ease,
                  border-color 0.2s ease, transform 0.15s ease;
    }
    .cat-btn:active, .sub-btn:active, .cat-picker-btn:active,
    #categoryChips button:active, #pagination button:active {
      transform: scale(0.97);
    }

    @media (prefers-reduced-motion: reduce) {
      .page-transition-overlay,
      main.site-page,
      .global-search-section,
      .content-swap,
      .stagger-item {
        transition: none !important;
        animation: none !important;
        transform: none !important;
        opacity: 1 !important;
      }
    }
  `;
  document.head.appendChild(style);
}

function initSiteMotion() {
  if (document.documentElement.dataset.motionInit) return;
  document.documentElement.dataset.motionInit = '1';
  mountMotionStyles();
  enhanceNavLinks();
  bindPageExitTransitions();
  preparePageEnter();
  enableContentSwapSoon();
}

function animateContentSwap(container, updateFn, { stagger = true } = {}) {
  if (!container) {
    if (updateFn) updateFn();
    return Promise.resolve();
  }
  if (!contentSwapReady || prefersReducedMotion()) {
    if (updateFn) updateFn();
    if (stagger && contentSwapReady) staggerRevealChildren(container);
    return Promise.resolve();
  }

  container.classList.add('content-swap');
  container.classList.add('content-swap-out');

  return new Promise((resolve) => {
    window.setTimeout(() => {
      if (updateFn) updateFn();
      container.classList.remove('content-swap-out');
      container.classList.add('content-swap-in');
      if (stagger) staggerRevealChildren(container);
      window.setTimeout(() => {
        container.classList.remove('content-swap-in');
        resolve();
      }, 320);
    }, 160);
  });
}

function staggerRevealChildren(container) {
  if (prefersReducedMotion()) return;
  container.querySelectorAll(':scope > *').forEach((el, i) => {
    el.classList.remove('stagger-item');
    el.style.setProperty('--stagger-i', String(i));
    void el.offsetWidth;
    el.classList.add('stagger-item');
  });
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
  pdf: { label: 'PDF', icon: 'fa-file-pdf', page: 'pdfs.html' },
};

function searchResultThumb(item, meta) {
  if (isValidThumb(item.thumb)) {
    return `<div class="global-search-thumb w-14 h-10 rounded-lg overflow-hidden thumb-box flex items-center justify-center flex-shrink-0 p-0.5">
      <img src="${thumbSrc(item.thumb)}" alt="" class="max-w-full max-h-full object-contain" loading="lazy"
        onerror="this.parentElement.outerHTML='<span class=\\'global-search-thumb w-9 h-9 rounded-lg bg-gold/10 border border-gold/20 flex items-center justify-center flex-shrink-0\\'><i class=\\'fas ${meta.icon} text-gold text-sm\\'></i></span>'">
    </div>`;
  }
  return `<span class="global-search-thumb w-9 h-9 rounded-lg bg-gold/10 border border-gold/20 flex items-center justify-center flex-shrink-0">
    <i class="fas ${meta.icon} text-gold text-sm"></i>
  </span>`;
}

function mountGlobalSearch({ inputId = 'globalSearch', resultsId = 'globalSearchResults' } = {}) {
  const input = document.getElementById(inputId);
  const results = document.getElementById(resultsId);
  if (!input || !results) return;

  let debounceTimer = null;
  let indexLoadPromise = null;

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
        <a href="${item.href}" class="global-search-result flex items-center gap-3 px-4 py-3 hover:bg-slate-800 transition border-b border-slate-800 last:border-0">
          ${searchResultThumb(item, meta)}
          <span class="min-w-0 flex-1">
            <span class="block text-sm text-slate-100 leading-snug line-clamp-2">${escapeHtml(item.title)}</span>
            <span class="block text-xs text-slate-500 mt-0.5">${escapeHtml(meta.label)}${item.sub ? ` · ${escapeHtml(item.sub)}` : ''}</span>
          </span>
          <i class="fas fa-arrow-right text-gold/40 text-xs flex-shrink-0"></i>
        </a>`;
    }).join('');
    results.classList.remove('hidden');
  };

  const loadIndex = () => {
    if (typeof SEARCH_INDEX !== 'undefined') return Promise.resolve();
    if (!indexLoadPromise) {
      results.innerHTML = '<p class="px-4 py-3 text-sm text-slate-500">Loading search…</p>';
      results.classList.remove('hidden');
      indexLoadPromise = ensureSearchIndexLoaded().catch(() => {
        indexLoadPromise = null;
        results.innerHTML = '<p class="px-4 py-3 text-sm text-slate-500">Search unavailable. Try again.</p>';
        throw new Error('search-index load failed');
      });
    }
    return indexLoadPromise;
  };

  input.addEventListener('focus', () => { loadIndex(); });

  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const query = input.value.trim();
      if (!query) {
        hideResults();
        return;
      }
      loadIndex().then(() => {
        if (typeof SEARCH_INDEX !== 'undefined') renderResults(searchGlobalIndex(query));
      }).catch(() => {});
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

function mountGlobalSearchShell() {
  if (document.getElementById('globalSearch')) {
    mountGlobalSearch();
    return;
  }
  const header = document.querySelector('.site-header');
  if (!header) return;

  const section = document.createElement('section');
  section.className = 'global-search-section max-w-7xl mx-auto px-4 sm:px-8 pt-4 sm:pt-5';
  section.setAttribute('aria-label', 'Site search');
  section.innerHTML = `
    <div class="relative max-w-2xl mx-auto">
      <label for="globalSearch" class="sr-only">Search audio, videos, clips, and PDFs</label>
      <i class="fas fa-search absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none"></i>
      <input id="globalSearch" type="search" placeholder="Search lectures, videos, clips, and PDFs…" autocomplete="off"
        class="w-full pl-11 pr-4 py-3 sm:py-3.5 rounded-xl bg-slate-900 border border-slate-700 focus:outline-none focus:border-gold/50 text-slate-100 placeholder:text-slate-500">
      <div id="globalSearchResults" class="global-search-panel hidden absolute left-0 right-0 top-full mt-2 z-50 rounded-xl border border-slate-700 bg-slate-925 overflow-hidden max-h-[min(24rem,60vh)] overflow-y-auto"></div>
    </div>`;

  const main = document.querySelector('main');
  if (main && main.parentNode) {
    main.parentNode.insertBefore(section, main);
  } else {
    header.insertAdjacentElement('afterend', section);
  }

  section.classList.add('site-search-enter');
  requestAnimationFrame(() => section.classList.add('site-search-enter--ready'));

  mountGlobalSearch();
}

function buildAudioLookup(pool) {
  const map = new Map();
  if (!Array.isArray(pool)) return map;
  for (const item of pool) {
    if (Number.isFinite(item.id)) map.set(item.id, item);
  }
  return map;
}

function mountContinueListening(audioLookup) {
  const section = document.getElementById('continueListeningSection');
  if (!section) return;

  const entries = getContinueListeningEntries(3);
  if (!entries.length) {
    section.classList.add('hidden');
    section.innerHTML = '';
    return;
  }

  const lookup = audioLookup instanceof Map ? audioLookup : buildAudioLookup(audioLookup);
  section.classList.remove('hidden');
  section.innerHTML = `
    <div class="flex items-center justify-between mb-4">
      <h2 class="font-display text-lg sm:text-xl text-gold-gradient flex items-center gap-2">
        <i class="fas fa-play-circle text-gold text-sm"></i> Continue listening
      </h2>
      <a href="audio.html" class="text-sm text-gold hover:text-gold-light">Audio library <i class="fas fa-arrow-right text-xs"></i></a>
    </div>
    <div id="continueListeningList" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3"></div>`;

  const listEl = document.getElementById('continueListeningList');
  listEl.innerHTML = entries.map((entry) => {
    const meta = lookup.get(entry.id);
    const title = meta?.title || `Lecture #${entry.id}`;
    const sub = meta?.categoryLabel || 'Audio lecture';
    const thumb = meta?.thumb;
    const href = `audio.html?lecture=${entry.id}`;
    const thumbHtml = thumb && isValidThumb(thumb)
      ? `<img src="${thumbSrc(thumb)}" alt="" class="max-w-full max-h-full object-contain" loading="lazy" onerror="this.style.display='none'">`
      : `<i class="fas fa-headphones text-gold/50 text-lg"></i>`;
    return `
      <a href="${href}" class="continue-listening-card card-hover flex items-center gap-3 p-3 rounded-xl border border-slate-800 bg-slate-900/60 group">
        <div class="continue-listening-thumb w-16 h-16 rounded-lg overflow-hidden thumb-box flex items-center justify-center flex-shrink-0 p-1">
          ${thumbHtml}
        </div>
        <div class="min-w-0 flex-1">
          <p class="text-sm font-medium text-slate-100 group-hover:text-gold transition line-clamp-2 leading-snug">${escapeHtml(title)}</p>
          <p class="text-xs text-slate-500 mt-0.5">${escapeHtml(sub)}</p>
          <p class="text-xs text-gold/80 mt-1.5 flex items-center gap-1.5">
            <i class="fas fa-clock text-[0.65rem]"></i> Resume at ${formatAudioTimestamp(entry.seconds)}
          </p>
        </div>
        <i class="fas fa-play text-gold/50 group-hover:text-gold text-sm flex-shrink-0"></i>
      </a>`;
  }).join('');

  section.classList.add('home-fade-in');
}

function mountLayoutFallback() {
  if (document.getElementById('layout-fallback')) return;
  const style = document.createElement('style');
  style.id = 'layout-fallback';
  style.textContent = `
    html.no-tailwind body {
      background-color: #080d18;
      color: #e2e8f0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      margin: 0;
    }
    html.no-tailwind .min-h-screen { min-height: 100vh; }
    html.no-tailwind .flex { display: flex; }
    html.no-tailwind .flex-col { flex-direction: column; }
    html.no-tailwind .flex-1 { flex: 1 1 0%; }
    html.no-tailwind .flex-shrink-0 { flex-shrink: 0; }
    html.no-tailwind .items-center { align-items: center; }
    html.no-tailwind .justify-center { justify-content: center; }
    html.no-tailwind .justify-between { justify-content: space-between; }
    html.no-tailwind .gap-1 { gap: 0.25rem; }
    html.no-tailwind .gap-2 { gap: 0.5rem; }
    html.no-tailwind .gap-3 { gap: 0.75rem; }
    html.no-tailwind .gap-8 { gap: 2rem; }
    html.no-tailwind .hidden { display: none !important; }
    html.no-tailwind .block { display: block; }
    html.no-tailwind .grid { display: grid; }
    html.no-tailwind .grid-cols-1 { grid-template-columns: repeat(1, minmax(0, 1fr)); }
    html.no-tailwind .relative { position: relative; }
    html.no-tailwind .absolute { position: absolute; }
    html.no-tailwind .sticky { position: sticky; }
    html.no-tailwind .top-0 { top: 0; }
    html.no-tailwind .left-0 { left: 0; }
    html.no-tailwind .right-0 { right: 0; }
    html.no-tailwind .top-1\\/2 { top: 50%; }
    html.no-tailwind .z-10 { z-index: 10; }
    html.no-tailwind .z-50 { z-index: 50; }
    html.no-tailwind .w-full { width: 100%; }
    html.no-tailwind .w-10 { width: 2.5rem; }
    html.no-tailwind .h-10 { height: 2.5rem; }
    html.no-tailwind .w-24 { width: 6rem; }
    html.no-tailwind .h-14 { height: 3.5rem; }
    html.no-tailwind .min-w-0 { min-width: 0; }
    html.no-tailwind .max-w-2xl { max-width: 42rem; }
    html.no-tailwind .max-w-7xl { max-width: 80rem; }
    html.no-tailwind .mx-auto { margin-left: auto; margin-right: auto; }
    html.no-tailwind .mb-3 { margin-bottom: 0.75rem; }
    html.no-tailwind .mb-4 { margin-bottom: 1rem; }
    html.no-tailwind .mb-6 { margin-bottom: 1.5rem; }
    html.no-tailwind .mt-2 { margin-top: 0.5rem; }
    html.no-tailwind .mt-3 { margin-top: 0.75rem; }
    html.no-tailwind .mt-5 { margin-top: 1.25rem; }
    html.no-tailwind .px-4 { padding-left: 1rem; padding-right: 1rem; }
    html.no-tailwind .px-5 { padding-left: 1.25rem; padding-right: 1.25rem; }
    html.no-tailwind .py-3 { padding-top: 0.75rem; padding-bottom: 0.75rem; }
    html.no-tailwind .py-4 { padding-top: 1rem; padding-bottom: 1rem; }
    html.no-tailwind .py-8 { padding-top: 2rem; padding-bottom: 2rem; }
    html.no-tailwind .py-10 { padding-top: 2.5rem; padding-bottom: 2.5rem; }
    html.no-tailwind .pt-6 { padding-top: 1.5rem; }
    html.no-tailwind .pt-8 { padding-top: 2rem; }
    html.no-tailwind .pb-6 { padding-bottom: 1.5rem; }
    html.no-tailwind .pb-16 { padding-bottom: 4rem; }
    html.no-tailwind .pl-11 { padding-left: 2.75rem; }
    html.no-tailwind .p-3 { padding: 0.75rem; }
    html.no-tailwind .p-4 { padding: 1rem; }
    html.no-tailwind .text-center { text-align: center; }
    html.no-tailwind .text-xs { font-size: 0.75rem; }
    html.no-tailwind .text-sm { font-size: 0.875rem; }
    html.no-tailwind .text-lg { font-size: 1.125rem; }
    html.no-tailwind .text-xl { font-size: 1.25rem; }
    html.no-tailwind .font-bold { font-weight: 700; }
    html.no-tailwind .font-medium { font-weight: 500; }
    html.no-tailwind .font-semibold { font-weight: 600; }
    html.no-tailwind .leading-snug { line-height: 1.375; }
    html.no-tailwind .leading-relaxed { line-height: 1.625; }
    html.no-tailwind .uppercase { text-transform: uppercase; }
    html.no-tailwind .tracking-wide { letter-spacing: 0.025em; }
    html.no-tailwind .tracking-widest { letter-spacing: 0.1em; }
    html.no-tailwind .rounded-lg { border-radius: 0.5rem; }
    html.no-tailwind .rounded-xl { border-radius: 0.75rem; }
    html.no-tailwind .rounded-2xl { border-radius: 1rem; }
    html.no-tailwind .rounded-full { border-radius: 9999px; }
    html.no-tailwind .border { border-width: 1px; border-style: solid; }
    html.no-tailwind .border-b { border-bottom-width: 1px; border-style: solid; }
    html.no-tailwind .border-t { border-top-width: 1px; border-style: solid; }
    html.no-tailwind .border-slate-700 { border-color: #334155; }
    html.no-tailwind .border-slate-800 { border-color: #1e293b; }
    html.no-tailwind .bg-slate-900 { background-color: #0f172a; }
    html.no-tailwind .bg-slate-950 { background-color: #080d18; }
    html.no-tailwind .bg-slate-925,
    html.no-tailwind .bg-slate-925\\/50,
    html.no-tailwind .bg-slate-925\\/90 { background-color: #0c1220; }
    html.no-tailwind .bg-slate-900\\/50,
    html.no-tailwind .bg-slate-900\\/60 { background-color: rgba(15, 23, 42, 0.6); }
    html.no-tailwind .bg-gold { background-color: #d4a853; }
    html.no-tailwind .bg-gold\\/90 { background-color: rgba(212, 168, 83, 0.9); }
    html.no-tailwind .bg-gold\\/15 { background-color: rgba(212, 168, 83, 0.15); }
    html.no-tailwind .text-white { color: #fff; }
    html.no-tailwind .text-slate-100 { color: #f1f5f9; }
    html.no-tailwind .text-slate-200 { color: #e2e8f0; }
    html.no-tailwind .text-slate-400 { color: #94a3b8; }
    html.no-tailwind .text-slate-500 { color: #64748b; }
    html.no-tailwind .text-slate-600 { color: #475569; }
    html.no-tailwind .text-slate-950 { color: #020617; }
    html.no-tailwind .text-gold { color: #d4a853; }
    html.no-tailwind .overflow-hidden { overflow: hidden; }
    html.no-tailwind .overflow-y-auto { overflow-y: auto; }
    html.no-tailwind .space-y-3 > * + * { margin-top: 0.75rem; }
    html.no-tailwind .-translate-y-1\\/2 { transform: translateY(-50%); }
    html.no-tailwind .shadow-lg { box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3); }
    html.no-tailwind .shadow-2xl { box-shadow: 0 25px 50px -12px rgba(0,0,0,0.45); }
    html.no-tailwind .sr-only {
      position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
      overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0;
    }
    html.no-tailwind #slideTrack { display: flex; }
    html.no-tailwind [data-slide] { flex-shrink: 0; width: 100%; }
    html.no-tailwind .site-header { border-bottom: 1px solid #1e293b; background: rgba(12, 18, 32, 0.95); }
    html.no-tailwind input[type="search"] {
      width: 100%; box-sizing: border-box;
      background: #0f172a; color: #f1f5f9; border: 1px solid #334155;
    }
    @media (min-width: 640px) {
      html.no-tailwind .sm\\:flex { display: flex; }
      html.no-tailwind .sm\\:flex-row { flex-direction: row; }
      html.no-tailwind .sm\\:hidden { display: none !important; }
      html.no-tailwind .sm\\:px-8 { padding-left: 2rem; padding-right: 2rem; }
      html.no-tailwind .sm\\:pt-8 { padding-top: 2rem; }
      html.no-tailwind .sm\\:pt-12 { padding-top: 3rem; }
      html.no-tailwind .sm\\:py-14 { padding-top: 3.5rem; padding-bottom: 3.5rem; }
      html.no-tailwind .sm\\:text-3xl { font-size: 1.875rem; }
      html.no-tailwind .sm\\:w-12 { width: 3rem; }
      html.no-tailwind .sm\\:h-12 { height: 3rem; }
      html.no-tailwind .sm\\:left-5 { left: 1.25rem; }
      html.no-tailwind .sm\\:right-5 { right: 1.25rem; }
      html.no-tailwind .sm\\:inline { display: inline; }
    }
    @media (min-width: 1024px) {
      html.no-tailwind .lg\\:grid-cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    }
  `;
  document.head.appendChild(style);
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

    .global-search-section { position: relative; z-index: 45; }
    .global-search-section + main { padding-top: 0.25rem; }

    .continue-listening-card .line-clamp-2 {
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
  `;
  document.head.appendChild(style);
}

function mountTopBar() {
  initCloudflareAnalytics();
  initSiteMotion();
  mountLayoutFallback();
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

  mountGlobalSearchShell();
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

function downloadIconLink(url, { label = 'Download', className = '' } = {}) {
  if (!url) return '';
  return `<a href="${url}" class="media-download-link inline-flex items-center justify-center w-8 h-8 rounded-lg text-slate-500 hover:text-gold hover:bg-slate-800/80 transition flex-shrink-0 ${className}" target="_blank" rel="noopener" download title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}">
    <i class="fas fa-download text-sm"></i>
  </a>`;
}

function downloadGlassLink(url, { label = 'Download' } = {}) {
  if (!url) return '';
  return `<a href="${url}" class="lecture-download-glass" target="_blank" rel="noopener" download title="${escapeHtml(label)}" aria-label="${escapeHtml(label)}">
    <i class="fas fa-download"></i>
  </a>`;
}

function previewButtonHtml({ embedUrl, title = '', downloadUrl = '', detailsUrl = '', label = 'Read', fullWidth = false }) {
  if (!embedUrl) return '';
  const widthClass = fullWidth ? 'w-full justify-center' : 'w-fit';
  return `<button type="button" class="pdf-preview-btn inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-gold/25 bg-gold/10 text-gold hover:bg-gold/20 hover:border-gold/40 text-xs font-medium transition ${widthClass}"
    data-title="${escapeHtml(title)}" data-embed="${escapeHtml(embedUrl)}" data-download="${escapeHtml(downloadUrl)}" data-details="${escapeHtml(detailsUrl)}">
    <i class="fas fa-book-open"></i> ${escapeHtml(label)}
  </button>`;
}

function archivePdfEmbedUrl(identifier, archivePath) {
  const encoded = archivePath.split('/').map(part => encodeURIComponent(part)).join('/');
  return `https://archive.org/embed/${identifier}/${encoded}#page/n1/mode/1up`;
}

let pdfPreviewModalMounted = false;

function mountPdfPreviewModal() {
  if (pdfPreviewModalMounted || document.getElementById('pdfPreviewModal')) return;
  pdfPreviewModalMounted = true;

  const modal = document.createElement('div');
  modal.id = 'pdfPreviewModal';
  modal.className = 'fixed inset-0 z-[80] hidden';
  modal.setAttribute('role', 'dialog');
  modal.setAttribute('aria-modal', 'true');
  modal.setAttribute('aria-hidden', 'true');
  modal.innerHTML = `
    <button type="button" id="pdfPreviewBackdrop" class="absolute inset-0 bg-slate-950/85 backdrop-blur-sm" aria-label="Close preview"></button>
    <div class="relative z-10 h-full flex flex-col p-3 sm:p-5 max-w-6xl mx-auto">
      <div class="flex items-start justify-between gap-3 mb-3 shrink-0">
        <div class="min-w-0">
          <p class="text-[10px] uppercase tracking-widest text-slate-500 mb-1">PDF preview</p>
          <h2 id="pdfPreviewTitle" class="font-display text-lg sm:text-xl text-gold-gradient leading-snug line-clamp-2"></h2>
        </div>
        <button type="button" id="pdfPreviewClose" class="w-10 h-10 rounded-full border border-slate-700 text-slate-400 hover:text-gold hover:border-gold/40 transition shrink-0" aria-label="Close preview">
          <i class="fas fa-times"></i>
        </button>
      </div>
      <div class="pdf-preview-frame relative flex-1 min-h-[min(75vh,calc(100dvh-11rem))] rounded-xl overflow-hidden border border-slate-700 bg-slate-900 shadow-2xl shadow-black/40">
        <div id="pdfPreviewLoader" class="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-slate-900 text-slate-400">
          <i class="fas fa-circle-notch fa-spin text-2xl text-gold"></i>
          <span class="text-sm">Loading PDF…</span>
        </div>
        <iframe id="pdfPreviewFrame" title="PDF preview" class="relative z-20 w-full h-full border-0 bg-white" allow="fullscreen"></iframe>
      </div>
      <div class="flex flex-wrap items-center justify-between gap-3 mt-3 shrink-0">
        <p class="text-xs text-slate-500">Preview from Internet Archive</p>
        <div class="flex flex-wrap gap-2">
          <a id="pdfPreviewArchiveLink" href="#" class="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-700 text-slate-300 hover:border-gold/40 hover:text-gold text-xs font-medium transition" target="_blank" rel="noopener">
            <i class="fas fa-external-link-alt"></i> View on Archive
          </a>
          <a id="pdfPreviewDownloadLink" href="#" class="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-gold/40 bg-gold/10 text-gold text-xs font-medium transition hover:bg-gold/20" target="_blank" rel="noopener" download>
            <i class="fas fa-download"></i> Download
          </a>
        </div>
      </div>
    </div>`;
  document.body.appendChild(modal);

  const closePreview = () => {
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
    const frame = document.getElementById('pdfPreviewFrame');
    const loader = document.getElementById('pdfPreviewLoader');
    frame.src = 'about:blank';
    frame.onload = null;
    frame.onerror = null;
    if (loader) {
      loader.classList.remove('hidden');
      loader.innerHTML = '<i class="fas fa-circle-notch fa-spin text-2xl text-gold"></i><span class="text-sm">Loading PDF…</span>';
    }
    document.body.classList.remove('overflow-hidden');
  };

  document.getElementById('pdfPreviewBackdrop').onclick = closePreview;
  document.getElementById('pdfPreviewClose').onclick = closePreview;
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !modal.classList.contains('hidden')) closePreview();
  });
}

function pdfPreviewSrc(downloadUrl, detailsUrl) {
  if (downloadUrl) return downloadUrl;
  if (detailsUrl) return `${detailsUrl}${detailsUrl.includes('?') ? '&' : '?'}view=theater`;
  return '';
}

function openPdfPreview({ title, embedUrl, downloadUrl, detailsUrl }) {
  mountPdfPreviewModal();
  const modal = document.getElementById('pdfPreviewModal');
  const frame = document.getElementById('pdfPreviewFrame');
  const loader = document.getElementById('pdfPreviewLoader');
  const previewUrl = pdfPreviewSrc(downloadUrl, detailsUrl) || embedUrl;

  document.getElementById('pdfPreviewTitle').textContent = title || 'PDF preview';
  if (loader) loader.classList.remove('hidden');

  frame.onload = () => {
    if (loader) loader.classList.add('hidden');
  };
  frame.onerror = () => {
    if (loader) {
      loader.innerHTML = '<p class="text-sm text-slate-400 px-6 text-center">Preview could not load. Use <strong class="text-gold">View on Archive</strong> or <strong class="text-gold">Download</strong> below.</p>';
    }
  };

  frame.src = 'about:blank';
  requestAnimationFrame(() => {
    frame.src = previewUrl;
  });

  const archiveLink = document.getElementById('pdfPreviewArchiveLink');
  const downloadLink = document.getElementById('pdfPreviewDownloadLink');
  if (detailsUrl) archiveLink.href = detailsUrl;
  if (downloadUrl) downloadLink.href = downloadUrl;
  modal.classList.remove('hidden');
  modal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('overflow-hidden');
}

function bindPdfPreviewControls(root = document) {
  root.querySelectorAll('.pdf-preview-btn, .pdf-preview-open').forEach(el => {
    if (el.dataset.boundPreview) return;
    el.dataset.boundPreview = '1';
    el.addEventListener('click', () => {
      openPdfPreview({
        title: el.getAttribute('data-title') || '',
        embedUrl: el.getAttribute('data-embed') || '',
        downloadUrl: el.getAttribute('data-download') || '',
        detailsUrl: el.getAttribute('data-details') || '',
      });
    });
  });
}

function pdfPartSubtitle(title, series) {
  if (!series) return title;
  let sub = title;
  const seriesLower = series.toLowerCase();
  if (sub.toLowerCase().startsWith(seriesLower)) {
    sub = sub.slice(series.length).replace(/^[\s–—-]+/, '').trim();
  }
  sub = sub.replace(/^part\s*\d+\s*[\s–—-]*/i, '').trim();
  return sub || title;
}

function pdfPartCard(data) {
  const {
    id, title, sizeLabel, downloadUrl, embedUrl, detailsUrl, thumb, series, part,
  } = data;
  const partLabel = part ? `Part ${part}` : 'Part';
  const subtitle = pdfPartSubtitle(title, series);
  const hasThumb = isValidThumb(thumb);

  const previewArea = embedUrl
    ? `<button type="button" class="pdf-preview-open group relative w-full aspect-[3/4] bg-slate-950 overflow-hidden text-left"
        data-title="${escapeHtml(title)}" data-embed="${escapeHtml(embedUrl)}" data-download="${escapeHtml(downloadUrl || '')}" data-details="${escapeHtml(detailsUrl || '')}" aria-label="Preview ${escapeHtml(partLabel)}">
        <div class="absolute inset-0 bg-gradient-to-b from-slate-900 to-slate-950"></div>
        ${hasThumb ? `<img src="${thumbSrc(thumb)}" alt="" class="absolute inset-0 w-full h-full object-cover object-top" loading="lazy" onerror="this.style.display='none'">` : ''}
        <div class="absolute inset-0 bg-slate-950/10 group-hover:bg-slate-950/30 transition"></div>
        <span class="absolute top-2 left-2 z-10 px-2 py-1 rounded-md bg-gold text-slate-950 text-xs font-bold">${escapeHtml(partLabel)}</span>
      </button>`
    : `<div class="w-full aspect-[3/4] bg-slate-950 flex items-center justify-center"><span class="text-gold font-bold">${escapeHtml(partLabel)}</span></div>`;

  return `
    <article id="${id || ''}" class="pdf-part-card w-[11.5rem] sm:w-[13rem] flex-shrink-0 snap-start bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden flex flex-col hover:border-gold/30 transition-all">
      ${previewArea}
      <div class="p-3 flex flex-col flex-1 min-w-0">
        <p class="text-[10px] uppercase tracking-wider text-gold/90 mb-1">${escapeHtml(partLabel)}</p>
        <h3 class="font-medium text-xs text-slate-100 leading-snug mb-2 line-clamp-3" title="${escapeHtml(subtitle)}">${escapeHtml(subtitle)}</h3>
        <div class="flex items-center justify-between gap-2 mb-2">
          <p class="text-[10px] text-slate-500">${escapeHtml(sizeLabel || '')}</p>
          ${downloadIconLink(downloadUrl, { label: 'Download PDF' })}
        </div>
        <div class="mt-auto">
          ${previewButtonHtml({ embedUrl, title, downloadUrl, detailsUrl, label: 'Read', fullWidth: true })}
        </div>
      </div>
    </article>`;
}

function pdfSeriesBlock({ name, items, categoryLabel, showCategory = false }) {
  const cards = items.map((pdf, index) => {
    const card = pdfPartCard({
      id: 'pdf-' + pdf.id,
      title: pdf.title,
      sizeLabel: pdf.sizeLabel,
      downloadUrl: pdf.download,
      embedUrl: pdf.embed,
      detailsUrl: pdf.details,
      thumb: pdf.thumb,
      series: pdf.series,
      part: pdf.part,
    });
    const arrow = index < items.length - 1
      ? `<span class="hidden sm:flex items-center text-gold/30 flex-shrink-0 px-0.5" aria-hidden="true"><i class="fas fa-chevron-right text-sm"></i></span>`
      : '';
    return card + arrow;
  }).join('');

  const meta = [
    `${items.length} parts`,
    'read in order',
    showCategory && categoryLabel ? categoryLabel : '',
  ].filter(Boolean).join(' · ');

  return `
    <div class="pdf-series-block rounded-2xl border border-slate-800 bg-slate-900/50 p-4 sm:p-5">
      <div class="flex flex-wrap items-center justify-between gap-2 mb-4">
        <h3 class="font-display text-lg sm:text-xl text-gold-gradient flex items-center gap-2">
          <i class="fas fa-layer-group text-sm text-gold/80"></i>
          ${escapeHtml(name)}
        </h3>
        <span class="text-xs text-slate-500">${escapeHtml(meta)}</span>
      </div>
      <div class="pdf-series-track flex items-stretch gap-3 sm:gap-2 overflow-x-auto pb-1 snap-x snap-mandatory scroll-smooth">
        ${cards}
      </div>
    </div>`;
}

function pdfSeriesBadge({ series, part, categoryLabel }) {
  if (series && part) {
    return `<span class="absolute top-2 left-2 z-10 px-2 py-0.5 rounded-md bg-slate-950/85 text-gold text-[10px] font-semibold uppercase tracking-wider border border-gold/20">${escapeHtml(series)} · Part ${part}</span>`;
  }
  if (series) {
    return `<span class="absolute top-2 left-2 z-10 px-2 py-0.5 rounded-md bg-slate-950/85 text-gold text-[10px] font-semibold uppercase tracking-wider border border-gold/20">${escapeHtml(series)}</span>`;
  }
  if (categoryLabel) {
    return `<span class="absolute top-2 left-2 z-10 px-2 py-0.5 rounded-md bg-slate-950/85 text-slate-300 text-[10px] font-semibold uppercase tracking-wider border border-slate-700">${escapeHtml(categoryLabel)}</span>`;
  }
  return '';
}

function pdfCard({ id, title, sizeLabel, downloadUrl, embedUrl, detailsUrl, thumb, series, part, categoryLabel }) {
  const badge = pdfSeriesBadge({ series, part, categoryLabel });
  const hasThumb = isValidThumb(thumb);
  const thumbImg = hasThumb
    ? `<img src="${thumbSrc(thumb)}" alt="" class="absolute inset-0 w-full h-full object-cover object-top transition duration-300 group-hover:scale-[1.02]" loading="lazy"
        onerror="this.style.display='none'">`
    : '';
  const thumbFallback = hasThumb ? '' : `
        <div class="absolute inset-0 flex flex-col items-center justify-center gap-2 p-4 text-center">
          <span class="w-14 h-14 rounded-2xl bg-red-950/60 border border-red-900/40 flex items-center justify-center">
            <i class="fas fa-file-pdf text-3xl text-red-400/90"></i>
          </span>
        </div>`;

  const previewBlock = embedUrl
    ? `<button type="button" class="pdf-preview-open group relative w-full aspect-[4/5] bg-slate-950 border-b border-slate-800 overflow-hidden text-left"
        data-title="${escapeHtml(title)}" data-embed="${escapeHtml(embedUrl)}" data-download="${escapeHtml(downloadUrl || '')}" data-details="${escapeHtml(detailsUrl || '')}" aria-label="Preview ${escapeHtml(title)}">
        <div class="absolute inset-0 bg-gradient-to-b from-slate-900 via-slate-950 to-slate-900"></div>
        ${thumbImg}
        ${thumbFallback}
        ${badge}
        <div class="absolute inset-0 bg-slate-950/0 group-hover:bg-slate-950/35 transition"></div>
        <div class="absolute inset-x-0 bottom-0 p-3 bg-gradient-to-t from-slate-950/95 via-slate-950/70 to-transparent">
          <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-950/85 text-[10px] font-medium text-slate-200 border border-slate-700 group-hover:border-gold/40 group-hover:text-gold transition">
            <i class="fas fa-eye text-[9px]"></i> Preview
          </span>
        </div>
      </button>`
    : `<div class="w-full aspect-[4/5] bg-slate-950 border-b border-slate-800 overflow-hidden relative flex items-center justify-center">
        ${hasThumb ? `<img src="${thumbSrc(thumb)}" alt="" class="absolute inset-0 w-full h-full object-cover object-top" loading="lazy">` : '<i class="fas fa-file-pdf text-4xl text-red-400/70"></i>'}
      </div>`;

  return `
    <article id="${id || ''}" class="pdf-card bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden flex flex-col hover:border-gold/30 transition-all hover:-translate-y-0.5">
      ${previewBlock}
      <div class="p-4 flex flex-col flex-1 min-w-0">
        ${series ? `<p class="text-[10px] uppercase tracking-wider text-gold/80 mb-1 line-clamp-1">${escapeHtml(series)}${part ? ` · Part ${part}` : ''}</p>` : (categoryLabel ? `<p class="text-[10px] uppercase tracking-wider text-slate-500 mb-1 line-clamp-1">${escapeHtml(categoryLabel)}</p>` : '')}
        <h3 class="font-medium text-sm text-slate-100 leading-snug mb-2 line-clamp-3" title="${escapeHtml(title)}">${escapeHtml(title)}</h3>
        <div class="flex items-center justify-between gap-2 mt-auto pt-1">
          <p class="text-xs text-slate-500">${escapeHtml(sizeLabel || '')}</p>
          ${downloadIconLink(downloadUrl, { label: 'Download PDF' })}
        </div>
      </div>
    </article>`;
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

function mediaCard({ id, thumb, title, badge, stream, downloadUrl, posterOnly = false, hideThumbImage = false }) {
  const encThumb = thumbSrc(thumb);
  const poster = encThumb ? `poster="${encThumb}"` : '';
  const imgBlock = encThumb
    ? `<img src="${encThumb}" alt="" class="relative z-[1] max-w-full max-h-full object-contain" loading="lazy" onerror="this.style.display='none'">`
    : `<i class="fas fa-play-circle text-4xl text-gold/25"></i>`;
  const badgeHtml = badge ? `<span class="absolute top-2 left-2 z-10 px-2 py-0.5 rounded-md bg-slate-950/85 text-gold text-[10px] font-semibold uppercase tracking-wider">${escapeHtml(badge)}</span>` : '';
  const downloadLink = downloadIconLink(downloadUrl || stream, {
    label: 'Download video',
    className: 'absolute top-2 right-2 z-10 bg-slate-950/75 backdrop-blur-sm border border-slate-700/80 hover:border-gold/40',
  });
  const videoBlock = posterOnly ? '' : `
    <div class="relative mt-auto">
      <video controls preload="none" playsinline class="w-full rounded-lg bg-black ${hideThumbImage ? 'aspect-video' : ''}" ${poster}>
        <source src="${stream}" type="video/mp4">
      </video>
      ${downloadLink}
    </div>`;

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