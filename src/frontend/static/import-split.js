// The cuts between the leaflets of a volume: a page grid on the left, two neighbouring pages large on the right.
(() => {
    const data = JSON.parse(document.getElementById('split-data').textContent);
    const $ = (id) => document.getElementById(id);
    const [stage, left, right, nav, decide, finish, outside] = ['split-stage', 'split-left', 'split-right', 'split-nav', 'split-decide', 'split-finish', 'split-finish-page'].map($);
    const errors = document.querySelectorAll('.split-error');
    const cuts = new Set(data.cuts);
    const excluded = new Set(data.excluded);
    const suggested = new Set(data.suggested);
    const reviewed = new Set(data.reviewed);
    const hints = new Set(data.hints);
    const transitions = data.pages - 1;
    let dirty = false;
    const undo = [], redo = [];
    let current = 0, shown = 0, note = '';

    right.innerHTML = '<div class="split-pair"></div>';
    const pair = right.firstChild;
    const join = document.createElement('div'), sheets = new Map();
    const at = () => Math.max(1, Math.min(current || 1, transitions));

    const forced = (page) => page < data.pages && excluded.has(page) !== excluded.has(page + 1);
    const segments = () => {
        const result = [];
        for (let page = 1; page <= data.pages; page++) {
            if (page === 1 || cuts.has(page - 1) || forced(page - 1)) result.push([page, page]);
            else result[result.length - 1][1] = page;
        }
        return result;
    };

    left.innerHTML = '<div class="split-grid">' + Array.from({ length: data.pages }, (_, i) => {
        const page = i + 1;
        return `<figure class="split-page" data-page="${page}">
            <img loading="lazy" alt="Seite ${page}" title="Seite ${page}" src="${data.thumb.replace('{n}', page)}">
            <figcaption><span class="split-num">${page}</span></figcaption>
            ${page < data.pages ? `<button type="button" class="split-cut" data-cut="${page}">✂</button>` : ''}</figure>`;
    }).join('') + '</div>';
    const cells = [...left.querySelectorAll('.split-page')];

    const render = () => {
        let leaflet = 0;
        cells.forEach((cell, i) => {
            const page = i + 1, out = excluded.has(page), starts = page === 1 || cuts.has(page - 1) || forced(page - 1);
            if (starts && !out) leaflet++;
            if (out) cell.removeAttribute('data-group'); else cell.dataset.group = leaflet % 2;
            cell.classList.toggle('excluded', out);
            const cut = cell.querySelector('.split-cut');
            if (!cut) return;
            const on = cuts.has(page) && !forced(page), hint = hints.has(page) && !on;
            const checked = !on && !hint && !suggested.has(page) && reviewed.has(page), open = !decided(page);
            cut.className = `split-cut${on || forced(page) ? ' on' : ''}${(on && suggested.has(page)) || hint ? ' suggested' : ''}${checked ? ' checked' : ''}${open ? ' open' : ''}`;
            cut.title = cut.ariaLabel = forced(page) ? 'Getrennt wegen „Leerseite / Trennblatt“' : `Trennung nach Seite ${page} ${on ? 'entfernen' : 'setzen'}`;
            cut.disabled = forced(page);
        });
        cells.forEach((cell, i) => {  // the colour of the next leaflet starts at the cut line, not at the next page
            const next = cells[i + 1];
            if (next && next.dataset.group !== cell.dataset.group) cell.dataset.after = next.dataset.group ?? 'x';
            else delete cell.dataset.after;
        });
        paint();
        document.querySelectorAll('.split-count').forEach((e) => {
            e.classList.toggle('done', data.confirmed && !dirty);
            e.textContent = `${leaflet} ${leaflet === 1 ? 'Flugblatt' : 'Flugblätter'} · ${data.confirmed && !dirty ? 'Einteilung abgeschlossen' : complete() && !dirty ? 'alle Übergänge geprüft' : `${all.filter(decided).length} von ${transitions} Übergängen geprüft`}${hints.size ? ` · ${hints.size} ${hints.size === 1 ? 'mögliche fehlende Trennung' : 'mögliche fehlende Trennungen'}` : ''}${
                dirty ? ' · speichert …' : data.confirmed ? '' : data.saved ? '' : ' · noch nicht gesetzt'}`;
        });
        finish.hidden = complete() && !dirty && data.confirmed;
        const ready = complete() && !dirty && !data.confirmed;  // everything decided, only the click is missing
        outside.hidden = !ready;
        $('split-open').classList.toggle('primary', !ready && !data.confirmed);
        const missing = all.filter((a) => !decided(a)).length;
        finish.textContent = missing ? `Noch ${missing} offen →` : 'Einteilung abschließen';
        finish.title = missing ? `Zum Abschließen fehlen noch ${missing} Übergänge${suggested.size + hints.size ? ` (davon ${suggested.size + hints.size} Trennvorschläge)` : ''}. Ein Klick springt zum nächsten.` : 'Alle Übergänge sind geprüft: Einteilung übernehmen und zur Übersicht';
        renderView();
    };
    const decided = (a) => forced(a) || (excluded.has(a) && excluded.has(a + 1)) || (!suggested.has(a) && !hints.has(a) && (cuts.has(a) || reviewed.has(a)));
    const all = Array.from({ length: transitions }, (_, i) => i + 1);
    const complete = () => all.every(decided);
    const kind = (a) => forced(a) ? ['on', 'Leerseite'] : suggested.has(a) ? ['suggested', 'Trennung vorgeschlagen'] : hints.has(a) ? ['suggested', 'Trennung fehlt vielleicht']
        : cuts.has(a) ? ['on', 'getrennt'] : reviewed.has(a) ? ['', 'gehören zusammen'] : ['', ''];
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    const renderView = (direction = 0) => {
        const a = at(), [style, text] = kind(a);
        if (shown !== a) {
            const sheet = (p) => {
                if (!sheets.has(p)) {
                    const figure = document.createElement('figure');
                    figure.className = 'split-sheet';
                    figure.innerHTML = `<img alt="Seite ${p}" src="${data.large.replace('{n}', p)}"><figcaption><b>Seite ${p}</b><button type="button" class="split-skip" data-out="${p}"></button></figcaption>`;
                    sheets.set(p, figure);
                }
                return sheets.get(p);
            };
            pair.replaceChildren(...(transitions < 1 ? [sheet(1)] : [sheet(a), join, sheet(a + 1)]));
            [a - 1, a + 2].filter((p) => p >= 1 && p <= data.pages).forEach(sheet);
            sheets.forEach((_, p) => { if (Math.abs(p - a) > 3) sheets.delete(p); });
            shown = a;
            if (Math.abs(direction) === 1 && !reduced.matches) {
                pair.classList.remove('from-right', 'from-left');
                void pair.offsetWidth;
                pair.classList.add(direction > 0 ? 'from-right' : 'from-left');
            }
        }
        pair.classList.toggle('together', reviewed.has(a) && !cuts.has(a) && !suggested.has(a) && !hints.has(a) && !forced(a));
        join.className = `split-join ${style}`;
        pair.querySelectorAll('.split-sheet').forEach((f, i) => {
            const out = excluded.has(a + i), skip = f.querySelector('.split-skip');
            f.classList.toggle('excluded', out);
            skip.setAttribute('aria-pressed', out);
            skip.innerHTML = `${out ? 'Wieder einbeziehen' : 'Leerseite / Trennblatt'} <kbd>${i ? 'Shift+L' : 'L'}</kbd>`;
            skip.title = (out ? `Seite ${a + i} wieder einbeziehen` : `Seite ${a + i} ist eine Leerseite oder ein Trennblatt: gehört zu keinem Flugblatt, wird nicht gezählt`) + ` (Taste ${i ? 'Shift+L' : 'L'})`;
        });
        nav.innerHTML = transitions < 1 ? '' : `<button type="button" class="button" data-act="prev" title="Voriger Übergang (←)"${a < 2 ? ' disabled' : ''}><kbd>←</kbd> Zurück</button>
            <b class="${note ? '' : style}">${note || text}</b>
            <button type="button" class="button" data-act="next" title="Nächster Übergang (→)"${current >= data.pages ? ' disabled' : ''}>Weiter <kbd>→</kbd></button>`;
        decide.innerHTML = transitions < 1 ? '' : `<p class="split-question">Zwischen Seite ${a} und ${a + 1} trennen?</p>
            <div class="split-buttons"><button type="button" class="button" data-act="cut" aria-pressed="${!suggested.has(a) && cuts.has(a) && !forced(a)}"${forced(a) ? ' disabled' : ''}>Ja, trennen <kbd>T</kbd></button>
            <button type="button" class="button" data-act="keep" aria-pressed="${!suggested.has(a) && !hints.has(a) && !cuts.has(a) && reviewed.has(a)}"${forced(a) ? ' disabled' : ''}>Nein, gehören zusammen <kbd>Z</kbd></button></div>`;
        $('split-undo').disabled = !undo.length;
        $('split-redo').disabled = !redo.length;
    };
    const sets = [cuts, excluded, suggested, reviewed, hints];
    const sorted = (set) => [...set].sort((a, b) => a - b);
    const snapshot = () => JSON.stringify([...sets.map(sorted), at()]);
    const change = (edit) => {
        undo.push(snapshot());
        redo.length = 0;
        edit();
        touch();
        render();
    };
    const travel = (from, to) => {
        if (!from.length) return;
        to.push(snapshot());
        const list = JSON.parse(from.pop()), page = list.pop();
        list.forEach((items, i) => { sets[i].clear(); items.forEach((x) => sets[i].add(x)); });
        touch();
        render();
        go(page);
    };
    const choose = (page, cut) => change(() => {
        suggested.delete(page);
        hints.delete(page);
        if (cut) { cuts.add(page); reviewed.delete(page); } else { cuts.delete(page); reviewed.add(page); }
    });
    const toggleCut = (page) => choose(page, !cuts.has(page));
    const decideAt = (cut) => {
        const a = at();
        choose(a, cut);
        if (a >= transitions) return;
        const next = all.slice(a).find((x) => !decided(x)) || a + 1;
        const skipped = next - a - 1;
        go(next, true, skipped ? `${skipped} bereits entschiedene${skipped === 1 ? 'r Übergang' : ' Übergänge'} übersprungen` : '');
    };
    const nextOpen = () => {
        const a = at(), open = [...all.slice(a), ...all.slice(0, a - 1)].find((x) => !decided(x));
        if (open) go(open);
    };
    const pass = (page) => {
        if (decided(page) || suggested.has(page) || hints.has(page)) return;
        reviewed.add(page);
        touch();
    };
    const act = (e) => {
        const what = e.target.closest('[data-act]')?.dataset.act;
        if (what === 'cut' || what === 'keep') decideAt(what === 'cut');
        else if (what === 'undo') travel(undo, redo);
        else if (what === 'redo') travel(redo, undo);
        else if (what === 'prev') go(at() - 1);
        else if (what === 'next') forward();
    };
    stage.addEventListener('click', act);

    left.addEventListener('click', (e) => {
        const cut = e.target.closest('[data-cut]');
        if (cut) return toggleCut(Number(cut.dataset.cut));
        const thumb = e.target.closest('.split-page');
        if (thumb) go(Number(thumb.dataset.page));
    });

    right.addEventListener('click', (e) => {
        const skip = e.target.closest('[data-out]');
        if (skip) leaveOut(Number(skip.dataset.out));
    });
    const leaveOut = (page) => {
        const marking = !excluded.has(page);
        change(() => {
            marking ? excluded.add(page) : excluded.delete(page);
            [page - 1, page].filter((c) => c > 0 && c < data.pages).forEach((c) => { cuts.add(c); suggested.delete(c); hints.delete(c); });
        });
        if (marking && page < data.pages) go(all.slice(page).find((x) => !decided(x)) || page + 1, true);  // on to the next open transition
    };

    const paint = () => {
        left.querySelectorAll('.current, .next').forEach((e) => e.classList.remove('current', 'next', 'joined'));
        const [a, b] = [at(), at() + 1].map((page) => left.querySelector(`[data-page="${page}"]`));
        a?.classList.add('current');
        b?.classList.add('next');
        if (a && b && a.offsetTop === b.offsetTop) { a.classList.add('joined'); b.classList.add('joined'); }
    };
    const go = (page, slide = false, remark = '') => {
        const before = at();
        note = remark;
        current = Math.min(data.pages, Math.max(1, page));
        paint();
        const [first, second] = [at(), at() + 1].map((n) => left.querySelector(`[data-page="${n}"]`));
        const box = left.getBoundingClientRect(), top = first.getBoundingClientRect().top, bottom = (second || first).getBoundingClientRect().bottom;
        if (top < box.top || bottom > box.bottom) left.scrollBy({ top: (top + bottom - box.top - box.bottom) / 2, behavior: reduced.matches ? 'auto' : 'smooth' });
        const moved = at() - before;
        renderView(Math.abs(moved) === 1 || slide ? Math.sign(moved) : 0);
    };
    const forward = () => { pass(at()); go(current + 1); render(); };

    const fail = (message) => errors.forEach((e) => { e.hidden = false; e.textContent = message; });
    const post = async (url, body) => {
        errors.forEach((e) => { e.hidden = true; });
        const response = await fetch(url, { method: 'POST', body: body instanceof FormData ? body : JSON.stringify(body),
            headers: body instanceof FormData ? {} : { 'Content-Type': 'application/json' } });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Das hat nicht geklappt.');
        return result;
    };
    const saved = async (url, body) => {
        clearTimeout(timer);
        await queue;
        try { await post(url, body); dirty = false; location.reload(); } catch (e) { fail(e.message); }
    };

    const body = (done) => ({ cuts: sorted(cuts), excluded: sorted(excluded), suggested: sorted(suggested), reviewed: sorted(reviewed), hints: sorted(hints), finish: done && complete() });
    // one save at a time: parallel ones could arrive out of order and an older state would win
    let timer = null, changed = false, version = 0, queue = Promise.resolve();
    const store = async (finishing) => {
        if (!dirty && !finishing) return;
        const stored = body(finishing || data.confirmed), sent = version;
        try {
            await post(data.saveUrl, stored);
            data.saved = changed = true;
            if (version === sent) { dirty = false; data.confirmed = stored.finish; }
        } catch (e) { fail(e.message); }
        render();
    };
    const flush = (finishing = false) => { clearTimeout(timer); return (queue = queue.then(() => store(finishing))); };
    const touch = () => { dirty = true; version += 1; data.confirmed = false; clearTimeout(timer); timer = setTimeout(flush, 600); };
    finish.addEventListener('click', async () => {
        if (!complete()) return nextOpen();
        await flush(true);
        if (data.confirmed) location.reload();  // done: back to the step, where "Weiter" is free now
    });
    $('split-clear').addEventListener('click', () => {
        if (!confirm('Alle Trennungen, Leerseiten und Entscheidungen löschen und von vorn beginnen?')) return;
        saved(data.saveUrl, { cuts: [], excluded: [], suggested: [], reviewed: [], hints: [], finish: false });
    });
    outside.addEventListener('click', async () => { await flush(true); if (data.confirmed) location.reload(); });
    $('split-suggest-text').addEventListener('click', () => {
        if ((data.saved || cuts.size) && !confirm('Vorschlag übernehmen? Die vorhandenen Trennungen werden ersetzt.')) return;
        saved(data.textUrl, {});
    });

    $('split-list').addEventListener('change', async (e) => {
        const file = e.target.files[0];
        e.target.value = '';
        if (!file || ((data.saved || cuts.size) && !confirm('Liste laden? Die vorhandenen Trennungen werden ersetzt.'))) return;
        const form = new FormData();
        form.append('liste', file);
        try {
            const result = await post(data.listUrl, form);
            change(() => {
                suggested.clear();
                [[cuts, result.cuts], [excluded, result.excluded]].forEach(([set, list]) => { set.clear(); list.forEach((x) => set.add(x)); });
                hints.clear();
                (result.hints || []).forEach((a) => hints.add(a));
                reviewed.clear();
                all.filter((a) => !cuts.has(a) && !hints.has(a)).forEach((a) => reviewed.add(a));
            });
            const leaflets = segments().filter(([first]) => !excluded.has(first)).length;
            try {
                sessionStorage.setItem('split-note', result.hints === null ? 'Liste übernommen. Zusätzliche Hinweise sind erst nach der Texterkennung verfügbar.'
                    : `${leaflets} Flugblätter aus der Liste übernommen${hints.size ? ` · ${hints.size} ${hints.size === 1 ? 'mögliche fehlende Trennung' : 'mögliche fehlende Trennungen'} bitte prüfen` : ''}.`);
            } catch (x) { /* no storage */ }
            saved(data.saveUrl, body(false));
        } catch (e) { fail(e.message); }
    });
    $('split-download').addEventListener('click', () => {
        const lines = segments().map(([first, last]) => `${excluded.has(first) ? 'x ' : ''}${first === last ? first : `${first}-${last}`}`);
        const link = document.createElement('a');
        link.href = URL.createObjectURL(new Blob([`# ${data.name}: ein Flugblatt pro Zeile, Seiten von-bis; "x" davor lässt Seiten aus\n${lines.join('\n')}\n`],
            { type: 'text/plain;charset=utf-8' }));
        link.download = `${data.name}-flugblaetter.txt`;
        link.click();
        URL.revokeObjectURL(link.href);
    });

    try {
        const remark = sessionStorage.getItem('split-note');
        sessionStorage.removeItem('split-note');
        if (remark) document.querySelectorAll('.split-note').forEach((e) => { e.hidden = false; e.textContent = remark; });
    } catch (e) { /* no storage */ }

    const layout = left.parentElement, resizer = $('split-resizer');
    try { const width = localStorage.getItem('import-split-left'); if (width) layout.style.setProperty('--split-left', `${width}px`); } catch (e) { /* no storage */ }
    resizer.addEventListener('pointerdown', (e) => {
        e.preventDefault();
        const move = (m) => layout.style.setProperty('--split-left', `${Math.min(Math.max(m.clientX - layout.getBoundingClientRect().left, 240), layout.clientWidth - 320)}px`);
        addEventListener('pointermove', move);
        addEventListener('pointerup', () => {
            removeEventListener('pointermove', move);
            try { localStorage.setItem('import-split-left', parseInt(getComputedStyle(left).width, 10)); } catch (x) { /* no storage */ }
        }, { once: true });
    });
    resizer.addEventListener('dblclick', () => {
        layout.style.removeProperty('--split-left');
        try { localStorage.removeItem('import-split-left'); } catch (e) { /* no storage */ }
    });

    const open = (on) => { if (!on && changed) return location.reload(); document.activeElement.blur(); stage.hidden = !on; if (on && !current) go(1); document.body.classList.toggle('split-lock', on); };
    $('split-open').addEventListener('click', () => open(true));
    $('split-close').addEventListener('click', () => open(false));
    addEventListener('keydown', (e) => {
        if (e.key === 'Escape') return open(false);
        if (stage.hidden || e.altKey || e.target.closest('input')) return;
        const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
        const page = at();
        if (e.ctrlKey || e.metaKey) {
            const key = e.key.toLowerCase();
            if (key === 's') flush();
            if (key === 'z') travel(...(e.shiftKey ? [redo, undo] : [undo, redo]));
            if (key === 'y') travel(redo, undo);
            if ('szy'.includes(key)) e.preventDefault();
        } else if (step) {
            e.preventDefault();
            if (step > 0) forward(); else go(page - 1);
        } else if (e.key.toLowerCase() === 'u') {
            travel(undo, redo);
        } else if (e.key.toLowerCase() === 'l') {
            e.preventDefault();
            leaveOut(Math.min(page + (e.shiftKey ? 1 : 0), data.pages));  // L the left page, Shift+L the right one
        } else if (['t', 's', 'z', 'n'].includes(e.key.toLowerCase()) || (e.key === 'Enter' && !e.target.closest('.split-bar, .split-decide button'))) {
            e.preventDefault();
            if (transitions > 0 && !forced(page)) decideAt(!'zn'.includes(e.key.toLowerCase()));  // left hand splits, right hand keeps
        }
    });
    addEventListener('beforeunload', (e) => { if (dirty) e.preventDefault(); });
    render();
})();
