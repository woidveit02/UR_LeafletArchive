// The map of all leaflets by text similarity, with its legend, zoom and highlighting: /themen and the review of a new run.
Chart.register(ChartZoom);
const mapData = JSON.parse(document.getElementById('topic-map-data').textContent);
const COLORS = ['#4c72b0', '#dd8452', '#55a868', '#c44e52', '#8172b3', '#937860', '#da8bc3',
               '#ccb974', '#64b5cd', '#2f4b7c', '#a5d233', '#d45087', '#2ca089', '#f0a500',
               '#7a5195', '#003f5c', '#ef5675', '#665191', '#ffa600', '#488f31'];
const toPoints = (rows) => rows.map(([x, y, id, title, issuers, year, uncertain]) =>
    ({x, y, url: '/leaflets/' + id, title, issuers, year, uncertain}));
const hitAt = (chart, event) => chart.getElementsAtEventForMode(event, 'nearest', {intersect: true}, false)[0];
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'})[c]);

const picker = document.createElement('ul');
picker.className = 'topic-map-picker';
picker.hidden = true;
document.body.append(picker);
document.addEventListener('click', (e) => { if (!picker.contains(e.target)) picker.hidden = true; });

// custom tooltip: the color belongs to the topic line, leaflets listed below it plain
const tooltipEl = document.createElement('div');
tooltipEl.className = 'topic-map-tooltip';
tooltipEl.hidden = true;
document.body.append(tooltipEl);

function externalTooltip(context) {
    const tt = context.tooltip;
    const points = tt.dataPoints || [];
    // an open picker replaces the tooltip, which would otherwise cover it
    if (!tt.opacity || !points.length || !picker.hidden) { tooltipEl.hidden = true; return; }

    tooltipEl.innerHTML = '';
    const topic = document.createElement('div');
    topic.className = 'tm-topic';
    const swatch = document.createElement('span');
    swatch.className = 'tm-swatch';
    swatch.style.background = points[0].dataset.color || points[0].dataset.backgroundColor;
    topic.append(swatch, document.createTextNode(points[0].dataset.label));
    tooltipEl.append(topic);

    const list = document.createElement('ul');
    points.forEach((p) => {
        const li = document.createElement('li');
        li.textContent = p.raw.title + ' · '
            + [p.raw.year, p.raw.issuers, p.raw.uncertain ? 'unsicher' : null].filter(Boolean).join(' · ');
        list.append(li);
    });
    tooltipEl.append(list);

    const hint = document.createElement('p');
    hint.className = 'meta';
    hint.textContent = points.length > 1 ? 'Klick zum Auswählen' : 'Klick zeigt das Flugblatt';
    tooltipEl.append(hint);

    const rect = context.chart.canvas.getBoundingClientRect();
    tooltipEl.style.left = rect.left + tt.caretX + 10 + 'px';
    tooltipEl.style.top = rect.top + tt.caretY + 10 + 'px';
    tooltipEl.hidden = false;
}

// an isotropic view: 1 UMAP unit covers the same pixel distance on both axes,
// otherwise a wide, short canvas visually squashes the vertical distances.
// factored out so fullscreen (different aspect ratio) can recompute it.
const allXY = mapData.no_topic.concat(...mapData.topics.map((t) => t.points));
const dataXMin = Math.min(...allXY.map((p) => p[0])), dataXMax = Math.max(...allXY.map((p) => p[0]));
const dataYMin = Math.min(...allXY.map((p) => p[1])), dataYMax = Math.max(...allXY.map((p) => p[1]));
const wrapEl = document.querySelector('.topic-map-canvas-area');

