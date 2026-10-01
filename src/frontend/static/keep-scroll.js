// Keep the scroll position when a view switch, filter or edit reloads the same page.
(() => {
    const key = 'keep-scroll';
    try {
        const saved = JSON.parse(sessionStorage.getItem(key) || 'null');
        sessionStorage.removeItem(key);
        // 'instant', or the page-wide smooth scrolling animates it from the top
        if (saved && saved.path === location.pathname) scrollTo({ top: saved.y, behavior: 'instant' });
    } catch (e) { /* storage unavailable: normal page load */ }

    const keep = () => {
        try {
            sessionStorage.setItem(key, JSON.stringify({ path: location.pathname, y: scrollY }));
        } catch (e) { /* ignore */ }
    };
    document.querySelectorAll('.view-switch a, a.keep-scroll').forEach((a) => a.addEventListener('click', keep));
    document.querySelectorAll('form.keep-scroll').forEach((f) => f.addEventListener('submit', keep));
    document.querySelectorAll('form.filter').forEach((f) => f.addEventListener('change', keep));
})();
