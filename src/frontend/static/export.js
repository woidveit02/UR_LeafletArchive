// Export: choose the volumes, build the ZIP and show the progress until the download starts.
const form = document.getElementById('export-form');
const status = document.getElementById('export-status');
const button = form.querySelector('button');
form.querySelectorAll('[data-all]').forEach(a => a.addEventListener('click', e => {
    e.preventDefault();
    form.querySelectorAll('[name=band]').forEach(box => box.checked = !!a.dataset.all);
}));
form.addEventListener('submit', async e => {
    e.preventDefault();
    if (!form.querySelector('[name=band]:checked')) {
        status.textContent = 'Bitte mindestens einen Band wählen.';
        return;
    }
    const url = form.action + '?' + new URLSearchParams(new FormData(form));
    const started = Date.now();
    const tick = () => status.textContent = `ZIP wird erstellt … ${Math.round((Date.now() - started) / 1000)} s`;
    tick();
    const timer = setInterval(tick, 1000);
    button.disabled = true;
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(response.status);
        const blob = await response.blob();
        const name = (response.headers.get('Content-Disposition') || '').match(/filename="([^"]+)"/)?.[1] || 'export.zip';
        const link = Object.assign(document.createElement('a'), {href: URL.createObjectURL(blob), download: name});
        link.click();
        setTimeout(() => URL.revokeObjectURL(link.href), 10000);
        status.textContent = `Fertig: ${name} (${(blob.size / 1e6).toFixed(1).replace('.', ',')} MB) wird heruntergeladen.`;
    } catch (error) {
        status.textContent = 'Der Export ist fehlgeschlagen. Bitte noch einmal versuchen.';
    } finally {
        clearInterval(timer);
        button.disabled = false;
    }
});
