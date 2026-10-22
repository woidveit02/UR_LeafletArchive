// Upload of the scans with a progress bar: first the transfer to the app, then the building of the PDF,
// which runs in the background and is polled. Without this script the form is a plain post.
(() => {
    // a new volume: the link of the chosen unit in the findmittel, to be overwritten if needed
    const unit = document.getElementById('vz'), portal = document.getElementById('portal_url');
    if (unit && portal) unit.addEventListener('change', () => { portal.value = unit.selectedOptions[0].dataset.portal; });

    // the browser's own file button speaks the browser's language: a German label and the chosen names instead
    document.querySelectorAll('.file-pick input').forEach((input) => {
        const name = input.parentElement.querySelector('.file-name');
        if (!name) return;
        const load = input.required && input.form?.querySelector('button[type="submit"]');  // a form that only needs this file
        input.addEventListener('change', () => {
            const n = input.files.length;
            if (load) load.disabled = n === 0;
            name.textContent = n === 0 ? 'Nichts ausgewählt' : n === 1 ? input.files[0].name : `${n} Dateien ausgewählt`;
        });
    });

    const form = document.querySelector('form[data-status-url]:not([data-job])');
    if (!form) return;
    const box = document.getElementById('upload-progress');
    const bar = box.querySelector('progress');
    const text = box.querySelector('.upload-text');
    const error = document.getElementById('upload-error');
    const button = document.getElementById('upload-button');

    // what is chosen decides the button: a choice is not uploaded yet, which the page says in plain words
    const zone = document.getElementById('drop-zone');
    const summary = document.getElementById('pick-summary');
    const pdf = document.getElementById('pdf');
    const tiffs = document.getElementById('tiffs');
    const folder = document.getElementById('folder');
    const inputs = [pdf, tiffs, folder];  // one way at a time: choosing in one empties the others
    const replaceNote = document.getElementById('replace-note');
    let uploading = false;
    // the app sorts by path with numbers by value (15.2 before 15.10); the page shows that order before the upload
    const dropped = new Map();  // a dropped file does not know its folder, its entry does
    const rel = (f) => dropped.get(f) || f.webkitRelativePath || f.name;
    const key = (f) => rel(f).split(/(\d+)/).map((t, i) => (i % 2 ? Number(t) : t.toLowerCase()));
    const before = (a, b) => { const [x, y] = [key(a), key(b)]; for (let i = 0; i < Math.min(x.length, y.length); i++) if (x[i] !== y[i]) return x[i] < y[i] ? -1 : 1; return x.length - y.length; };
    const kind = (f) => (/\.pdf$/i.test(f.name) ? 'pdf' : /\.tiff?$/i.test(f.name) ? 'tiff' : '');
    const chosen = () => inputs.flatMap((input) => [...input.files]);
    const scans = () => chosen().filter(kind).sort(before);
    const mixed = () => new Set(scans().map(kind)).size > 1;
    const pending = () => !uploading && chosen().length > 0;
    const size = (bytes) => bytes >= 1e9 ? `${(bytes / 1e9).toFixed(1).replace('.', ',')} GB` : `${Math.max(1, Math.round(bytes / 1e6))} MB`;
    const describe = () => {
        const list = scans(), total = list.reduce((sum, f) => sum + f.size, 0), pdfs = list.filter((f) => kind(f) === 'pdf').length;
        const what = list.length === 1 ? rel(list[0]) : pdfs === list.length ? `${pdfs} PDFs` : `${list.length} TIFF-Scans`;
        const skipped = chosen().length - list.length;
        return `${what} · ${size(total)}${skipped ? ` · ${skipped === 1 ? '1 andere Datei wird' : `${skipped} andere Dateien werden`} übergangen` : ''}`;
    };
    const order = () => {  // the folders in their order, or the PDFs if there are few
        const list = scans(), folders = [];
        list.forEach((f) => {
            const dir = rel(f).split('/').slice(0, -1).join('/');
            if (folders.length && folders.at(-1)[0] === dir) folders.at(-1)[1] += 1; else folders.push([dir, 1]);
        });
        if (folders.length > 1) return `Reihenfolge: ${folders.map(([dir, n]) => `${dir.split('/').at(-1) || 'oben'} (${n})`).join(' → ')}`;
        if (list.length > 1 && list.length <= 12 && kind(list[0]) === 'pdf') return `Reihenfolge: ${list.map((f) => f.name).join(' → ')}`;
        return '';
    };
    const clear = () => { inputs.forEach((input) => { input.value = ''; }); refresh(); };
    const refresh = () => {
        const n = chosen().length;
        button.disabled = n === 0 || mixed() || !scans().length;
        zone.classList.toggle('has-files', n > 0);
        if (replaceNote) replaceNote.hidden = n === 0;
        summary.replaceChildren();
        if (!n) { summary.textContent = 'Nichts ausgewählt'; return; }
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'button text';
        remove.textContent = 'Entfernen';
        remove.addEventListener('click', clear);
        if (!scans().length) summary.append('Keine PDF- oder TIFF-Dateien ausgewählt · ', remove);
        else if (mixed()) summary.append('PDFs und TIFF-Scans gemischt: bitte nur eine Art hochladen · ', remove);
        else summary.append(describe(), ' · ', remove);
        const sequence = order();
        if (sequence && !mixed()) { const line = document.createElement('span'); line.className = 'pick-order'; line.textContent = sequence; summary.append(line); }
    };
    // leaving with a choice that was not uploaded would drop it silently
    document.querySelector('.step-head')?.addEventListener('click', (e) => {
        const link = e.target.closest('a');
        if (link && pending() && !confirm('Ohne Hochladen weitergehen? Die ausgewählten Scans sind noch nicht hochgeladen.')) e.preventDefault();
    });
    inputs.forEach((input) => input.addEventListener('change', () => {
        dropped.clear();
        inputs.filter((other) => other !== input).forEach((other) => { other.value = ''; });
        refresh();
    }));

    // a dropped folder arrives as an entry that is read recursively
    const filesOf = (entry) => new Promise((resolve) => {
        if (entry.isFile) { entry.file((f) => { dropped.set(f, entry.fullPath.replace(/^\//, '')); resolve([f]); }, () => resolve([])); return; }
        const reader = entry.createReader(), found = [];
        const next = () => reader.readEntries(async (batch) => {
            if (!batch.length) { resolve((await Promise.all(found.map(filesOf))).flat()); return; }
            found.push(...batch);
            next();
        }, () => resolve([]));
        next();
    });
    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('over'));
    zone.addEventListener('drop', async (e) => {
        e.preventDefault();
        zone.classList.remove('over');
        // read both before the first await: the browser empties the drop afterwards
        const entries = [...e.dataTransfer.items].map((i) => i.webkitGetAsEntry && i.webkitGetAsEntry()).filter(Boolean);
        const direct = [...e.dataTransfer.files];
        clear();
        const found = entries.some((entry) => entry.isDirectory) ? (await Promise.all(entries.map(filesOf))).flat() : direct;
        const list = new DataTransfer();
        found.forEach((f) => list.items.add(f));
        const target = found.length && found.every((f) => kind(f) === 'pdf') ? pdf : tiffs;
        target.files = list.files;
        // the input hands out new File objects: carry the folder names over
        const paths = found.map(rel);
        dropped.clear();
        [...target.files].forEach((f, i) => { if (paths[i] !== f.name) dropped.set(f, paths[i]); });
        refresh();
    });

    const show = (message, value, max) => {
        box.hidden = false;
        text.textContent = message;
        if (value === undefined) bar.removeAttribute('value');
        else { bar.max = max; bar.value = value; }
    };
    const fail = (message) => {
        box.hidden = true;
        uploading = false;
        summary.hidden = false;
        refresh();
        error.hidden = false;
        error.textContent = message;
    };

    const clock = (seconds) => `${Math.floor(seconds / 60)}:${String(Math.round(seconds) % 60).padStart(2, '0')}`;
    const poll = async () => {
        try {
            const job = await (await fetch(form.dataset.statusUrl)).json();
            if (job.state === 'running') {
                const percent = job.total ? ` · ${Math.round(job.done / job.total * 100)} %` : '';
                show(`${job.phase}${percent} · seit ${clock(job.now - job.started)} Min`, job.total ? job.done : undefined, job.total);
            } else if (job.state === 'done') {
                location.href = `${location.pathname}?schritt=scans&hochgeladen=1`;
                return;
            } else if (job.state === 'error') {
                fail(job.error);
                return;
            } else if (job.state === 'idle') {
                fail('Die App wurde neu gestartet, der Upload ist abgebrochen. Bitte noch einmal hochladen.');
                return;
            }
        } catch (e) { /* app restarting: try again */ }
        setTimeout(poll, 1000);
    };

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        error.hidden = true;
        uploading = true;
        button.disabled = true;
        summary.hidden = true;
        if (replaceNote) replaceNote.hidden = true;
        const request = new XMLHttpRequest();
        request.open('POST', form.action);
        request.setRequestHeader('Accept', 'application/json');
        request.upload.onprogress = (e) => {
            if (e.lengthComputable) show(`Hochladen: ${Math.round(e.loaded / e.total * 100)} %`, e.loaded, e.total);
        };
        request.upload.onload = () => show('Dateien sind übertragen und werden von der App übernommen …');
        request.onload = () => {
            if (request.status === 200) poll();
            else { let message; try { message = JSON.parse(request.responseText).error; } catch (e) { /* not JSON */ }
                   fail(message || `Der Upload ist fehlgeschlagen (${request.status}).`); }
        };
        request.onerror = () => fail('Die Verbindung zur App ist abgebrochen.');
        const data = new FormData();
        scans().forEach((f) => data.append('scans', f, rel(f)));  // with the folder: 15.1/a.pdf, 15.2/a.pdf
        request.send(data);
    });

    refresh();
    if (form.dataset.running) { uploading = true; button.disabled = true; summary.hidden = true; poll(); }
})();
