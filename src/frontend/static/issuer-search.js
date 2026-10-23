// The register as a list that stays visible: typing narrows it, each row names the short name, the long form and
// how many leaflets the organization has; without a search the ones with the most leaflets. Several organizations
// can be chosen; the chosen ones stay at the top of the list while searching for the next.
(() => {
    const data = document.getElementById('org-register');
    if (!data) return;
    const form = data.closest('form');
    const fold = (text) => text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
    const register = JSON.parse(data.textContent).map((o) => ({ ...o, search: fold([o.name, o.full, ...o.variants].join(' ')) }));
    const query = document.getElementById('org-query'), results = document.getElementById('org-results');
    const count = document.getElementById('org-count');
    const picked = new Set();
    const row = (o) => {
        const label = document.createElement('label');
        label.innerHTML = '<input type="checkbox" name="choice"><span><span class="org-name"></span> <span class="meta org-full"></span></span><span class="meta org-count"></span>';
        label.querySelector('input').value = o.id;
        label.querySelector('input').checked = picked.has(o.id);
        label.querySelector('.org-name').textContent = o.name;
        label.querySelector('.org-full').textContent = o.full && o.full !== o.name ? o.full : '';
        if (o.n) {  // the leaflets of the organization in a new tab, the choice stays as it is
            const link = Object.assign(document.createElement('a'), { href: `/leaflets?org=${encodeURIComponent(o.id)}`, target: '_blank', rel: 'noopener',
                textContent: `${o.n} ${o.n === 1 ? 'Flugblatt' : 'Flugblätter'} ↗`, title: 'Die Flugblätter in einem neuen Tab' });
            label.querySelector('.org-count').append(link);
        } else label.querySelector('.org-count').textContent = 'noch keins';
        return label;
    };
    const show = () => {
        const words = fold(query.value).split(/\s+/).filter(Boolean);
        const all = register.filter((o) => words.every((w) => o.search.includes(w))), found = all.slice(0, 100);  // the list scrolls
        count.textContent = !words.length ? ''
            : all.length ? `${all.length} Treffer${all.length > found.length ? `, die ersten ${found.length}` : ''}`
            : 'Nichts gefunden. Weiter unten lässt sich eine neue Organisation anlegen.';
        const kept = register.filter((o) => picked.has(o.id) && !found.includes(o));
        results.replaceChildren(...[...kept, ...found].map(row));
        results.hidden = !results.children.length;
    };
    // above the button: what saving assigns
    const summary = document.getElementById('issuer-summary');
    const names = Object.fromEntries(register.map((o) => [o.id, o.name]));
    const surface = summary.dataset.surface;
    const newName = () => (form.short.value || form.full_name.value).trim() || (surface ? `„${surface}“` : 'Name fehlt noch');
    const none = { person: `„${surface}“ wird zu den Unterzeichnenden verschoben.`, erwaehnt: `„${surface}“ wird als Herausgeber entfernt.`,
        personen: 'Kein Herausgeber: Es unterschreiben nur Personen.', unbekannt: 'Kein Herausgeber: nicht feststellbar.' };
    // one evidence per chosen organization (or the person), picked in the scan; it starts with the place found
    const evidence = document.getElementById('issuer-evidence'), rows = evidence.querySelector('.issuer-evidence-rows');
    const picker = initEvidencePicking('.ocr-box');
    const pickText = (value) => { const n = value.split(' ').filter(Boolean).length; return !n ? 'Beleg wählen' : n === 1 ? 'Beleg: 1 Textstelle' : `Beleg: ${n} Textstellen`; };
    const showEvidence = (chosen) => {
        const wanted = chosen.filter((v) => !none[v] || v === 'person');
        [...rows.children].filter((row) => !wanted.includes(row.dataset.for)).forEach((row) => {
            if (row.querySelector('[aria-pressed="true"]')) picker.stop(false);
            row.remove();
        });
        wanted.forEach((v) => {
            let row = [...rows.children].find((r) => r.dataset.for === v);
            if (!row) {
                row = Object.assign(document.createElement('div'), { className: 'issuer-evidence-row' });
                row.dataset.for = v;
                row.innerHTML = '<span></span><input type="hidden" name="evidence_for"><input type="hidden" name="evidence"><button type="button" class="pick-evidence" aria-pressed="false"></button>';
                row.querySelector('[name=evidence_for]').value = v;
                row.querySelector('[name=evidence]').value = evidence.dataset.blocks;
                row.querySelector('button').textContent = pickText(evidence.dataset.blocks);
                rows.append(row);
            }
            const name = v === 'neu' ? newName() : v === 'person' ? `„${surface}“ (Person)` : names[v] || v;
            row.querySelector('span').textContent = name;
            row.querySelector('button').dataset.label = name;
        });
        evidence.hidden = !wanted.length;
    };
    document.querySelector('[data-pick="done"]').addEventListener('click', () => {  // marked in the scan: all evidence chosen
        const ids = [...rows.querySelectorAll('[name=evidence]')].flatMap((input) => input.value.split(' '));
        document.querySelectorAll('.issuer-review .ocr-box').forEach((box) => box.classList.toggle('active', ids.includes(box.dataset.block)));
    });
    const summarize = () => {
        const chosen = [...new Set([...form.querySelectorAll('input[name=choice]:checked')].map((b) => b.value))];
        showEvidence(chosen);
        const text = chosen.filter((v) => !none[v]).map((v) => v === 'neu' ? `${newName()} (neu)` : names[v] || v);
        const others = summary.dataset.others;  // on this leaflet already, they stay
        const decided = chosen.find((v) => none[v]);
        summary.textContent = (decided ? none[decided]
            : text.length ? `Herausgeber: ${[others, ...text].filter(Boolean).join(', ')}.`
                + (surface && text.length === 1 && !chosen.includes('neu') ? ` „${surface}“ wird als Schreibweise von ${text[0]} gemerkt.` : '')
            : 'Noch nichts gewählt.')
            + (others && !text.length ? ` Es bleibt: ${others}.` : '');
    };
    form.addEventListener('change', (e) => {
        const box = e.target;
        if (box.name !== 'choice') return;
        if (box.dataset.none !== undefined) {  // a person or only mentioned: no organization besides
            form.querySelectorAll('input[name=choice]:not([data-none])').forEach((b) => { b.checked = false; });
            picked.clear();
        } else {
            form.querySelectorAll('[data-none]').forEach((b) => { b.checked = false; });
            form.querySelectorAll(`input[name=choice][value="${CSS.escape(box.value)}"]`).forEach((b) => { b.checked = box.checked; });
            if (box.value !== 'neu') picked[box.checked ? 'add' : 'delete'](box.value);
        }
        summarize();
    });
    form.querySelectorAll('[data-new]').forEach((input) => input.addEventListener('input', () => {
        const box = document.getElementById('org-new');
        if (!box.checked) box.click();
        summarize();
    }));
    summarize();
    query.addEventListener('input', show);
    query.addEventListener('keydown', (e) => {  // Enter takes the first hit instead of sending the form
        if (e.key !== 'Enter') return;
        e.preventDefault();
        results.querySelector('input:not(:checked)')?.click();
    });
    show();
})();
