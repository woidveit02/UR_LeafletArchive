// Review of a copy group: choose the main copy, compare the scans and texts side by side.
// evidence can only be picked on the main copy: in its text and on its scan
const pick = initEvidencePicking('.copy-ocr[data-main] .ocr-block[data-block], .scan-boxes .ocr-box[data-block]');
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && pick.active()) pick.stop(false); });

const pair = document.getElementById('pair');
const mains = [...document.querySelectorAll('input[name=main]')], boxes = [...document.querySelectorAll('input[name=show]')];
const checkedGroup = 'checked' in pair.dataset;  // only a checked group has a main copy
let sheet = 1, allSheets = false, onlyDiffs = false;  // the sheet shown, the two options

// the sheet switch decides which sheet of the OCR text is shown, unless all sheets are wanted
const showSheets = () => {
    pair.querySelectorAll('.sheet-row').forEach((row) => { row.hidden = !allSheets && Number(row.dataset.sheet) !== sheet; });
    pair.querySelectorAll('.scan-boxes').forEach((boxes) => { boxes.hidden = Number(boxes.dataset.sheet) !== sheet; });
    pair.querySelectorAll('.copy-sheets button').forEach((b) => {  // both switchers show the same sheet; "Alle" only exists for the text
        const all = b.dataset.sheet === 'all', ofText = b.closest('.copy-sheets').classList.contains('for-text');
        b.setAttribute('aria-pressed', all ? allSheets : Number(b.dataset.sheet) === sheet && !(ofText && allSheets));
    });
};

// the leaflets that are ticked are compared side by side; at least two stay
const loadPair = () => {
    const ids = boxes.filter((b) => b.checked).map((b) => b.value);
    boxes.forEach((b) => { b.disabled = b.checked && ids.length <= 2; });
    fetch(`/leaflets/${pair.dataset.leaflet}/exemplare/paar?ids=${ids.join(',')}`)
        .then((r) => r.text())
        .then((html) => {
            pair.innerHTML = html;
            sheet = 1;
            allSheets = false;
            const box = pair.querySelector('#only-diffs');
            if (box) box.checked = onlyDiffs;
            showSheets();
        });
};

// "gehört nicht dazu" excludes "Hauptexemplar"; the main copy moves on when it is excluded
const sync = () => {
    mains.forEach((r) => { r.disabled = r.closest('.dup-card').querySelector('input[name=out]').checked; });
    mains.filter((r) => r.checked && r.disabled).forEach((r) => { r.checked = false; });
    if (checkedGroup && !mains.some((r) => r.checked)) {  // a checked group keeps a main copy; otherwise the user chooses
        const next = mains.find((r) => !r.disabled);
        if (next) next.checked = true;
    }
    document.querySelectorAll('#save, #save-next').forEach((b) => { b.disabled = !mains.some((r) => r.checked); });
    mains.forEach((r) => {  // the role of a card, as it will be saved
        const badge = r.closest('.dup-card').querySelector('[data-role]'), main = r.checked && !r.disabled;
        badge.hidden = !main && !r.disabled;  // only the main copy and an excluded one carry a badge
        badge.className = `role ${main ? 'main' : 'alt'}`;
        badge.textContent = main ? 'Hauptexemplar' : 'Falsch zugeordnet';
    });
};
if (mains.length) {  // with more than two copies each card has its own choice
    document.querySelectorAll('input[name=out], input[name=main]').forEach((box) => box.addEventListener('change', sync));
    sync();
}
boxes.forEach((b) => b.addEventListener('change', loadPair));

pair.addEventListener('click', (e) => {
    const picked = e.target.dataset.sheet;
    if (!picked) return;  // one sheet number for both copies, for the scans and the OCR text
    allSheets = picked === 'all';  // the whole text; the scans stay at the sheet shown
    if (!allSheets) sheet = Number(picked);
    pair.querySelectorAll('.copy-scan').forEach((scan) => {
        const has = sheet <= Number(scan.dataset.pages), page = Number(scan.dataset.first) + sheet - 1;
        const link = scan.querySelector('a'), img = scan.querySelector('img');
        link.hidden = !has;
        scan.querySelector('p').hidden = has;
        if (has) {
            const url = `/leaflets/${scan.dataset.id}/pages/${page}.png`;
            link.href = url + '?dpi=220';
            img.classList.remove('loaded');  // fades in again when the new sheet has loaded
            img.src = url + '?dpi=90';
            img.alt = `Blattseite ${sheet}`;
        }
    });
    showSheets();
});

// a click on a passage shows its place in the scan: the clicked block and its partner in the other
// copy, one at a time as large as possible (the box of a block; the OCR has no boxes for single words)
const popup = document.getElementById('scan-popup'), grid = document.getElementById('popup-grid');
const shot = (column, blockId) => {
    const [page] = blockId.split('-'), label = column.dataset.label, base = `/leaflets/${column.dataset.leaflet}`;
    const title = label.includes('–') ? `${label}, Seite ${page}` : label;
    return `<figure><figcaption>${title}
        <a href="${base}/pages/${page}.png?dpi=220" target="_blank" rel="noopener">ganze Seite ↗</a></figcaption>
        <img src="${base}/evidence.png?blocks=${blockId}" alt="Ausschnitt aus dem Scan"></figure>`;
};
const showScan = (i) => {
    popup.querySelectorAll('.popup-switch button').forEach((b) => b.setAttribute('aria-pressed', b.dataset.show === String(i)));
    [...grid.children].forEach((figure, n) => { figure.hidden = n !== i; });
};
// the same passage in every shown leaflet: the clicked block and its partners
const passage = (block) => {
    const column = block.closest('.copy-ocr');
    const partners = Object.fromEntries((block.dataset.partners || '').split(' ').filter(Boolean).map((p) => p.split(':')));
    return [...column.closest('.sheet-row').querySelectorAll('.copy-ocr')]
        .map((col) => [col, col === column ? block.dataset.block : partners[col.dataset.side]]);
};
pair.addEventListener('click', (e) => {
    const block = e.target.closest('.ocr-block[data-block]');
    if (!block || e.target.closest('a') || String(getSelection())) return;  // keep links and text selection
    if (pick.active()) return;  // picking evidence: blocks of other leaflets do nothing
    const column = block.closest('.copy-ocr');
    const pieces = passage(block);
    grid.innerHTML = pieces.map(([col, id]) => id ? shot(col, id)
        : `<figure><figcaption>${col.dataset.label}</figcaption>
           <p class="meta">Im anderen Text wurde kein Gegenstück zu dieser Stelle gefunden.</p></figure>`).join('');
    popup.querySelector('.popup-switch').innerHTML = pieces.map(([col], i) =>
        `<button type="button" data-show="${i}" aria-pressed="false">${col.dataset.label.split(' · ')[0]}</button>`).join('');
    showScan(pieces.findIndex(([col]) => col === column));  // the clicked block is shown first
    popup.showModal();
});
popup.querySelector('.popup-switch').addEventListener('click', (e) => {
    const button = e.target.closest('button');
    if (button) showScan(Number(button.dataset.show));
});
document.getElementById('popup-close').addEventListener('click', () => popup.close());
popup.addEventListener('click', (e) => { if (e.target === popup) popup.close(); });  // the backdrop

pair.addEventListener('change', (e) => {
    if (e.target.id === 'only-diffs') { onlyDiffs = e.target.checked; pair.classList.toggle('only-diffs', onlyDiffs); }
});
