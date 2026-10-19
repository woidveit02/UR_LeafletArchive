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
    const chosen = () => inputs.flatMap((input) => [...input.files]);
    const pending = () => !uploading && chosen().length > 0;
    const size = (bytes) => bytes >= 1e9 ? `${(bytes / 1e9).toFixed(1).replace('.', ',')} GB` : `${Math.max(1, Math.round(bytes / 1e6))} MB`;
    const describe = () => {
        const list = chosen(), total = list.reduce((sum, f) => sum + f.size, 0);
        const what = list.length === 1 ? list[0].name
            : folder.files.length ? `Ordner „${(list[0].webkitRelativePath || '').split('/')[0]}“ mit ${list.length} Dateien`
            : `${list.length} Dateien`;
        return `${what} · ${size(total)}`;
    };
    const clear = () => { inputs.forEach((input) => { input.value = ''; }); refresh(); };
    const refresh = () => {
        const n = chosen().length;
        button.disabled = n === 0;
        zone.classList.toggle('has-files', n > 0);
        if (replaceNote) replaceNote.hidden = n === 0;
        summary.replaceChildren();
        if (!n) { summary.textContent = 'Nichts ausgewählt'; return; }
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'button text';
        remove.textContent = 'Entfernen';
        remove.addEventListener('click', clear);
        summary.append(describe(), ' · ', remove);
    };
    // leaving with a choice that was not uploaded would drop it silently
    document.querySelector('.step-head')?.addEventListener('click', (e) => {
        const link = e.target.closest('a');
        if (link && pending() && !confirm('Ohne Hochladen weitergehen? Die ausgewählten Scans sind noch nicht hochgeladen.')) e.preventDefault();
    });
    inputs.forEach((input) => input.addEventListener('change', () => {
        inputs.filter((other) => other !== input).forEach((other) => { other.value = ''; });
        refresh();
    }));

    // a dropped folder arrives as an entry that is read recursively
    const filesOf = (entry) => new Promise((resolve) => {
        if (entry.isFile) { entry.file((f) => resolve([f]), () => resolve([])); return; }
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
        const dropped = new DataTransfer();
        const found = entries.some((entry) => entry.isDirectory) ? (await Promise.all(entries.map(filesOf))).flat() : direct;
        found.forEach((f) => dropped.items.add(f));
        const target = found.length === 1 && /\.pdf$/i.test(found[0].name) ? pdf : tiffs;
        clear();
        target.files = dropped.files;
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

    const poll = async () => {
        try {
            const job = await (await fetch(form.dataset.statusUrl)).json();
            if (job.state === 'running') {
                show(job.total > 1 ? `Seite ${job.done} von ${job.total} wird zusammengefügt …` : 'Scan wird geprüft …',
                     job.done, job.total);
            } else if (job.state === 'done') {
                location.href = `${location.pathname}?schritt=scans&hochgeladen=1`;
                return;
            } else if (job.state === 'error') {
                fail(job.error);
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
        request.upload.onload = () => show('Dateien werden gespeichert …');
        request.onload = () => {
            if (request.status === 200) poll();
            else { let message; try { message = JSON.parse(request.responseText).error; } catch (e) { /* not JSON */ }
                   fail(message || `Der Upload ist fehlgeschlagen (${request.status}).`); }
        };
        request.onerror = () => fail('Die Verbindung zur App ist abgebrochen.');
        request.send(new FormData(form));
    });

    refresh();
    if (form.dataset.running) { uploading = true; button.disabled = true; summary.hidden = true; poll(); }
})();
