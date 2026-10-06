// Evidence picking for the metadata form: a field's "Beleg wählen" button starts pick mode, a click on a pickable block
// adds or removes it, and the floating bar names the field while the form is out of view.
// `selector` says which blocks can be picked on the page. Returns {active, stop} for the page's own key handling.
function initEvidencePicking(selector) {
    const bar = document.querySelector('.pick-bar');
    let picking = null;
    const pickedIds = () => picking.input.value.split(' ').filter(Boolean);
    const showPicked = () => {
        document.querySelectorAll('[data-block].picked').forEach((el) => el.classList.remove('picked'));
        if (!picking) return;
        const ids = pickedIds();
        ids.forEach((id) => document.querySelectorAll(`[data-block="${id}"]`).forEach((el) => el.classList.add('picked')));
        const n = ids.length === 1 ? '1 Textstelle' : `${ids.length} Textstellen`;
        picking.btn.textContent = ids.length ? `Beleg: ${n}` : 'Beleg wählen';
        bar.querySelector('.pick-n').textContent = `${n} gewählt`;
    };
    const stopPicking = (restore) => {
        if (!picking) return;
        if (restore) picking.input.value = picking.before;
        showPicked();
        picking.btn.setAttribute('aria-pressed', 'false');
        picking = null;
        bar.hidden = true;
        document.body.classList.remove('picking');
        showPicked();
    };
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.pick-evidence');
        if (!btn) return;
        const again = picking?.btn === btn;
        stopPicking(false);
        if (again) return;
        const input = btn.previousElementSibling;
        picking = { btn, input, before: input.value };
        btn.setAttribute('aria-pressed', 'true');
        bar.querySelector('.pick-field').textContent = btn.dataset.label;
        bar.hidden = false;
        document.body.classList.add('picking');
        showPicked();
    });
    bar.querySelector('[data-pick="done"]').addEventListener('click', () => stopPicking(false));
    bar.querySelector('[data-pick="cancel"]').addEventListener('click', () => stopPicking(true));
    document.addEventListener('click', (e) => {
        const block = picking && e.target.closest(selector);
        if (!block) return;
        e.preventDefault();
        e.stopPropagation();  // capture phase: the usual scroll-to-block handlers stay quiet
        const ids = pickedIds(), id = block.dataset.block;
        picking.input.value = (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]).join(' ');
        showPicked();
    }, true);
    document.addEventListener('click', (e) => {  // capture phase: removing a row ends the picking in it, before meta-form.js removes it
        const remove = e.target.closest('.row-remove');
        if (picking && remove?.parentElement.contains(picking.btn)) stopPicking(false);
    }, true);
    return { active: () => picking !== null, stop: stopPicking };
}