function isotropicRange() {
    const wrapStyle = getComputedStyle(wrapEl);
    const plotW = wrapEl.clientWidth - parseFloat(wrapStyle.paddingRight);
    const plotH = wrapEl.clientHeight - parseFloat(wrapStyle.paddingBottom);
    const dataAspect = (dataXMax - dataXMin) / (dataYMax - dataYMin), canvasAspect = plotW / plotH;
    const xRange = {min: dataXMin, max: dataXMax}, yRange = {min: dataYMin, max: dataYMax};
    if (canvasAspect > dataAspect) {
        const pad = ((dataYMax - dataYMin) * canvasAspect - (dataXMax - dataXMin)) / 2;
        xRange.min -= pad; xRange.max += pad;
    } else {
        const pad = ((dataXMax - dataXMin) / canvasAspect - (dataYMax - dataYMin)) / 2;
        yRange.min -= pad; yRange.max += pad;
    }
    // a touch more margin so the overview isn't cropped right at the outermost points
    const OVERVIEW_MARGIN = 0.04;
    const xPad = (xRange.max - xRange.min) * OVERVIEW_MARGIN;
    const yPad = (yRange.max - yRange.min) * OVERVIEW_MARGIN;
    xRange.min -= xPad; xRange.max += xPad;
    yRange.min -= yPad; yRange.max += yPad;
    return {xRange, yRange};
}

const colorById = {};
mapData.topics.forEach((t, i) => { colorById[t.id] = COLORS[i % COLORS.length]; });

// a factory, not a one-off: rebuilt from scratch after the maximize toggle instead of
// resized in place, since Chart.js' own resize/ResizeObserver pipeline kept leaving the
// canvas's internal pixel buffer out of sync with its new CSS size on that transition
// (stretched/squashed, washed-out colors) no matter which resize hook it was driven from.
// A fresh instance always measures its container correctly at construction time.
function buildChart() {
    return new Chart(document.getElementById('topic-map'), {
        type: 'scatter',
        data: {datasets: [
            {label: 'ohne Thema', data: toPoints(mapData.no_topic),
             backgroundColor: '#d9dce1', pointRadius: 1.5},
            ...mapData.topics.map((t) => {
                const color = colorById[t.id];
                return {label: t.title, id: t.id, data: toPoints(t.points), color, pointRadius: 2.5,
                       // unsure assignments fade out instead of standing out in full color
                       backgroundColor: (ctx) => color + (ctx.raw && ctx.raw.uncertain ? '55' : 'cc')};
            }),
        ]},
        options: {
            maintainAspectRatio: false,
            // zoom/pan redraw on every wheel tick and pointer move; animated transitions
            // between those (Chart.js' default) make it feel laggy instead of direct
            animation: false,
            interaction: {mode: 'point', intersect: true},
            scales: {x: {display: false, ...isotropicRange().xRange}, y: {display: false, ...isotropicRange().yRange}},
            plugins: {
                legend: {display: false},
                tooltip: {enabled: false, external: externalTooltip},
                zoom: {
                    pan: {enabled: true, mode: 'xy', onPanComplete: ({chart: c}) => updateScrollbars(c)},
                    zoom: {wheel: {enabled: true}, pinch: {enabled: true}, mode: 'xy',
                          onZoomComplete: ({chart: c}) => updateScrollbars(c)},
                    limits: {x: {...isotropicRange().xRange}, y: {...isotropicRange().yRange}},
                },
            },
            onHover: (event, _, c) => {
                if (isDragging) return;
                const hit = hitAt(c, event);
                c.canvas.style.cursor = hit ? 'pointer' : 'default';
                const topic = hit && mapData.topics.find((t) => t.id === c.data.datasets[hit.datasetIndex].id);
                previewHighlight(topic || null);
            },
            onClick: (event, _, c) => {
                const hits = c.getElementsAtEventForMode(event, 'point', {intersect: true}, false);
                if (!hits.length) return;
                const leaflets = hits.map((h) => c.data.datasets[h.datasetIndex].data[h.index]);
                if (leaflets.length === 1) { location.href = leaflets[0].url; return; }
                picker.innerHTML = leaflets.map((l) =>
                    `<li><a href="${l.url}">${esc(l.title)}<span class="meta"> · ${
                        esc([l.year, l.issuers, l.uncertain ? 'unsicher' : null].filter(Boolean).join(' · '))}</span></a></li>`
                ).join('');
                picker.style.left = event.native.clientX + 'px';
                picker.style.top = event.native.clientY + 'px';
                picker.hidden = false;
                tooltipEl.hidden = true;
            },
        },
    });
}

