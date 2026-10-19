// Topic admin: edit a title in place; Escape or "Verwerfen" brings the saved one back.
document.addEventListener('click', (e) => {
    const cell = e.target.closest('.topic-heading');
    if (!cell) return;
    const view = cell.querySelector('[data-view]'), form = cell.querySelector('[data-form]');
    if (e.target.closest('[data-edit]')) {
        view.hidden = true; form.hidden = false;
        const field = form.elements.title; field.focus(); field.select();
    } else if (e.target.closest('[data-cancel]')) {
        form.elements.title.value = form.elements.title.defaultValue;
        form.hidden = true; view.hidden = false;
    }
});
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && e.target.closest('[data-form]')) e.target.closest('.topic-heading').querySelector('[data-cancel]').click();
});
