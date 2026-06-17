/* Shared helpers for Shaykh Abdullah Faisal Archive */
const SITE_DISCLAIMER = `This is not an official website and is not affiliated with Shaykh Abdullah Faisal. This archive is maintained independently and is intended strictly for educational purposes.`;

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
    <article id="${id || ''}" class="media-card bg-slate-900/70 border border-slate-800 rounded-2xl overflow-hidden flex flex-col hover:border-gold/30 transition-all hover:-translate-y-0.5">
      ${thumbSection}
      <div class="p-4 flex flex-col flex-1 min-h-0">
        <h3 class="font-medium text-sm text-slate-100 leading-snug ${hideThumbImage ? 'mb-4' : 'mb-3'} line-clamp-3" title="${escapeHtml(title)}">${escapeHtml(title)}</h3>
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