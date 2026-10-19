// Trends page: the comparison chart, the charts per term and swapping the page content without a reload.
let mode = 'year';  // year or semester: kept when the page is swapped
const initTrends = () => {
    const data = JSON.parse(document.getElementById('trend-data').textContent);
    const token = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    const COLORS = [token('--accent'), token('--warning'), token('--success'), '#8a3fa8'];
    const labels = data.years.map((y, i) => y.includes('/') ? [y, 'n = ' + data.totals[i], 'zusammengefasst'] : [y, 'n = ' + data.totals[i]]);
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    Chart.defaults.color = token('--muted');
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.scale.ticks.maxRotation = 0;  // years stay readable on phones
    document.querySelectorAll('.trend-swatch').forEach((s) => { s.style.background = COLORS[s.dataset.term]; });

    const share = (t, i) => `${t.counts[i]} von ${data.totals[i]} Flugblättern · ${t.shares[i].toLocaleString('de-DE')} %`;
    // a click on a point or bar opens the list; the pointer cursor and the tooltip footer say so
    const hitAt = (chart, event) => chart.getElementsAtEventForMode(event, 'nearest', {intersect: true}, false)[0];
    const openList = (chart, event, urls) => {
        const hit = hitAt(chart, event);
        if (hit) location.href = urls(hit)[hit.index];
    };
    const pointer = (event, _, chart) => { chart.canvas.style.cursor = hitAt(chart, event) ? 'pointer' : 'default'; };
    const terms = data.terms.filter((t) => t.counts);

    // the comparison chart shows years or semesters (the semester shares have gaps where too few leaflets are dated)
    const periods = () => mode === 'year' ? {labels, totals: data.totals} : {labels: data.sems.labels.map((l) => l.split(' ')), totals: data.sems.totals};
    const values = (t) => mode === 'year' ? t : t.sems;
    // semesters with too few dated leaflets: a gray field behind the lines, the lines break there (no value is measured)
    const semMax = Math.max(10, Math.ceil(Math.max(0, ...terms.flatMap((t) => t.sems.shares.filter((v) => v !== null))) / 10) * 10);
    const gaps = () => mode === 'year' ? [] : data.sems.gap.map((g) => g ? semMax : null);
    const compare = new Chart(document.getElementById('trend-compare'), {
        type: 'line',
        data: {labels, datasets: [...terms.map((t) => ({
            label: t.term, data: t.shares, borderColor: COLORS[data.terms.indexOf(t)],
            backgroundColor: COLORS[data.terms.indexOf(t)], pointRadius: 4, pointHoverRadius: 6, pointHitRadius: 10,
        })), {type: 'bar', label: 'zu wenige datierte Flugblätter', data: [], backgroundColor: token('--surface-muted'), grouped: false, order: 99,
              barPercentage: 1, categoryPercentage: 1}]},
        options: {
            interaction: {mode: 'nearest', intersect: true},  // one point at a time, like the click
            scales: {y: {beginAtZero: true, ticks: {callback: (v) => v + ' %'}}},
            plugins: {legend: {labels: {filter: (item) => item.datasetIndex < terms.length}}, tooltip: {filter: (c) => c.datasetIndex < terms.length, callbacks: {
                title: ([c]) => [].concat(c.chart.data.labels[c.dataIndex]).join(', '),
                label: (c) => {
                    const t = values(terms[c.datasetIndex]), i = c.dataIndex;
                    return `${c.dataset.label}: ${t.counts[i]} von ${periods().totals[i]} ${mode === 'year' ? '' : 'datierten '}Flugblättern · ${t.shares[i].toLocaleString('de-DE')} %`;
                },
                footer: () => 'Klick auf einen Punkt zeigt die Flugblätter',
            }}},
            onHover: pointer,
            onClick: (e, _, chart) => {
                const hit = hitAt(chart, e);
                if (hit && terms[hit.datasetIndex]) location.href = values(terms[hit.datasetIndex]).urls[hit.index];
            },
        },
    });
    document.querySelectorAll('.trend-switch button').forEach((button) => button.addEventListener('click', () => {
        mode = button.dataset.mode;
        document.querySelectorAll('.trend-switch button').forEach((b) => b.setAttribute('aria-pressed', String(b === button)));
        document.getElementById('trend-unit').textContent = mode === 'year' ? 'Jahr' : 'Semester';
        compare.data.labels = periods().labels;
        compare.data.datasets.forEach((d, n) => { d.data = n < terms.length ? values(terms[n]).shares : gaps(); });
        compare.options.scales.y.max = mode === 'year' ? undefined : semMax;
        document.getElementById('trend-basis').textContent = mode === 'year' ? '' : 'Semester: nur Flugblätter mit Monatsangabe';
        const cut = document.getElementById('trend-cut');
        if (cut) cut.hidden = mode === 'year';
        compare.update();
    }));

    // the table of the issuers: a click on a column head sorts it, the first three rows show, a button the rest
    document.querySelectorAll('.trend-orgs').forEach((table) => {
        const body = table.tBodies[0], more = table.nextElementSibling;
        const mark = () => [...body.rows].forEach((r, n) => r.classList.toggle('extra', n >= 3 && !table.classList.contains('open')));
        table.querySelectorAll('[data-sort]').forEach((b) => b.addEventListener('click', () => {
            [...body.rows].sort((x, y) => y.dataset[b.dataset.sort] - x.dataset[b.dataset.sort]).forEach((r) => body.append(r));
            mark();
        }));
        more?.addEventListener('click', () => { table.classList.add('open'); mark(); more.remove(); });
    });

    // one color per issuer on the whole page, apart from the terms' colors; the grays are not issuers
    const ORG_COLORS = ['#8d7b68', '#b59a5b', '#5e7c7a', '#a37b82', '#7c8f6a',
                        '#9a8bb0', '#c0a080', '#6f7f99', '#b07a5a', '#8a9a86'];
    // "mehrere Herausgeber" is hatched, so that it is not taken for an issuer
    const hatch = () => {
        const tile = document.createElement('canvas');
        tile.width = tile.height = 8;
        const g = tile.getContext('2d');
        g.fillStyle = '#eef0f3'; g.fillRect(0, 0, 8, 8);
        g.strokeStyle = '#6b7380'; g.lineWidth = 2; g.beginPath(); g.moveTo(-1, 9); g.lineTo(9, -1); g.stroke();
        return g.createPattern(tile, 'repeat');
    };
    const orgColor = {nicht_im_register: '#8a929c', _mehrere: hatch(), null: '#c8ccd2'};
    data.terms.flatMap((t) => t.by_org || []).forEach((o) => {
        if (!(o.org in orgColor)) orgColor[o.org] = ORG_COLORS[Object.keys(orgColor).length % ORG_COLORS.length];
    });
    document.querySelectorAll('canvas[data-orgs]').forEach((canvas) => {
        const t = data.terms[canvas.dataset.orgs];
        new Chart(canvas, {
            type: 'bar',
            data: {labels, datasets: t.by_org.map((o) => ({
                label: o.label, backgroundColor: orgColor[o.org],
                data: o.counts.map((n, i) => n / data.totals[i] * 100)}))},  // share of the year's leaflets
            options: {
                interaction: {mode: 'index', intersect: false},
                scales: {x: {stacked: true}, y: {stacked: true, beginAtZero: true, ticks: {callback: (v) => v + ' %'}}},
                plugins: {legend: {position: 'bottom', labels: {boxWidth: 12}}, tooltip: {
                    filter: (c) => c.raw > 0, callbacks: {
                        label: (c) => `${c.dataset.label}: ${t.by_org[c.datasetIndex].counts[c.dataIndex]}`,
                        title: ([c]) => c ? [data.years[c.dataIndex], share(t, c.dataIndex)] : '',  // empty column: no item left
                        footer: () => 'Klick auf einen Abschnitt zeigt dessen Flugblätter',
                    }}},
                onHover: pointer,
                onClick: (e, _, chart) => openList(chart, e, (hit) => t.by_org[hit.datasetIndex].urls),
            },
        });
    });

    // the semester view stays when the page is swapped
    if (mode !== 'year') document.querySelector(`.trend-switch button[data-mode="${mode}"]`)?.click();
};
initTrends();

