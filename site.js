/* Shared helpers for Shaykh Abdullah Faisal Archive */
const SITE_DISCLAIMER = `This is not an official website and is not affiliated with Shaykh Abdullah Faisal. This archive is maintained independently and is intended strictly for educational purposes.`;
const TELEGRAM_URL = 'https://t.me/ShaykhAbdullahFaisal';

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
      .audio-cat-nav {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch;
        gap: 0.5rem !important;
        max-height: none !important;
        padding-bottom: 0.375rem;
        scrollbar-width: none;
      }
      .audio-cat-nav::-webkit-scrollbar { display: none; }
      .audio-cat-nav .cat-btn {
        width: auto !important;
        flex-shrink: 0;
        white-space: nowrap;
        min-height: 2.75rem;
        padding: 0.625rem 0.875rem !important;
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
  `;
  document.head.appendChild(style);
}

function mountTopBar() {
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
  el.innerHTML = `<a href="${TELEGRAM_URL}" class="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-slate-700 text-slate-300 hover:border-gold/40 hover:text-gold transition text-sm" target="_blank" rel="noopener"><i class="fa-brands fa-telegram text-lg"></i> @ShaykhAbdullahFaisal</a>`;
}

function archiveStreamUrl(base, path) {
  return base + encodeURI(path).replace(/%2F/g, '/');
}

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
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