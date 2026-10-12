// Shared by the leaflet page and the text check: a block of the transcription and its box on the scan light up together.
window.PagePair = (() => {
    const highlight = (els, on) => els.forEach((el) => el.classList.toggle('active', on));

    const flash = (els) => {
        els[0]?.scrollIntoView({behavior: 'smooth', block: 'center'});
        highlight(els, true);
        setTimeout(() => highlight(els, false), 1500);
    };

    const link = (block, box) => {
        for (const el of [block, box]) {
            el.addEventListener('mouseenter', () => highlight([block, box], true));
            el.addEventListener('mouseleave', () => highlight([block, box], false));
        }
        box.addEventListener('click', () => flash([block]));
    };

    return {highlight, flash, link};
})();
