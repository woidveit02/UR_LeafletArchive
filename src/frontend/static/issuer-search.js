// The register as a list that stays visible: typing narrows it, each row names the short name, the long form and
// how many leaflets the organization has; without a search the ones with the most leaflets.
(() => {
    const data = document.getElementById('org-register');
    if (!data) return;
    const fold = (text) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    const register = JSON.parse(data.textContent).map((o) => ({ ...o, search: fold([o.name, o.full, ...o.variants].join(' ')) }));
    const query = document.getElementById('org-query'), results = document.getElementById('org-results');
    const count = document.getElementById('org-count');
    const row = (o) => {
        const label = document.createElement('label');
        label.innerHTML = '<input type="radio" name="choice" required><span><span class="org-name"></span> <span class="meta org-full"></span></span><span class="meta org-count"></span>';
        label.querySelector('input').value = o.id;
        label.querySelector('.org-name').textContent = o.name;
        label.querySelector('.org-full').textContent = o.full && o.full !== o.name ? o.full : '';
        label.querySelector('.org-count').textContent = o.n ? `${o.n} ${o.n === 1 ? 'Flugblatt' : 'Flugblätter'}` : 'noch keins';
        return label;
    };
    const show = () => {
        const words = fold(query.value).split(/\s+/).filter(Boolean);
        const chosen = results.querySelector('input:checked')?.value;
        const all = register.filter((o) => words.every((w) => o.search.includes(w))), found = all.slice(0, 8);
        count.textContent = !words.length ? `Die ${found.length} mit den meisten Flugblättern, von ${register.length} im Register`
            : all.length ? `${all.length} ${all.length === 1 ? 'Treffer' : 'Treffer'}${all.length > found.length ? `, die ersten ${found.length}` : ''}`
            : 'Nichts gefunden. Weiter unten lässt sich eine neue Organisation anlegen.';
        results.replaceChildren(...found.map(row));
        results.hidden = !found.length;
        if (chosen) results.querySelector(`input[value="${CSS.escape(chosen)}"]`)?.click();
    };
    query.addEventListener('input', show);
    query.addEventListener('keydown', (e) => {  // Enter takes the first hit instead of sending the form
        if (e.key !== 'Enter') return;
        e.preventDefault();
        results.querySelector('input')?.click();
    });
    show();
})();
