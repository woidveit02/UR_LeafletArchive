// Start page: step through the featured leaflets.
const row = document.querySelector('.featured .doc-grid');
const steps = document.querySelectorAll('.featured-nav button');
const update = () => {
    steps.forEach(b => {
        b.disabled = b.dataset.step < 0 ? row.scrollLeft < 1 : row.scrollLeft + row.clientWidth >= row.scrollWidth - 1;
    });
    const page = Math.round(row.scrollLeft / row.clientWidth) + 1, pages = Math.round(row.scrollWidth / row.clientWidth);
    document.getElementById('featured-count').textContent = `${page} / ${pages}`;
};
steps.forEach(b => b.addEventListener('click', () => row.scrollBy({left: b.dataset.step * row.clientWidth, behavior: 'smooth'})));
row.addEventListener('scroll', update);
update();
