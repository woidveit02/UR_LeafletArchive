// Upload of the scans with a progress bar: first the transfer to the app, then the building of the PDF,
// which runs in the background and is polled. Without this script the form is a plain post.
(() => {
    // the browser's own file button speaks the browser's language: a German label and the chosen names instead
    document.querySelectorAll('.file-pick input').forEach((input) => {
        const name = input.parentElement.querySelector('.file-name');
        input.addEventListener('change', () => {
            const n = input.files.length;
            name.textContent = n === 0 ? 'Nichts ausgewählt' : n === 1 ? input.files[0].name : `${n} Dateien ausgewählt`;
        });
    });

    const form = document.querySelector('form[data-status-url]');
    if (!form) return;
    const box = document.getElementById('upload-progress');
    const bar = box.querySelector('progress');
    const text = box.querySelector('.upload-text');
    const error = document.getElementById('upload-error');
    const button = form.querySelector('button');

    const show = (message, value, max) => {
        box.hidden = false;
        text.textContent = message;
        if (value === undefined) bar.removeAttribute('value');
        else { bar.max = max; bar.value = value; }
    };
    const fail = (message) => {
        box.hidden = true;
        button.disabled = false;
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
                location.reload();
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
        button.disabled = true;
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

    if (form.dataset.running) { button.disabled = true; poll(); }
})();