let chart = buildChart();

// scrollbar thumbs mirror the zoomed/panned extent of the original (locked) axis range
const original = {x: {...chart.scales.x}, y: {...chart.scales.y}};
const hThumb = document.getElementById('topic-map-hthumb');
const vThumb = document.getElementById('topic-map-vthumb');

function updateScrollbars(c) {
    const ox = original.x, oy = original.y, x = c.scales.x, y = c.scales.y;
    const xSpan = ox.max - ox.min, ySpan = oy.max - oy.min;
    // at the full (locked) extent there is nothing to scroll: hide the track instead of a full-width thumb
    const xFull = x.max - x.min >= xSpan - 1e-6, yFull = y.max - y.min >= ySpan - 1e-6;
    hThumb.parentElement.hidden = xFull;
    vThumb.parentElement.hidden = yFull;
    if (!xFull) {
        hThumb.style.left = (x.min - ox.min) / xSpan * 100 + '%';
        hThumb.style.width = (x.max - x.min) / xSpan * 100 + '%';
    }
    if (!yFull) {
        // the y axis runs low-to-high bottom-to-top; the track runs top-to-bottom like the canvas
        vThumb.style.top = (oy.max - y.max) / ySpan * 100 + '%';
        vThumb.style.height = (y.max - y.min) / ySpan * 100 + '%';
    }
}
updateScrollbars(chart);

function dragThumb(thumb, track, axis) {
    thumb.addEventListener('pointerdown', (down) => {
        down.preventDefault();
        const trackRect = track.getBoundingClientRect();
        const trackLength = axis === 'x' ? trackRect.width : trackRect.height;
        let lastPos = axis === 'x' ? down.clientX : down.clientY;

        function move(e) {
            const pos = axis === 'x' ? e.clientX : e.clientY;
            const trackDelta = pos - lastPos;
            lastPos = pos;
            // a scrollbar moves the view the same way the thumb moves: the opposite of dragging the content itself.
            // the magnitude comes from the value delta (zoom-aware, via the scale's current pixel-per-value
            // ratio), but the sign must follow trackDelta directly: getPixelForValue() is inverted for the
            // y-axis (larger data value -> smaller screen pixel), which would otherwise flip only that axis
            const scale = chart.scales[axis];
            const valueDelta = trackDelta / trackLength * (original[axis].max - original[axis].min);
            const pixelDelta = Math.abs(scale.getPixelForValue(scale.min + valueDelta) - scale.getPixelForValue(scale.min))
                * Math.sign(trackDelta);
            chart.pan({[axis]: -pixelDelta}, undefined, 'none');
            updateScrollbars(chart);
        }

        function up() {
            document.removeEventListener('pointermove', move);
            document.removeEventListener('pointerup', up);
        }
        document.addEventListener('pointermove', move);
        document.addEventListener('pointerup', up);
    });
}
dragThumb(hThumb, hThumb.parentElement, 'x');
dragThumb(vThumb, vThumb.parentElement, 'y');

