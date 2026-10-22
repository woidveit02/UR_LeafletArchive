// Leaflet list: facet filters, the search conditions and how they travel in the address.
// narrow a long facet list while typing; Enter must not submit the search form
document.querySelectorAll('.facet-filter').forEach((input) => {
    const rows = input.nextElementSibling.querySelectorAll('li');
    input.addEventListener('input', () => {
        const text = input.value.toLowerCase();
        rows.forEach((li) => { li.hidden = !li.textContent.toLowerCase().includes(text); });
    });
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') e.preventDefault(); });
});

(() => {
    const form = document.querySelector('form.filter');
    const lines = document.getElementById('search-lines');
    document.getElementById('add-line').addEventListener('click', () => {
        lines.append(document.getElementById('line-template').content.cloneNode(true));
        lines.lastElementChild.querySelector('.text').focus();
    });
    lines.addEventListener('click', e => {
        const line = e.target.closest('.remove')?.closest('.search-line');
        if (!line) return;
        const next = line.nextElementSibling;
        if (!next) {  // the last line stays and is emptied
            line.querySelector('.text').value = '';
        } else {
            if (!line.classList.contains('extra')) {  // the next line becomes the first
                next.classList.remove('extra');
                next.querySelector('.operator-cell').remove();
            }
            line.remove();
        }
        form.requestSubmit();  // the condition is gone from the results at once
    });
    // the first line with a term travels as q and feld, each further one as s=operator|field|term
    form.addEventListener('submit', () => {
        form.querySelectorAll('input.built').forEach(input => input.remove());
        const add = (name, value) => form.append(Object.assign(document.createElement('input'), {type: 'hidden', name, value, className: 'built'}));
        [...lines.children].filter(line => line.querySelector('.text').value.trim()).forEach((line, i) => {
            const term = line.querySelector('.text').value.trim();
            const field = line.querySelector('.field').value;
            if (i === 0) {
                add('q', term);
                if (field) add('feld', field);
            } else {
                add('s', [line.querySelector('.operator').value, field, term].join('|'));
            }
        });
    });
})();
