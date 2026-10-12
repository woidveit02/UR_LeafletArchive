// Checking the text recognition one page at a time, in the layout of the leaflet page: the transcription next to the
// scan with the boxes of the recognized blocks (page-pair.js links them).
(() => {
    const box = document.getElementById('page-check');
    if (!box) return;
    const pages = Number(box.dataset.pages);
    const input = box.querySelector('input');
    const pair = document.getElementById('check-pair');
    const frame = document.getElementById('check-frame');
    const img = document.getElementById('check-scan');
    const wrap = document.getElementById('check-scan-wrap');
    const body = document.getElementById('check-body');
    let current = 0;

    const render = (n, blocks) => {
        frame.querySelectorAll('.ocr-box').forEach((el) => el.remove());
        body.replaceChildren();
        if (!blocks.length) body.innerHTML = '<p class="meta">Kein OCR-Text auf dieser Seite.</p>';
        blocks.forEach((block, i) => {
            const id = `${n}-${i + 1}`;
            const mark = document.createElement('span');
            mark.className = 'ocr-box';
            mark.dataset.block = id;
            mark.style.cssText = `left: ${block.box[0]}%; top: ${block.box[1]}%; width: ${block.box[2]}%; height: ${block.box[3]}%;`;
            frame.append(mark);

            let el;
            if (block.type === 'Picture') {
                el = document.createElement('figure');
                el.className = 'ocr-block ocr-picture';
                if (block.image) {
                    const picture = document.createElement('img');
                    picture.src = box.dataset.images + block.image;
                    picture.alt = block.description || 'Abbildung';
                    el.append(picture);
                }
                const caption = document.createElement('figcaption');
                caption.textContent = block.description ? `${block.description} (Bildbeschreibung, automatisch erzeugt)` : '[Abbildung]';
                el.append(caption);
            } else {
                el = document.createElement('div');
                el.className = `ocr-block ocr-${block.type.toLowerCase()}`;
                el.innerHTML = block.html;  // sanitized by the app when it reads the Datalab result, as on the leaflet page
            }
            el.dataset.block = id;
            body.append(el);
            PagePair.link(el, mark);
        });
    };

    const show = async (wanted) => {
        const n = Math.min(pages, Math.max(1, Math.round(wanted) || 1));
        current = n;
        input.value = n;
        box.querySelector('.check-scroll').scrollTop = 0;
        img.classList.remove('loaded');
        img.onload = () => {
            pair.style.setProperty('--ratio', img.naturalWidth / img.naturalHeight);  // the scan is sized to the screen
            img.classList.add('loaded');
        };
        img.src = wrap.href = box.dataset.large.replace('{n}', n);  // the large rendering: single words must be readable
        body.textContent = 'Wird geladen …';
        try {
            const answer = await (await fetch(box.dataset.url.replace('{n}', n))).json();
            if (current === n) render(n, answer.blocks);
        } catch (e) {
            if (current === n) body.textContent = 'Der Text konnte nicht geladen werden.';
        }
    };

    box.addEventListener('click', (e) => {
        const go = e.target.closest('[data-go]')?.dataset.go;
        if (go) show(Number(input.value) + (go === 'prev' ? -1 : 1));
    });
    input.addEventListener('change', () => show(Number(input.value)));
    show(1);

    const stage = document.getElementById('check-stage');
    const open = (on) => { stage.hidden = !on; document.body.style.overflow = on ? 'hidden' : ''; };
    document.getElementById('check-open').addEventListener('click', () => open(true));
    document.getElementById('check-close').addEventListener('click', () => open(false));
    document.addEventListener('keydown', (e) => {
        if (stage.hidden) return;
        if (e.key === 'Escape') open(false);
        if (e.target !== input && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) show(current + (e.key === 'ArrowLeft' ? -1 : 1));
    });
})();