// chartjs-plugin-zoom's own drag-to-pan needs Hammer.js, which isn't loaded here
// (only wheel/pinch zoom use plain DOM events) - so left-button drag is done by hand
let dragMoved = false;
let isDragging = false;
chart.canvas.addEventListener('click', (e) => {
    if (dragMoved) { e.stopPropagation(); dragMoved = false; }
}, true);
chart.canvas.addEventListener('pointerdown', (down) => {
    if (down.button !== 0) return;
    let last = {x: down.clientX, y: down.clientY};
    dragMoved = false;

    function move(e) {
        const dx = e.clientX - last.x, dy = e.clientY - last.y;
        last = {x: e.clientX, y: e.clientY};
        if (!dragMoved && (Math.abs(dx) > 3 || Math.abs(dy) > 3)) {
            dragMoved = true;
            isDragging = true;
            chart.canvas.style.cursor = 'grabbing';
        }
        if (dragMoved) {
            chart.pan({x: dx, y: dy}, undefined, 'none');
            updateScrollbars(chart);
        }
    }

    function up() {
        isDragging = false;
        chart.canvas.style.cursor = 'default';
        document.removeEventListener('pointermove', move);
        document.removeEventListener('pointerup', up);
    }
    document.addEventListener('pointermove', move);
    document.addEventListener('pointerup', up);
});

document.getElementById('topic-map-reset').addEventListener('click', () => {
    chart.resetZoom();
    updateScrollbars(chart);
});
document.getElementById('topic-map-in').addEventListener('click', () => {
    chart.zoom(1.2);
    updateScrollbars(chart);
});
document.getElementById('topic-map-out').addEventListener('click', () => {
    chart.zoom(1 / 1.2);
    updateScrollbars(chart);
});

// "Vollbild" only maximizes within the browser window (position: fixed over the
// page), not the OS-level Fullscreen API: no browser-chrome takeover, no permission prompt.
const mapWrapEl = document.querySelector('.topic-map-wrap');
const fullscreenBtn = document.getElementById('topic-map-fullscreen');

function setMaximized(on) {
    mapWrapEl.classList.toggle('maximized', on);
    document.body.classList.toggle('topic-map-lock-scroll', on);
    fullscreenBtn.textContent = on ? 'Vollbild verlassen' : 'Vollbild';
    // double rAF: wait for the final layout, including a page scrollbar that can
    // reappear a frame after the flex/position change (exiting unlocks body scroll)
    requestAnimationFrame(() => requestAnimationFrame(() => {
        chart.destroy();
        chart = buildChart();
        original.x = {...chart.scales.x};
        original.y = {...chart.scales.y};
        applyFilters();
        updateScrollbars(chart);
    }));
}
fullscreenBtn.addEventListener('click', () => setMaximized(!mapWrapEl.classList.contains('maximized')));
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && mapWrapEl.classList.contains('maximized')) setMaximized(false);
});

// highlighting is a legend function: click toggles a topic in/out of the active
// set (multiple at once), hovering a row/point/legend entry previews one topic
// and falls back to the active set on mouseleave.
const originalColors = chart.data.datasets.map((d) => d.backgroundColor);
const activeTopics = new Set();

function render(ids) {
    const dim = ids && ids.size > 0;
    chart.data.datasets.forEach((d, i) => {
        d.backgroundColor = !dim || ids.has(d.id) ? originalColors[i] : '#d9dce1';
    });
    chart.update();
    document.querySelectorAll('.topic-row-highlight').forEach((el) => el.classList.remove('topic-row-highlight'));
    document.querySelectorAll('.topic-map-legend button.active').forEach((el) => el.classList.remove('active'));
    if (dim) {
        ids.forEach((id) => {
            const row = document.querySelector(`.topic-row[data-id="${id}"]`);
            if (row) row.classList.add('topic-row-highlight');
            const btn = document.querySelector(`.topic-map-legend button[data-id="${id}"]`);
            if (btn) btn.classList.add('active');
        });
    }
}

const refresh = () => render(activeTopics);
// hovering previews on top of the active selection instead of replacing it,
// so a multi-selection doesn't visually disappear while the mouse passes over another topic
const previewHighlight = (topic) => render(topic ? new Set([...activeTopics, topic.id]) : activeTopics);

// "aktive Themen" strip above the map, same look as the active-filter pills on /leaflets
const activeFiltersEl = document.getElementById('topic-active-filters');

