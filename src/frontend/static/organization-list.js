// Issuer list: filter the rows while typing.
(() => {
    const box = document.getElementById('org-filter');
    const rows = document.querySelectorAll('tr[data-search]');
    box.addEventListener('input', () => {
        const text = box.value.trim().toLowerCase();
        rows.forEach(tr => tr.hidden = !!text && !tr.dataset.search.includes(text));
        const few = document.getElementById('org-few');
        if (few) few.open = !!text;
    });
})();
