// Rows of the metadata form (issuers, signatories): "+" adds a blank row from the <template>, "×" removes one.
document.addEventListener('click', (e) => {
    const add = e.target.closest('.row-add');
    const remove = e.target.closest('.row-remove');
    if (add) {
        const rows = add.parentElement.querySelector('.edit-rows');
        rows.append(add.previousElementSibling.content.cloneNode(true));
        rows.lastElementChild.querySelector('input').focus();
    } else if (remove) {
        remove.parentElement.remove();
    }
});