function renderActiveChips() {
    activeFiltersEl.hidden = activeTopics.size === 0;
    if (!activeTopics.size) { activeFiltersEl.innerHTML = ''; return; }
    activeFiltersEl.innerHTML = [...activeTopics].map((id) => {
        const t = mapData.topics.find((x) => x.id === id);
        return `<button type="button" class="active-filter" data-id="${id}" title="Entfernen">${esc(t.title)} <span aria-hidden="true">×</span></button>`;
    }).join('')
        + '<button type="button" class="active-reset">Alle zurücksetzen</button>'
        + `<a class="button small topic-list-link" href="/leaflets?${[...activeTopics].map((id) => `${mapData.param || 'thema'}=${id}`).join('&')}">In der Liste zeigen</a>`;
    activeFiltersEl.querySelectorAll('button.active-filter').forEach((btn) => {
        const topic = mapData.topics.find((t) => String(t.id) === btn.dataset.id);
        btn.addEventListener('click', () => toggleTopic(topic));
    });
    activeFiltersEl.querySelector('.active-reset').addEventListener('click', () => {
        activeTopics.clear();
        document.querySelectorAll('.topic-map-legend button[aria-pressed="true"]').forEach((b) => b.setAttribute('aria-pressed', 'false'));
        refresh();
        renderActiveChips();
    });
}

function toggleTopic(topic) {
    if (activeTopics.has(topic.id)) activeTopics.delete(topic.id);
    else activeTopics.add(topic.id);
    document.querySelector(`.topic-map-legend button[data-id="${topic.id}"]`)
        ?.setAttribute('aria-pressed', String(activeTopics.has(topic.id)));
    refresh();
    renderActiveChips();
}

mapData.topics.forEach((topic) => {
    const row = document.querySelector(`.topic-row[data-id="${topic.id}"]`);
    if (!row) return;
    row.addEventListener('mouseenter', () => previewHighlight(topic));
    row.addEventListener('mouseleave', () => previewHighlight(null));
});

// legend next to the map: title, color, count; click toggles that topic's highlight.
// a real <button> gives native hover/focus/keyboard affordance for free.
const legendEl = document.getElementById('topic-map-legend');
const showUncertainEl = document.getElementById('topic-map-show-uncertain');
const showNoTopicEl = document.getElementById('topic-map-show-no-topic');
const visibleCount = (t) => t.points.filter((p) => showUncertainEl.checked || !p[6]).length;

// sorted by how many points are actually visible, so the order follows the
// same filters as the counts instead of staying pinned to the unfiltered total
function renderLegend() {
    const order = [...mapData.topics].sort((a, b) => visibleCount(b) - visibleCount(a));
    legendEl.innerHTML = order.map((t) =>
        `<li><button type="button" data-id="${t.id}" aria-pressed="${activeTopics.has(t.id)}">`
        + `<span class="tm-swatch" style="background:${colorById[t.id]}"></span>`
        + `<span class="tm-title">${esc(t.title)}</span>`
        + `<span class="meta tm-count">${visibleCount(t)}</span></button></li>`
    ).join('');
    legendEl.querySelectorAll('button').forEach((btn) => {
        const topic = mapData.topics.find((t) => String(t.id) === btn.dataset.id);
        btn.addEventListener('mouseenter', () => previewHighlight(topic));
        btn.addEventListener('mouseleave', () => previewHighlight(null));
        btn.addEventListener('click', () => toggleTopic(topic));
    });
    refresh();
}

function applyFilters() {
    const showUncertain = showUncertainEl.checked;
    const keep = (points) => points.filter((p) => showUncertain || !p[6]);
    chart.data.datasets[0].data = showNoTopicEl.checked ? toPoints(keep(mapData.no_topic)) : [];
    mapData.topics.forEach((t, i) => { chart.data.datasets[i + 1].data = toPoints(keep(t.points)); });
    chart.update();
    renderLegend();
}
showUncertainEl.addEventListener('change', applyFilters);
showNoTopicEl.addEventListener('change', applyFilters);
applyFilters();
