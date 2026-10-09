
    // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ CONFIGURATION â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    const POLL_STATS_MS       = 500;
    const POLL_THROUGHPUT_MS  = 1000;
    const POLL_PLAZA_MS       = 2000;
    const POLL_EVENTS_MS      = 2000;
    const POLL_HEALTH_MS      = 5000;

    // Actual Toll Plaza coordinates in India
    
    const KNOWN_PLAZAS = {
        'PLAZA_NH44_DELHI':     { region: 'DELHI', name: 'Delhi Border (NH-44)' },
        'PLAZA_NH48_MUMBAI':    { region: 'MUMBAI',  name: 'Bandra-Worli (Mumbai)' },
        'PLAZA_NH44_CHENNAI':   { region: 'CHENNAI', name: 'Paranur (Chennai)' }
    };


    // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ STATE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    const counters = {
        totalPings:   { current: 0, target: 0, el: null },
        totalJourneys:{ current: 0, target: 0, el: null },
        dedupRatio:   { current: 0, target: 0, el: null },
        pps:          { current: 0, target: 0, el: null },
    };
    let lastDedupRunAt = null;
    let plazaSortKey   = 'total_pings';
    let plazaSortAsc   = false;
    let currentPlazaData = {};

    let throughputChart = null;
    let dedupGaugeChart = null;
    let map = null;
    let mapMarkers = {};

    // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ UTILITIES â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    function escapeHtml(s) {
        return String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    function formatTime(iso) {
        if (!iso) return 'â€”';
        try {
            const d = new Date(iso);
            return d.toLocaleTimeString('en-US', { hour12: false });
        } catch { return iso; }
    }
    function formatPlazaName(id) {
        if (KNOWN_PLAZAS[id]) return KNOWN_PLAZAS[id].name;
        return String(id).replace(/^PLAZA_/i, '').replace(/_/g, ' ');
    }
    function debounce(fn, ms) {
        let timer;
        return function() {
            const args = arguments;
            clearTimeout(timer);
            timer = setTimeout(function() { fn.apply(null, args); }, ms);
        };
    }

    
    // --- CUSTOM CSS MAP INITIALIZATION ---
    
    // --- CUSTOM CSS MAP INITIALIZATION ---
    const mapContainer = document.getElementById('map');
    if (mapContainer) {
        // Reset container to be a flexbox
        mapContainer.style.display = 'flex';
        mapContainer.style.justifyContent = 'center';
        mapContainer.style.alignItems = 'center';
        mapContainer.style.overflow = 'hidden';
        
        // Create an inner wrapper that maintains the 1:1 square aspect ratio of the image
        var mapDiv = document.createElement('div');
        mapDiv.style.position = 'relative';
        mapDiv.style.height = '100%';
        mapDiv.style.aspectRatio = '1 / 1';
        mapDiv.style.backgroundImage = "url('/static/india_map_transparent.png')";
        mapDiv.style.backgroundSize = 'contain';
        mapDiv.style.backgroundRepeat = 'no-repeat';
        mapDiv.style.backgroundPosition = 'center';
        
        mapContainer.appendChild(mapDiv);
    }

    
    
    const tooltip = document.createElement('div');
    tooltip.style.position = 'absolute';
    tooltip.style.display = 'none';
    tooltip.style.backgroundColor = '#d4edda';
    tooltip.style.border = '2px solid #0b4a22';
    tooltip.style.padding = '10px';
    tooltip.style.borderRadius = '5px';
    tooltip.style.color = '#0b4a22';
    tooltip.style.fontWeight = 'bold';
    tooltip.style.zIndex = '1000';
    tooltip.style.boxShadow = '0 2px 10px rgba(0,0,0,0.2)';
    tooltip.style.pointerEvents = 'none';
    
    if (mapDiv) {
        mapDiv.appendChild(tooltip);
    }

    const markersData = {};

    const markers = {};
    
    function createMarker(id, top, left, label) {
        if (!mapDiv) return;
        const m = document.createElement('div');
        m.style.position = 'absolute';
        m.style.top = top;
        m.style.left = left;
        m.style.width = '15px';
        m.style.height = '15px';
        m.style.backgroundColor = 'var(--color-3)';
        m.style.borderRadius = '50%';
        m.style.transform = 'translate(-50%, -50%)';
        m.style.transition = 'all 0.3s ease';
        m.style.boxShadow = '0 0 10px var(--color-3)';
        
        const text = document.createElement('div');
        text.textContent = label;
        text.style.position = 'absolute';
        text.style.top = '20px';
        text.style.left = '50%';
        text.style.transform = 'translateX(-50%)';
        text.style.color = '#0b4a22';
        text.style.fontWeight = 'bold';
        text.style.textShadow = '0 0 3px #fff';
        m.appendChild(text);
        
        mapDiv.appendChild(m);
        
        m.style.cursor = 'pointer';
        
        m.onclick = function(e) {
            const data = markersData[id];
            if (data) {
                tooltip.innerHTML = `
                    <div style="font-size: 1.1em; border-bottom: 1px solid #0b4a22; margin-bottom: 5px; padding-bottom: 5px;">${label}</div>
                    Total Pings: ${data.total_pings.toLocaleString()}<br>
                    Unique Tags: ${data.unique_tags.toLocaleString()}<br>
                    Duplicates: ${data.duplicates.toLocaleString()}
                `;
                tooltip.style.display = 'block';
                
                // Position tooltip near the marker
                const rect = m.getBoundingClientRect();
                const mapRect = mapDiv.getBoundingClientRect();
                tooltip.style.left = (rect.left - mapRect.left + 25) + 'px';
                tooltip.style.top = (rect.top - mapRect.top - 20) + 'px';
                
                // Hide after 3 seconds
                setTimeout(() => { tooltip.style.display = 'none'; }, 3000);
            } else {
                tooltip.innerHTML = label + "<br>No data yet";
                tooltip.style.display = 'block';
                const rect = m.getBoundingClientRect();
                const mapRect = mapDiv.getBoundingClientRect();
                tooltip.style.left = (rect.left - mapRect.left + 25) + 'px';
                tooltip.style.top = (rect.top - mapRect.top - 20) + 'px';
                setTimeout(() => { tooltip.style.display = 'none'; }, 3000);
            }
            e.stopPropagation();
        };
        
        mapDiv.onclick = function() {
            tooltip.style.display = 'none';
        };

        markers[id] = m;
    }
    
    function initMap() {
        createMarker('PLAZA_NH44_DELHI', '32%', '45%', 'DELHI');
        createMarker('PLAZA_NH48_MUMBAI', '65%', '32%', 'MUMBAI');
        createMarker('PLAZA_NH44_CHENNAI', '82%', '45%', 'CHENNAI');
    }
    
    function updateMapMarkers(plazasData) {
        Object.values(markers).forEach(m => {
            m.style.width = '15px';
            m.style.height = '15px';
            m.style.backgroundColor = 'var(--color-3)';
        });
        
        
        for (const id in plazasData) {
            const data = plazasData[id];
            markersData[id] = data;

            if (markers[id]) {
                const scale = Math.min(3, 1 + (data.total_pings / 5000));
                markers[id].style.width = (15 * scale) + 'px';
                markers[id].style.height = (15 * scale) + 'px';
                markers[id].style.backgroundColor = '#913c32'; // Reddish when active
            }
        }
    }

    // ─── COUNTER ANIMATION ───
    function tickCounters() {
        for (const key of Object.keys(counters)) {
            const c = counters[key];
            if (!c.el) continue;
            const diff = c.target - c.current;
            if (Math.abs(diff) < 0.5) {
                c.current = c.target;
            } else {
                c.current += diff * 0.15;
            }
            if (key === 'dedupRatio') {
                c.el.textContent = c.current.toFixed(1) + '%';
            } else {
                c.el.textContent = Math.round(c.current).toLocaleString();
            }
        }
        requestAnimationFrame(tickCounters);
    }

    // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ CHART INITIALIZATION â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    function initCharts() {
        if (typeof Chart === 'undefined') return;

        Chart.defaults.color = '#ead3b5'; // color-4
        Chart.defaults.borderColor = 'rgba(156, 195, 230, 0.4)'; // border-light
        Chart.defaults.font.family = "'Inter', sans-serif";
        Chart.defaults.font.weight = 500;

        const tCtx = document.getElementById('throughput-canvas').getContext('2d');
        throughputChart = new Chart(tCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Pings/sec',
                    data: [],
                    borderColor: '#9cc3e6', // color-3
                    backgroundColor: 'rgba(156, 195, 230, 0.15)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHitRadius: 10,
                    borderWidth: 3,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 200 },
                interaction: { intersect: false, mode: 'index' },
                scales: {
                    x: {
                        ticks: { maxTicksLimit: 6 },
                        grid: { color: 'rgba(156, 195, 230, 0.2)' },
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(156, 195, 230, 0.2)' },
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#16304a', // color-2
                        titleColor: '#f3efe6', // color-5
                        bodyColor: '#9cc3e6', // color-3
                        borderColor: '#9cc3e6',
                        borderWidth: 1,
                        titleFont: { family: "'Inter', sans-serif", weight: 500 },
                        bodyFont: { family: "'Inter', sans-serif", weight: 500 }
                    }
                }
            }
        });

        const gCtx = document.getElementById('gauge-canvas').getContext('2d');
        dedupGaugeChart = new Chart(gCtx, {
            type: 'doughnut',
            data: {
                labels: ['Duplicates Filtered', 'Clean Journeys'],
                datasets: [{
                    data: [0, 1],
                    backgroundColor: ['#0a1726', '#16304a'], // color-1, color-2
                    borderColor: '#16304a',
                    borderWidth: 3,
                    hoverOffset: 4,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '75%',
                animation: { duration: 400 },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#16304a',
                        titleColor: '#f3efe6',
                        bodyColor: '#ead3b5',
                        borderColor: '#9cc3e6',
                        borderWidth: 1,
                        callbacks: {
                            label: function(ctx) {
                                return ctx.label + ': ' + ctx.parsed.toFixed(1) + '%';
                            }
                        },
                        titleFont: { family: "'Inter', sans-serif", weight: 500 },
                        bodyFont: { family: "'Inter', sans-serif", weight: 500 }
                    }
                }
            }
        });
    }

    // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ POLLING â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    async function pollStats() {
        try {
            const res = await fetch('/api/stats');
            if (!res.ok) return;
            const d = await res.json();

            counters.totalPings.target   = d.total_raw_pings || 0;
            counters.totalJourneys.target = d.total_deduplicated_journeys || 0;
            counters.dedupRatio.target    = d.dedup_ratio || 0;
            counters.pps.target           = d.pings_per_second || 0;

            if (d.last_raw_count > 0 && d.last_journey_count >= 0) {
                document.getElementById('hero-pings-sub').textContent = 'last window: ' + d.last_raw_count.toLocaleString();
                document.getElementById('hero-journeys-sub').textContent = 'last run: ' + d.last_journey_count.toLocaleString();
            }

            if (dedupGaugeChart) {
                if (!d.last_dedup_run) {
                    dedupGaugeChart.data.datasets[0].data = [0, 1];
                    dedupGaugeChart.data.datasets[0].backgroundColor = ['#0a1726', '#16304a'];
                    document.getElementById('gauge-ratio').textContent = 'â€”';
                    document.getElementById('gauge-sublabel').textContent = 'Awaiting first dedup runâ€¦';
                } else {
                    const ratio = d.dedup_ratio || 0;
                    dedupGaugeChart.data.datasets[0].data = [ratio, Math.max(0.5, 100 - ratio)];
                    dedupGaugeChart.data.datasets[0].backgroundColor = ['#ead3b5', '#9cc3e6']; // Beige and light blue
                    document.getElementById('gauge-ratio').textContent = ratio.toFixed(1) + '%';
                    document.getElementById('gauge-sublabel').textContent =
                        (d.last_raw_count || 0).toLocaleString() + ' raw â†’ ' +
                        (d.last_journey_count || 0).toLocaleString() + ' journeys';
                }
                dedupGaugeChart.update();
            }

            const chaosActive = !!d.chaos_mode;

            document.getElementById('status-last-dedup').textContent = formatTime(d.last_dedup_run);

            if (d.last_dedup_run && d.last_dedup_run !== lastDedupRunAt) {
                if (lastDedupRunAt !== null) playKaChing();
                lastDedupRunAt = d.last_dedup_run;
            }

        } catch (e) {}
    }

    async function pollThroughput() {
        if (!throughputChart) return;
        try {
            const res = await fetch('/api/stats/throughput?buckets=30');
            if (!res.ok) return;
            const d = await res.json();
            if (!d.data || !Array.isArray(d.data)) return;

            const labels = d.data.map(function(point) {
                const t = new Date(point.timestamp);
                return String(t.getHours()).padStart(2, '0') + ':' +
                       String(t.getMinutes()).padStart(2, '0') + ':' +
                       String(t.getSeconds()).padStart(2, '0');
            });
            const values = d.data.map(function(point) { return point.pps; });

            throughputChart.data.labels = labels;
            throughputChart.data.datasets[0].data = values;
            throughputChart.update('none');
        } catch (e) {}
    }

    async function pollPlaza() {
        try {
            const res = await fetch('/api/stats/plaza');
            if (!res.ok) return;
            const d = await res.json();
            if (!d.plazas) return;

            currentPlazaData = d.plazas;
            renderPlazaTable();
            updateMapMarkers(d.plazas);
        } catch (e) {}
    }

    function renderPlazaTable() {
        const plazas = currentPlazaData;
        const tbody = document.getElementById('plaza-table-body');
        const entries = Object.values(plazas);

        if (entries.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No data yet - start a generator</td></tr>';
            return;
        }

        entries.sort(function(a, b) {
            const av = a[plazaSortKey], bv = b[plazaSortKey];
            if (typeof av === 'string') return plazaSortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
            return plazaSortAsc ? av - bv : bv - av;
        });

        let maxPings = 0;
        entries.forEach(function(e) { if (e.total_pings > maxPings) maxPings = e.total_pings; });

        tbody.innerHTML = entries.map(function(p) {
            const isBusiest = p.total_pings === maxPings && maxPings > 0;
            return '<tr class="' + (isBusiest ? 'busiest' : '') + '">' +
                '<td>' + escapeHtml(formatPlazaName(p.plaza_id)) + '</td>' +
                '<td>' + (p.total_pings || 0).toLocaleString() + '</td>' +
                '<td>' + (p.unique_tags || 0).toLocaleString() + '</td>' +
                '<td>' + (p.duplicates || 0).toLocaleString() + '</td>' +
                '<td><span class="region-badge">' + escapeHtml(p.region || 'â€”') + '</span></td>' +
                '</tr>';
        }).join('');
    }

    function sortPlazaTable(key) {
        if (plazaSortKey === key) {
            plazaSortAsc = !plazaSortAsc;
        } else {
            plazaSortKey = key;
            plazaSortAsc = false;
        }
        renderPlazaTable();
    }

    async function pollEvents() {
        try {
            const res = await fetch('/api/dedup/results');
            if (!res.ok) return;
            const d = await res.json();
            const feed = document.getElementById('event-feed');

            if (d.journeys && d.journeys.length > 0) {
                const items = d.journeys.slice(-30).reverse();
                feed.innerHTML = items.map(function(j) {
                    return '<div class="event-row">' +
                        '<span class="ev-tag">' + escapeHtml(j.tag_id) + '</span>' +
                        '<span>@</span>' +
                        '<span class="ev-plaza">' + escapeHtml(formatPlazaName(j.plaza_id)) + '</span>' +
                        '<span class="ev-rssi">RSSI: ' + (j.rssi_signal_strength != null ? j.rssi_signal_strength.toFixed(1) : 'â€”') + '</span>' +
                        '<span class="ev-dupes">' + (j.duplicate_count || 0) + ' dupes</span>' +
                        '<span class="ev-time">' + formatTime(j.ping_timestamp) + '</span>' +
                        '</div>';
                }).join('');
            }
        } catch (e) {}
    }

    async function pollHealth() {
        try {
            const res = await fetch('/api/health');
            if (!res.ok) { document.getElementById('status-health').textContent = 'ERROR'; return; }
            const d = await res.json();
            document.getElementById('status-backend').textContent = d.storage_backend || 'â€”';
            document.getElementById('status-worker').textContent = d.dedup_worker_running ? 'running' : 'stopped';
            document.getElementById('status-health').textContent = d.status || 'â€”';
        } catch (e) {
            document.getElementById('status-health').textContent = 'OFFLINE';
        }
    }

    // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ CONTROLS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    async function toggleChaos() {
        try { await fetch('/api/chaos', { method: 'POST' }); } catch (e) {}
    }

    async function triggerDedup() {
        const btn = document.getElementById('trigger-dedup-btn');
        btn.disabled = true;
        btn.textContent = 'Runningâ€¦';
        try {
            const res = await fetch('/api/dedup/trigger', { method: 'POST' });
            const d = await res.json();
            btn.textContent = 'DONE: ' + (d.raw_count || 0) + ' -> ' + (d.journey_count || 0);
            setTimeout(() => { btn.textContent = 'Trigger Dedup Now'; btn.disabled = false; }, 2000);
        } catch (e) {
            btn.textContent = 'Error';
            setTimeout(() => { btn.textContent = 'Trigger Dedup Now'; btn.disabled = false; }, 2000);
        }
    }

    function onSliderInput(val) { document.getElementById('slider-val').textContent = val + 's'; }
    const sendSliderUpdate = debounce(function(val) {
        fetch('/api/dedup/config', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ interval_seconds: parseInt(val, 10) })
        });
    }, 400);
    function onSliderChange(val) { sendSliderUpdate(val); }

    async function loadDedupConfig() {
        try {
            const res = await fetch('/api/dedup/config');
            if (!res.ok) return;
            const d = await res.json();
            if (d.interval_seconds != null) {
                const slider = document.getElementById('dedup-slider');
                const clamped = Math.max(10, Math.min(60, d.interval_seconds));
                slider.value = clamped;
                document.getElementById('slider-val').textContent = clamped + 's';
            }
        } catch (e) {}
    }

    // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ AUDIO â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    function playKaChing() {
        if (!soundEnabled || !audioCtx) return;
        try {
            const t = audioCtx.currentTime;
            [800, 1200].forEach((freq, i) => {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.connect(gain); gain.connect(audioCtx.destination);
                osc.type = 'sine';
                osc.frequency.setValueAtTime(freq, t + i * 0.08);
                gain.gain.setValueAtTime(0.08, t + i * 0.08);
                gain.gain.exponentialRampToValueAtTime(0.001, t + i * 0.08 + 0.25);
                osc.start(t + i * 0.08);
                osc.stop(t + i * 0.08 + 0.25);
            });
        } catch (e) {}
    }

    // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ INIT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    function updateClock() {
        const now = new Date();
        document.getElementById('live-clock').textContent =
            String(now.getHours()).padStart(2, '0') + ':' +
            String(now.getMinutes()).padStart(2, '0') + ':' +
            String(now.getSeconds()).padStart(2, '0');
    }

    function startPolling() {
        (function loopStats() { pollStats().finally(() => setTimeout(loopStats, POLL_STATS_MS)); })();
        (function loopThroughput() { pollThroughput().finally(() => setTimeout(loopThroughput, POLL_THROUGHPUT_MS)); })();
        (function loopPlaza() { pollPlaza().finally(() => setTimeout(loopPlaza, POLL_PLAZA_MS)); })();
        (function loopEvents() { pollEvents().finally(() => setTimeout(loopEvents, POLL_EVENTS_MS)); })();
        (function loopHealth() { pollHealth().finally(() => setTimeout(loopHealth, POLL_HEALTH_MS)); })();
    }

    function init() {
        counters.totalPings.el    = document.getElementById('hero-total-pings');
        counters.totalJourneys.el = document.getElementById('hero-total-journeys');
        counters.dedupRatio.el    = document.getElementById('hero-dedup-ratio');
        counters.pps.el           = document.getElementById('hero-pps');

        
        initMap();
        initCharts();
        loadDedupConfig();
        requestAnimationFrame(tickCounters);
        updateClock(); setInterval(updateClock, 1000);
        startPolling();
    }

    document.addEventListener('DOMContentLoaded', init);
    