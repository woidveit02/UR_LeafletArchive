// Volume page: mark the pages of a leaflet and let its title run over its cells.
// a link to a page marks the whole leaflet it belongs to
function markRange() {
    document.querySelectorAll('.grid-page.in-range').forEach((el) => el.classList.remove('in-range'));
    const hit = document.getElementById(location.hash.slice(1));
    if (hit?.dataset.leaflet) document.querySelectorAll(`.grid-page[data-leaflet="${hit.dataset.leaflet}"]`).forEach((el) => el.classList.add('in-range'));
}
markRange();
addEventListener('hashchange', markRange);

// a title runs over the cells of its leaflet that share its row
function spanTitles() {
    document.querySelectorAll('.group-start').forEach((first) => {
        let n = 1;
        for (let c = first.nextElementSibling; c && !c.classList.contains('group-start') && c.offsetTop === first.offsetTop; c = c.nextElementSibling) n++;
        first.style.setProperty('--span', n);
    });
}
spanTitles();
addEventListener('resize', spanTitles);

// hovering a page marks its whole leaflet
const pageGrid = document.querySelector('.page-grid');
const mark = (el, on) => {
    const id = el?.closest('.grid-page')?.dataset.leaflet;
    if (id) pageGrid.querySelectorAll(`.grid-page[data-leaflet="${id}"]`).forEach((c) => c.classList.toggle('hover', on));
};
pageGrid?.addEventListener('mouseover', (e) => mark(e.target, true));
pageGrid?.addEventListener('mouseout', (e) => mark(e.target, false));
