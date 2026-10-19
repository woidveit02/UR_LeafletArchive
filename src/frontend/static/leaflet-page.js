// Leaflet page: search hits, the metadata box, the sheet strip, the scan popup and the evidence buttons.
// mark the search terms in the transcription and show hit #treffer-N (default: the first);
// picture descriptions are not OCR text, so they are left out to keep the numbering of the list
const highlightTerms = document.getElementById('highlight-terms');
if (highlightTerms) {
    const terms = JSON.parse(highlightTerms.textContent)
        .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/ /g, '\\s+'));
    const re = new RegExp(`(${terms.join('|')})`, 'i');
    document.querySelectorAll('.ocr-block:not(.ocr-picture)').forEach((block) => {
        const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
        const nodes = [];
        while (walker.nextNode()) nodes.push(walker.currentNode);
        nodes.forEach((node) => {
            const parts = node.data.split(re);
            if (parts.length > 1) node.replaceWith(...parts.map((p, i) => i % 2
                ? Object.assign(document.createElement('mark'), {textContent: p}) : p));
        });
    });
    const marks = document.querySelectorAll('.ocr-block mark');
    const n = Number((location.hash.match(/^#treffer-(\d+)$/) || [])[1] || 1);
    const target = marks[Math.min(n, marks.length) - 1];
    if (target) {
        target.classList.add('current');
        target.scrollIntoView({block: 'center'});
    }
}

const pick = initEvidencePicking('.ocr-box[data-block], .ocr-block[data-block]');

document.addEventListener('click', (e) => {
    // evidence popups inside the folded row must not unfold it
    if (e.target.closest('summary .beleg-pop')) e.preventDefault();
    if (e.target.matches('[data-fold]')) e.target.closest('details').open = false;
});
document.addEventListener('toggle', (e) => {
    if (!e.target.matches?.('.meta-details')) return;
    try { localStorage.setItem('meta-open', e.target.open ? '1' : '0'); } catch (err) {}
}, true);

// edit in place: fetch the edit version and swap only title and metadata box
document.addEventListener('click', async (e) => {
    const link = e.target.closest('a[data-swap="edit"]');
    if (!link) return;
    e.preventDefault();
    try {
        const page = new DOMParser().parseFromString(await (await fetch(link.href)).text(), 'text/html');
        document.querySelector('.meta-area').replaceWith(page.querySelector('.meta-area'));
        document.querySelector('.meta-form [name=title]')?.focus({ preventScroll: true });
    } catch (err) {
        location.href = link.href;  // fall back to loading the edit page
    }
});

// the page strip marks the sheet in view; the outline closes when a heading is chosen
const strip = document.querySelector('.page-nav');
if (strip) {
    // the strip sticks below the top bar, the scan below the strip: both heights change with the window width
    const topbar = document.querySelector('.topbar');
    const measure = () => {
        document.documentElement.style.setProperty('--topbar-h', `${topbar.offsetHeight}px`);
        document.documentElement.style.setProperty('--strip-h', `${strip.offsetHeight}px`);
    };
    new ResizeObserver(measure).observe(strip);
    new ResizeObserver(measure).observe(topbar);
    measure();
    const links = Object.fromEntries([...strip.querySelectorAll('[data-page]')].map((a) => [a.dataset.page, a]));
    const spy = new IntersectionObserver((entries) => {
        entries.filter((en) => en.isIntersecting).forEach((en) => {
            Object.values(links).forEach((a) => a.removeAttribute('aria-current'));
            links[en.target.id]?.setAttribute('aria-current', 'true');
        });
    }, { rootMargin: '-25% 0px -60% 0px' });
    document.querySelectorAll('.page-pair').forEach((section) => spy.observe(section));
    strip.querySelector('.page-outline')?.addEventListener('click', (e) => {
        if (e.target.closest('a')) e.currentTarget.open = false;
    });
}

// the magnifier beside a section of the transcription shows that section of the scan, enlarged, with its text;
// the text itself stays free to select and copy
const popup = document.getElementById('scan-popup');
if (popup) {
    document.querySelectorAll('.pair-text .ocr-block[data-block]').forEach((block) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'block-scan';
        button.title = 'Diese Stelle im Scan zeigen';
        button.setAttribute('aria-label', 'Diese Stelle im Scan zeigen');
        block.append(button);
    });
    document.addEventListener('click', (e) => {
        const block = e.target.closest('.block-scan')?.parentElement;
        if (!block) return;
        const id = block.dataset.block, page = id.split('-')[0], base = `/leaflets/${popup.dataset.leaflet}`;
        popup.querySelector('.popup-grid').innerHTML = `<figure><figcaption>Bandseite ${page}
            <a href="${base}/pages/${page}.png?dpi=220" target="_blank" rel="noopener">ganze Seite ↗</a></figcaption>
            <img src="${base}/evidence.png?blocks=${id}" alt="Ausschnitt aus dem Scan"></figure>`;
        if (!block.classList.contains('ocr-picture')) {
            const transcript = document.createElement('div');
            transcript.className = 'popup-text ocr-page';
            const copy = block.cloneNode(true);
            copy.querySelector('.block-scan').remove();
            transcript.innerHTML = copy.innerHTML;
            popup.querySelector('figure').after(transcript);
        }
        popup.showModal();
    });
    document.getElementById('popup-close').addEventListener('click', () => popup.close());
    popup.addEventListener('click', (e) => { if (e.target === popup) popup.close(); });  // the backdrop
}

const { highlight, flash, link } = PagePair;

document.querySelectorAll('.ocr-block[data-block]').forEach((block) => {
    const box = document.querySelector(`.ocr-box[data-block="${block.dataset.block}"]`);
    if (box) link(block, box);
});

// a picture in the transcription is as large as its place on the scan, not stretched to the column
const fitPictures = () => document.querySelectorAll('.ocr-picture[data-block] img').forEach((img) => {
    const box = document.querySelector(`.ocr-box[data-block="${img.closest('.ocr-picture').dataset.block}"]`);
    const width = box?.getBoundingClientRect().width;
    if (width) Object.assign(img.style, {width: width + 'px', height: 'auto', maxHeight: 'none'});
});
window.addEventListener('load', fitPictures);
window.addEventListener('resize', fitPictures);

const closeAll = () => document.querySelectorAll('.beleg').forEach((b) => {
    b.nextElementSibling.hidden = true;
    b.setAttribute('aria-expanded', 'false');
});
document.querySelectorAll('.beleg').forEach((btn) => {
    const pop = btn.nextElementSibling;
    const targets = btn.dataset.evidence.split(' ')
        .flatMap((id) => [...document.querySelectorAll(`[data-block="${id}"]`)]);
    btn.addEventListener('mouseenter', () => highlight(targets, true));
    btn.addEventListener('mouseleave', () => highlight(targets, false));
    btn.addEventListener('click', () => {
        const opening = pop.hidden;
        closeAll();
        if (!opening) return;
        pop.querySelectorAll('img[data-src]').forEach((img) => { img.src = img.dataset.src; });
        pop.hidden = false;
        btn.setAttribute('aria-expanded', 'true');
    });
    pop.querySelector('.beleg-close').addEventListener('click', () => { closeAll(); btn.focus(); });
    pop.querySelector('.beleg-scan').addEventListener('click', () => {
        closeAll();
        flash(targets);
    });
});
document.addEventListener('click', (e) => { if (!e.target.closest('.beleg-wrap')) closeAll(); });
document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (pick.active()) { pick.stop(false); return; }
    const open = document.querySelector('.beleg[aria-expanded="true"]');
    closeAll();
    open?.focus();
});
// left and right, or the number of a sheet, move between the sheets of this leaflet; up and down keep scrolling
document.addEventListener('keydown', (e) => {
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || pick.active() || e.target.closest('input, textarea, select, [contenteditable]')) return;
    if (!/^(Arrow(Left|Right)|[1-9])$/.test(e.key)) return;
    // the same as clicking a number in the strip; a short leaflet has no strip, then the sheet's anchor is followed
    const links = [...document.querySelectorAll('.page-nav-pages a')];
    const sheets = [...document.querySelectorAll('.page-pair')];
    const edge = parseFloat(getComputedStyle(sheets[0] || document.body).scrollMarginTop) + 5;
    const now = links.length ? links.findIndex(a => a.hasAttribute('aria-current'))
        : sheets.filter(s => s.getBoundingClientRect().top <= edge).length - 1;
    const index = /\d/.test(e.key) ? e.key - 1 : now + (e.key === 'ArrowRight' ? 1 : -1);
    if (!sheets[index]) return;
    e.preventDefault();
    if (links[index]) links[index].click(); else location.hash = sheets[index].id;
});
