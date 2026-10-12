// Suggestions under the top search field: search in all fields or in one (ARIA combobox pattern).
document.querySelectorAll('form[data-fields]').forEach((form, n) => {
    const input = form.querySelector('input[name=q]');
    const fields = [['', 'Alle Felder'], ...JSON.parse(form.dataset.fields)];
    const list = Object.assign(document.createElement('ul'), {className: 'suggest', role: 'listbox', id: `suggest-${n}`, hidden: true});
    input.after(list);
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-controls', list.id);
    input.setAttribute('aria-expanded', 'false');
    input.setAttribute('aria-autocomplete', 'none');
    let active = 0;

    const options = () => [...list.children];
    const mark = i => {
        active = (i + fields.length) % fields.length;
        options().forEach((li, j) => li.setAttribute('aria-selected', j === active));
        input.setAttribute('aria-activedescendant', options()[active].id);
    };
    const close = () => {
        list.hidden = true;
        input.setAttribute('aria-expanded', 'false');
        input.removeAttribute('aria-activedescendant');
    };
    const choose = key => {
        form.querySelector('input[name=feld]')?.remove();
        if (key) form.append(Object.assign(document.createElement('input'), {type: 'hidden', name: 'feld', value: key}));
        form.requestSubmit();
    };
    const open = () => {
        const text = input.value.trim();
        if (!text) return close();
        list.replaceChildren(...fields.map(([key, label], i) => {
            const li = Object.assign(document.createElement('li'), {role: 'option', id: `${list.id}-${i}`});
            const name = Object.assign(document.createElement('span'), {textContent: key ? `${label}:` : 'Suchen in allen Feldern:'});
            const value = Object.assign(document.createElement('strong'), {textContent: text});
            li.append(name, value);
            if (!key) li.append(Object.assign(document.createElement('span'), {className: 'suggest-enter', textContent: 'Enter ↵'}));
            li.addEventListener('mousedown', e => { e.preventDefault(); choose(key); });
            return li;
        }));
        list.hidden = false;
        input.setAttribute('aria-expanded', 'true');
        mark(0);
    };

    input.addEventListener('input', open);
    input.addEventListener('focus', open);
    input.addEventListener('blur', close);
    input.addEventListener('keydown', e => {
        if (list.hidden) return;
        if (e.key === 'Escape') {
            e.preventDefault();  // the first Escape closes the list instead of emptying the search field
            return close();
        }
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            mark(active + (e.key === 'ArrowDown' ? 1 : -1));
        } else if (e.key === 'Enter') {
            e.preventDefault();
            choose(fields[active][0]);
        }
    });
});
