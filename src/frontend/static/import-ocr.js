// Starts the text recognition and shows its progress. The run goes on in the app, so the page may be closed;
// without this script the form would show the raw answer.
(() => {
    // leaving before the text is recognized is allowed, but asked about
    const guarded = document.querySelector('[data-leave-warning]');
    document.querySelector('.step-head')?.addEventListener('click', (e) => {
        if (guarded && e.target.closest('a') && !confirm(guarded.dataset.leaveWarning)) e.preventDefault();
    });

    // the folded quality shows the level and its price, which follow the choice
    document.addEventListener('change', (e) => {
        const choice = e.target.closest('input[name="mode"]');
        const details = choice?.closest('details');
        if (!details) return;
        details.querySelector('[data-mode-label]').textContent = choice.dataset.label;
        details.querySelector('[data-mode-price]').textContent = choice.dataset.price;
    });

    const choice = document.getElementById('model-choice'), model = document.getElementById('model');
    choice?.addEventListener('change', () => { model.value = ''; model.dispatchEvent(new Event('input')); });
    model?.addEventListener('input', () => {  // something typed in the search wins over the choice
        const typed = Boolean(model.value.trim());
        [choice.name, model.name] = typed ? ['', 'model'] : ['model', ''];
        choice.classList.toggle('overridden', typed);
        const id = typed ? model.value : choice.value;
        const option = [...document.querySelectorAll('#model-list option')].find((o) => o.value === id);
        document.getElementById('model-price').textContent = option?.dataset.price || 'unbekannt';
        const label = document.getElementById('model-label');
        if (label) label.textContent = typed ? option?.text || id : choice.selectedOptions[0].text;
    });
    model?.dispatchEvent(new Event('input'));

    const prompt = document.getElementById('prompt');
    document.getElementById('prompt-reset')?.addEventListener('click', () => { prompt.value = prompt.dataset.default; });

    const forms = document.querySelectorAll('form[data-ocr]');
    if (!forms.length) return;
    const box = document.getElementById('ocr-progress');
    const bar = box.querySelector('progress');
    const text = box.querySelector('.upload-text');
    const list = document.getElementById('ocr-parts');
    const error = document.getElementById('ocr-error');
    const cancel = document.getElementById('ocr-cancel');
    cancel?.addEventListener('click', async () => {
        if (!confirm(cancel.dataset.confirm)) return;
        cancel.disabled = true;
        await fetch(cancel.dataset.url, {method: 'POST'});
    });
    const url = forms[0].dataset.statusUrl;

    // Datalab reports no progress within a batch, so the page shows what is known: each batch with its
    // state and the time it has been in it, ticking every second between the polls
    let job = null, skew = 0;
    const now = () => Date.now() / 1000 + skew;
    const clock = (t) => {
        const s = Math.max(0, Math.round(now() - t));
        return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
    };
    const STATES = {wartet: 'wartet', upload: 'wird hochgeladen', datalab: 'wird bei Datalab verarbeitet', 'läuft': 'wird verarbeitet', fertig: 'fertig ✓', fehler: 'Fehler'};
    const render = () => {
        if (!job || job.state !== 'running') return;
        box.hidden = false;
        const count = `${job.done} von ${job.total} ${job.unit || 'Seiten erkannt'}`;  // a phase without a count shows its name alone
        text.textContent = `Läuft seit ${clock(job.started)} Min · ${job.phase ? job.phase + (job.total ? ` · ${count}` : '') : count}` +
            (job.cancel ? ' · wird abgebrochen, bereits gesendete Teile werden noch fertig' : '');
        if (cancel) cancel.disabled = Boolean(job.cancel);
        if (job.done) { bar.max = job.total; bar.value = job.done; } else bar.removeAttribute('value');
        list.replaceChildren(...(job.parts || []).map((p, i, all) => {
            const item = document.createElement('li');
            const busy = p.state === 'upload' || p.state === 'datalab';
            item.textContent = `Teil ${i + 1} von ${all.length} · ${p.label || `Seiten ${p.first}–${p.last}`} · ` +
                `${p.kept ? 'schon erkannt ✓' : STATES[p.state]}${busy ? ` (seit ${clock(p.since)} Min)` : ''}`;
            return item;
        }));
    };
    setInterval(render, 1000);

    const poll = async () => {
        try {
            job = await (await fetch(url)).json();
            skew = job.now - Date.now() / 1000;
            if (job.state === 'running') render();
            else if (['done', 'error', 'cancelled'].includes(job.state)) {
                location.reload();  // the page shows the result or the reason
                return;
            }
        } catch (e) { /* app restarting: try again */ }
        setTimeout(poll, 3000);
    };

    forms.forEach((form) => {
        const button = form.querySelector('button[type="submit"]');
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (form.dataset.confirm && !confirm(form.dataset.confirm)) return;
            error.hidden = true;
            button.disabled = true;
            const response = await fetch(form.action, {method: 'POST', body: new URLSearchParams(new FormData(form))});
            if (response.ok) { box.hidden = false; text.textContent = 'Wird gestartet …'; poll(); return; }
            let message;
            try { message = (await response.json()).error; } catch (e) { /* not JSON */ }
            error.textContent = message || `Der Start ist fehlgeschlagen (${response.status}).`;
            error.hidden = false;
            button.disabled = false;
        });
        if (form.dataset.running) poll();
    });
})();