// links and the form of this page swap the content instead of loading the page again (the address stays right)
const content = document.getElementById('content');
const go = async (url, push = true) => {
    content.style.opacity = '0.55';
    try {
        const doc = new DOMParser().parseFromString(await (await fetch(url)).text(), 'text/html');
        if (!doc.getElementById('trend-data')) { location.href = url; return; }
        document.querySelectorAll('canvas').forEach((c) => Chart.getChart(c)?.destroy());
        content.replaceChildren(...doc.getElementById('content').childNodes);
        document.getElementById('trend-data').textContent = doc.getElementById('trend-data').textContent;
        if (push) history.pushState({}, '', url);
        initTrends();
    } catch (error) {
        location.href = url;
    } finally {
        content.style.opacity = '';
    }
};
document.addEventListener('click', (e) => {
    const link = e.target.closest('.trend-tabs a, .form-toggle, .active-filter, .trend-examples a');
    if (!link || e.metaKey || e.ctrlKey || e.shiftKey || !link.getAttribute('href')?.startsWith('/trends')) return;
    e.preventDefault();
    go(link.getAttribute('href'));
});
document.addEventListener('submit', (e) => {
    if (!e.target.matches('.trend-form')) return;
    e.preventDefault();
    go('/trends?' + new URLSearchParams(new FormData(e.target)));
});
window.addEventListener('popstate', () => go(location.href, false));
