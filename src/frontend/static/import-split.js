// The cuts between the leaflets of a volume: one cell per page, a scissors button at its right edge.
// A page can also be left out of every leaflet (blank sheet, separator): it then forms a segment of its own.
(() => {
    const data = JSON.parse(document.getElementById('split-data').textContent);
    const grid = document.getElementById('split-grid');
    const count = document.getElementById('split-count');
    const error = document.getElementById('split-error');
    const save = document.getElementById('split-save');
    const suggest = document.getElementById('split-suggest');
    const progress = document.getElementById('split-progress');
    const pagesEl = document.getElementById('split-pages');
    const left = document.getElementById('split-left');
    const right = document.getElementById('split-right');
    const cuts = new Set(data.cuts);
    const excluded = new Set(data.excluded);
    let unsaved = !data.saved;  // a volume without a file starts as one leaflet that nobody has looked at
    const cells = [];
    const sheets = [];
    let current = 0;

    // keeps an element inside its own scrolling pane, without moving the page or the other pane
    const keepVisible = (pane, element) => {
        const top = element.offsetTop - pane.offsetTop, bottom = top + element.offsetHeight;
        if (top < pane.scrollTop) pane.scrollTop = top - 8;
        else if (bottom > pane.scrollTop + pane.clientHeight) pane.scrollTop = bottom - pane.clientHeight + 8;
    };
    const show = (page) => right.scrollTo({ top: sheets[page - 1].offsetTop - pagesEl.offsetTop - 8, behavior: 'instant' });
    const toggleExcluded = (page) => {
        if (excluded.has(page)) excluded.delete(page); else excluded.add(page);
        unsaved = true;
        update();
    };
    const skipButton = (page, text) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'split-skip';
        button.dataset.text = text;
        button.addEventListener('click', (event) => { event.stopPropagation(); toggleExcluded(page); });
        return button;
    };

    for (let page = 1; page <= data.pages; page++) {
        const cell = document.createElement('figure');
        cell.className = 'split-page';
        const img = document.createElement('img');
        img.loading = 'lazy';
        img.alt = `Seite ${page}`;
        img.src = data.thumb.replace('{n}', page);
        img.addEventListener('click', () => show(page));
        const label = document.createElement('figcaption');
        const badge = document.createElement('span');
        badge.className = 'split-badge';
        label.append(`S. ${page}`, badge);
        cell.append(img, label, cell.skip = skipButton(page, 'ausschließen'));
        if (page < data.pages) {
            const cut = document.createElement('button');
            cut.type = 'button';
            cut.className = 'split-cut';
            cut.textContent = '✂';
            cut.addEventListener('click', () => {
                if (cuts.has(page)) cuts.delete(page); else cuts.add(page);
                unsaved = true;
                update();
            });
            cell.append(cut);
            cell.cut = cut;
        }
        grid.append(cell);
        cells.push(cell);

        // the same page large, on the right
        const sheet = document.createElement('figure');
        sheet.className = 'split-sheet';
        const big = document.createElement('img');
        big.loading = 'lazy';
        big.alt = `Seite ${page}`;
        big.src = data.large.replace('{n}', page);
        const caption = document.createElement('figcaption');
        const name = document.createElement('span');
        name.append(`Seite ${page} `);
        const mark = document.createElement('span');
        mark.className = 'split-badge';
        name.append(mark);
        caption.append(name, sheet.skip = skipButton(page, 'Seite ausschließen'));
        sheet.append(big, caption);
        pagesEl.append(sheet);
        sheets.push(sheet);
    }

    // the page being read on the right is marked on the left
    let waiting = false;
    right.addEventListener('scroll', () => {
        if (waiting) return;
        waiting = true;
        requestAnimationFrame(() => {
            waiting = false;
            const line = right.scrollTop + right.clientHeight / 3;
            let page = sheets.findIndex((s) => s.offsetTop - pagesEl.offsetTop + s.offsetHeight > line);
            page = page < 0 ? sheets.length : page + 1;
            if (page === current) return;
            if (current) cells[current - 1].classList.remove('current');
            current = page;
            cells[page - 1].classList.add('current');
            keepVisible(left, cells[page - 1]);
        });
    });

    // a left-out page is cut off from the leaflets next to it
    const forced = (page) => page < data.pages && excluded.has(page) !== excluded.has(page + 1);
    const cutAfter = (page) => cuts.has(page) || forced(page);
    // the segments in order: [first, last, left out]
    const segments = () => {
        const result = [];
        for (let page = 1; page <= data.pages; page++) {
            if (page === 1 || cutAfter(page - 1)) result.push([page, page, excluded.has(page)]);
            else result[result.length - 1][1] = page;
        }
        return result;
    };

    function update() {
        let leaflet = 0;
        cells.forEach((cell, i) => {
            const page = i + 1;
            const starts = page === 1 || cutAfter(page - 1);
            const out = excluded.has(page);
            if (starts && !out) leaflet++;
            const text = !out && starts ? `Blatt ${leaflet}` : '';  // a left-out page is only dimmed
            cell.classList.toggle('tone-1', !out && leaflet % 2 === 0);
            cell.classList.toggle('split-start', starts && !out);
            cell.classList.toggle('excluded', out);
            sheets[i].classList.toggle('split-start', starts && !out);
            sheets[i].classList.toggle('excluded', out);
            cell.querySelector('.split-badge').textContent = text;
            sheets[i].querySelector('.split-badge').textContent = text;
            for (const holder of [cell, sheets[i]]) {
                const skip = holder.skip;
                skip.textContent = out ? 'einbeziehen' : skip.dataset.text;
                skip.title = out ? `Seite ${page} wieder einbeziehen` : `Seite ${page} ausschließen: weder Teil eines Flugblatts noch gezählt`;
                skip.setAttribute('aria-pressed', out);
            }
            if (cell.cut) {
                const on = cuts.has(page) && !forced(page);  // a cut that a left-out page forces is not shown as one
                cell.cut.classList.toggle('on', on);
                cell.cut.classList.toggle('forced', forced(page));
                cell.cut.disabled = forced(page);
                cell.cut.setAttribute('aria-pressed', on);
                cell.cut.title = forced(page) ? 'Schnitt wegen der ausgeschlossenen Seite'
                    : on ? `Schnitt nach Seite ${page} entfernen` : `Schnitt nach Seite ${page} setzen`;
                cell.cut.setAttribute('aria-label', cell.cut.title);
            }
        });
        const skipped = excluded.size ? ` · ${excluded.size} ausgeschlossen` : '';
        count.textContent = `${leaflet} ${leaflet === 1 ? 'Flugblatt' : 'Flugblätter'}${skipped}${unsaved ? ' · nicht gespeichert' : ''}`;
        const saved = document.querySelector('.split-info .form-ok');
        if (saved) saved.hidden = unsaved;  // "gespeichert" is only true until the next change
        save.disabled = !unsaved;
    }

    const fail = (message) => { error.hidden = false; error.textContent = message; };
    const post = async (url, body) => {
        const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Das hat nicht geklappt.');
        return result;
    };
    const sorted = (set) => [...set].sort((a, b) => a - b);

    save.addEventListener('click', async () => {
        error.hidden = true;
        try {
            await post(data.saveUrl, { cuts: sorted(cuts), excluded: sorted(excluded) });
            unsaved = false;
            location.reload();  // shows the saved state
        } catch (e) { fail(e.message); }
    });

    const poll = async () => {
        progress.hidden = false;
        suggest.disabled = true;
        try {
            const job = await (await fetch(data.statusUrl)).json();
            if (job.state === 'done') { unsaved = false; location.reload(); return; }
            if (job.state === 'error') { progress.hidden = true; suggest.disabled = false; fail(job.error); return; }
            const m = Math.floor((job.seconds || 0) / 60), s = String((job.seconds || 0) % 60).padStart(2, '0');
            progress.querySelector('.upload-text').textContent = `Datalab schlägt die Schnitte vor … ${m}:${s} Minuten`;
        } catch (e) { /* app restarting: try again */ }
        setTimeout(poll, 2000);
    };

    suggest.addEventListener('click', async () => {
        if ((data.saved || cuts.size) && !confirm('Der Vorschlag ersetzt die vorhandenen Schnitte. Fortfahren?')) return;
        if (!confirm(`Datalab ist ein kostenpflichtiger Dienst. Es werden ${data.pages} Seiten übertragen. Fortfahren?`)) return;
        error.hidden = true;
        try { await post(data.suggestUrl, {}); poll(); } catch (e) { fail(e.message); }
    });

    // a list kept while scanning: one leaflet per line, its pages "5-7" or "9"; "x 17" leaves a page out
    document.getElementById('split-list').addEventListener('change', async (event) => {
        const file = event.target.files[0];
        event.target.value = '';
        if (!file) return;
        error.hidden = true;
        const body = new FormData();
        body.append('liste', file);
        try {
            const response = await fetch(data.listUrl, { method: 'POST', body });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || 'Die Liste konnte nicht gelesen werden.');
            cuts.clear();
            result.cuts.forEach((c) => cuts.add(c));
            excluded.clear();
            result.excluded.forEach((p) => excluded.add(p));
            unsaved = true;
            update();
        } catch (e) { fail(e.message); }
    });

    document.getElementById('split-download').addEventListener('click', () => {
        const lines = segments().map(([first, last, out]) => `${out ? 'x ' : ''}${first === last ? first : `${first}-${last}`}`);
        const text = `# ${data.name}: ein Flugblatt pro Zeile, Seiten von-bis; "x" davor lässt Seiten aus\n${lines.join('\n')}\n`;
        const link = document.createElement('a');
        link.href = URL.createObjectURL(new Blob([text], { type: 'text/plain;charset=utf-8' }));
        link.download = `${data.name}-flugblaetter.txt`;
        link.click();
        URL.revokeObjectURL(link.href);
    });

    window.addEventListener('beforeunload', (e) => { if (unsaved && cells.length) { e.preventDefault(); } });

    // the divider between the two panes: dragged with the pointer, remembered per browser
    const layout = document.querySelector('.split-layout');
    const resizer = document.getElementById('split-resizer');
    const setLeft = (px) => {
        const width = layout.getBoundingClientRect().width;
        layout.style.setProperty('--split-left', `${Math.min(Math.max(px, 240), width - 320)}px`);
    };
    try { const saved = localStorage.getItem('import-split-left'); if (saved) setLeft(Number(saved)); } catch (e) { /* no storage */ }
    resizer.addEventListener('pointerdown', (event) => {
        resizer.setPointerCapture(event.pointerId);
        resizer.classList.add('dragging');
        const move = (e) => setLeft(e.clientX - layout.getBoundingClientRect().left);
        const stop = () => {
            resizer.classList.remove('dragging');
            resizer.removeEventListener('pointermove', move);
            resizer.removeEventListener('pointerup', stop);
            try { localStorage.setItem('import-split-left', parseInt(getComputedStyle(left).width, 10)); } catch (e) { /* no storage */ }
        };
        resizer.addEventListener('pointermove', move);
        resizer.addEventListener('pointerup', stop);
    });
    resizer.addEventListener('dblclick', () => {
        layout.style.removeProperty('--split-left');
        try { localStorage.removeItem('import-split-left'); } catch (e) { /* no storage */ }
    });

    // the controls and both panes can fill the browser window; a clear button and Esc bring them back
    const stage = document.getElementById('split-stage');
    const maximize = document.getElementById('split-fullscreen');
    const setMaximized = (on) => {
        stage.classList.toggle('maximized', on);
        document.body.classList.toggle('split-lock', on);
        maximize.setAttribute('aria-pressed', on);
        maximize.textContent = on ? '✕ Vollbild beenden (Esc)' : '⛶ Vollbild';
        maximize.classList.toggle('exit', on);
        if (current) keepVisible(left, cells[current - 1]);
    };
    maximize.addEventListener('click', () => setMaximized(!stage.classList.contains('maximized')));
    addEventListener('keydown', (e) => { if (e.key === 'Escape' && stage.classList.contains('maximized')) setMaximized(false); });
    update();
    if (data.suggesting) poll();
})();
