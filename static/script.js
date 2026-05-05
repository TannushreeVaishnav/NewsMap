// ═══════════════════════════════════════════════════════════════
//  GEO-NEWS 3D GLOBE v2 — Advanced UX Edition
// ═══════════════════════════════════════════════════════════════

const clientCache = {};
let currentCategory = 'general';
let globeInstance = null;
let autoRotating = true;
let searchDebounceTimer = null;

const categoryConfig = {
    general:       { color: "#00e5ff", icon: "fa-globe",      label: "General" },
    politics:      { color: "#c10027", icon: "fa-landmark",   label: "Politics" },
    sports:        { color: "#ff9900", icon: "fa-futbol",     label: "Sports" },
    technology:    { color: "#ea80fc", icon: "fa-microchip",  label: "Technology" },
    entertainment: { color: "#ff4785", icon: "fa-film",       label: "Entertainment" },
    health:        { color: "#69f0ae", icon: "fa-heartbeat",  label: "Health" },
    business:      { color: "#2575ff", icon: "fa-briefcase",  label: "Business" },
    search:        { color: "#ffd700", icon: "fa-search",     label: "Search Results" }
};

// ── INITIALIZE 3D GLOBE ────────────────────────────────────────
function initGlobe() {
    const container = document.getElementById('globe-container');

    globeInstance = Globe()
        .globeImageUrl('//unpkg.com/three-globe/example/img/earth-night.jpg')
        .bumpImageUrl('//unpkg.com/three-globe/example/img/earth-topology.png')
        .backgroundImageUrl('//unpkg.com/three-globe/example/img/night-sky.png')
        .showAtmosphere(true)
        .atmosphereColor('#4a90d9')
        .atmosphereAltitude(0.18)
        .htmlElementsData([])
        .htmlLat(d => d.lat)
        .htmlLng(d => d.lng)
        .htmlAltitude(0.02)
        .htmlElement(d => {
            const el = document.createElement('div');
            el.className = 'globe-marker';
            const isBreaking = isBreakingNews(d.published_at);
            el.innerHTML = `
                ${isBreaking ? `<div class="pulse-ring" style="border-color:${d.color}"></div>` : ''}
                <div class="marker-pin" style="color:${d.color};font-size:30px;filter:drop-shadow(0 0 6px rgba(0,0,0,0.8));margin-top:-14px;transition:all 0.3s ease;">
                    <i class="fas fa-map-marker-alt"></i>
                </div>
                <div class="marker-label" style="background:${d.color}22;border-color:${d.color}55;color:${d.color};margin-top:-2px;">
                    ${d.locationShort}
                </div>`;
            el.onpointerdown = (e) => {
                e.stopPropagation();
                stopAutoRotate();
                showArticlePopup(d);
            };
            el.style.cursor = 'pointer';
            d.element = el;
            return el;
        })
        .labelsData([])
        .labelLat(d => d.lat)
        .labelLng(d => d.lng)
        .labelText(d => d.locationShort)
        .labelSize(1.0)
        .labelDotRadius(0.35)
        .labelDotOrientation(() => 'bottom')
        .labelColor(d => () => d.color)
        .labelResolution(3)
        .labelAltitude(0.005)
        (container);

    globeInstance.pointOfView({ lat: 20.5, lng: 78.9, altitude: 2.2 }, 0);
    startAutoRotate();

    let dragTimeout;
    container.addEventListener('pointerdown', () => {
        stopAutoRotate();
        clearTimeout(dragTimeout);
    });
    container.addEventListener('pointerup', () => {
        clearTimeout(dragTimeout);
        dragTimeout = setTimeout(startAutoRotate, 4000);
    });

    const onResize = () => {
        globeInstance.width(container.clientWidth);
        globeInstance.height(container.clientHeight);
    };
    window.addEventListener('resize', onResize);
    onResize();
}

// ── AUTO ROTATION ─────────────────────────────────────────────
let rotationRAF = null;
function startAutoRotate() {
    if (rotationRAF) return;
    autoRotating = true;
    function rotate() {
        if (!autoRotating || !globeInstance) return;
        const { lat, lng, altitude } = globeInstance.pointOfView();
        globeInstance.pointOfView({ lat, lng: lng + 0.15, altitude }, 0);
        rotationRAF = requestAnimationFrame(rotate);
    }
    rotationRAF = requestAnimationFrame(rotate);
}
function stopAutoRotate() {
    autoRotating = false;
    if (rotationRAF) { cancelAnimationFrame(rotationRAF); rotationRAF = null; }
}

// ── HELPERS ───────────────────────────────────────────────────
function timeAgo(dateStr) {
    if (!dateStr) return '';
    const now = new Date();
    const past = new Date(dateStr);
    const diffMs = now - past;
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return '<span class="badge-breaking">BREAKING</span>';
    if (diffMins < 30) return `<span class="badge-breaking">BREAKING</span> ${diffMins}m ago`;
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHrs = Math.floor(diffMins / 60);
    if (diffHrs < 24) return `${diffHrs}h ago`;
    return `${Math.floor(diffHrs / 24)}d ago`;
}

function isBreakingNews(dateStr) {
    if (!dateStr) return false;
    return (new Date() - new Date(dateStr)) < 30 * 60 * 1000;
}

function shortLocation(name) {
    if (!name) return 'Unknown';
    let parts = name.split(',').map(s => s.trim()).filter(s => s.length > 0 && !/^[\d\s\-]+$/.test(s));
    if (parts.length <= 2) return parts.join(', ');
    return parts.slice(-2).join(', ');
}

function sentimentColor(score) {
    if (score > 0.2) return '#69f0ae';   // positive → green
    if (score < -0.2) return '#ff5252';  // negative → red
    return '#ffa726';                     // neutral → amber
}


// ── HIGHLIGHT MARKER ──────────────────────────────────────────
function highlightMarker(point) {
    document.querySelectorAll('.globe-marker').forEach(m => m.classList.remove('active-marker'));
    if (point && point.element) point.element.classList.add('active-marker');
}

// ── SHOW ARTICLE POPUP ────────────────────────────────────────
function showArticlePopup(d) {
    highlightMarker(d);
    const popup = document.getElementById('article-popup');
    const imageWrap = document.getElementById('popup-image-wrap');

    document.getElementById('popup-link').style.display = '';
    document.getElementById('popup-title').textContent = d.title;
    document.getElementById('popup-summary').textContent = d.summary || 'No summary available.';
    document.getElementById('popup-source').innerHTML = `<i class="fas fa-newspaper"></i> ${d.source}`;
    document.getElementById('popup-time').innerHTML = `<i class="far fa-clock"></i> ${timeAgo(d.published_at)}`;
    document.getElementById('popup-location').innerHTML = (d.locationName && d.locationName !== 'Unknown')
        ? `<i class="fas fa-map-marker-alt"></i> ${d.locationName}`
        : `<i class="fas fa-question-circle"></i> Unlocated`;
    document.getElementById('popup-link').href = d.url;

    if (d.image_url) {
        imageWrap.innerHTML = `<img src="${d.image_url}" class="popup-img" onerror="this.parentElement.style.display='none'" alt="">`;
        imageWrap.style.display = 'block';
    } else {
        imageWrap.innerHTML = '';
        imageWrap.style.display = 'none';
    }

    popup.classList.remove('hidden');
    if (d.lat !== undefined && d.lng !== undefined) {
        globeInstance.pointOfView({ lat: d.lat, lng: d.lng, altitude: 1.2 }, 800);
    }
}


document.getElementById('popup-close').addEventListener('click', () => {
    document.getElementById('article-popup').classList.add('hidden');
    highlightMarker(null);
    startAutoRotate();
});

// ── NUKE SCENE ────────────────────────────────────────────
function nukeSceneHtmlObjects() {
    const scene = globeInstance.scene();
    const toRemove = [];
    scene.traverse(obj => {
        if (obj.isCSS2DObject || (obj.element && obj.element instanceof HTMLElement && obj.type === 'Object3D')) {
            toRemove.push(obj);
        }
    });
    toRemove.forEach(obj => {
        if (obj.parent) obj.parent.remove(obj);
        if (obj.element && obj.element.parentNode) obj.element.parentNode.removeChild(obj.element);
    });
    document.querySelectorAll('.globe-marker').forEach(el => el.remove());
}

// ── RENDER NEWS DATA ────────────────────────────────────────────
function renderNewsData(data, category) {
    const catConfig = categoryConfig[category] || categoryConfig['general'];
    currentCategory = category;

    document.getElementById('news-sidebar').classList.remove('sidebar-hidden');
    document.getElementById('sidebar-open-btn').classList.add('hidden');
    resizeGlobe();

    globeInstance.htmlElementsData([]);
    globeInstance.labelsData([]);
    nukeSceneHtmlObjects();

    document.getElementById('sidebar-cat-icon').className = `fas ${catConfig.icon}`;
    document.getElementById('sidebar-cat-icon').style.color = catConfig.color;
    document.getElementById('sidebar-cat-name').textContent = `${catConfig.label} News`;

    const globeArticlesEl = document.getElementById('globe-articles');
    const unlocArticlesEl = document.getElementById('unloc-articles');
    globeArticlesEl.innerHTML = '';
    unlocArticlesEl.innerHTML = '';
    document.getElementById('article-popup').classList.add('hidden');

    if (!data || data.status !== 'success' || !data.articles || data.articles.length === 0) {
        globeArticlesEl.innerHTML = `<div class="sidebar-empty"><i class="fas fa-satellite-dish"></i><p>No articles found</p><span>Try another category or check later</span></div>`;
        document.getElementById('section-sidebar').style.display = 'none';
        updateCounts(0, 0);
        return;
    }

    const rawGlobePoints = [];
    const locatedArticles = [];   // has location → globe + sidebar top
    const unlocatedArticles = []; // no location → sidebar bottom only

    data.articles.forEach((article, index) => {
        const loc = article.location;
        if (loc && loc.lat && loc.lon) {
            const locName = loc.name || 'Unknown';
            const locShort = shortLocation(locName);
            const point = {
                lat: loc.lat,
                lng: loc.lon,
                color: catConfig.color,
                title: article.title,
                summary: article.summary,
                source: article.source || 'Unknown',
                published_at: article.published_at,
                image_url: article.image_url,
                url: article.url,
                locationName: locShort,
                locationShort: locShort.split(',')[0],
                sentiment_score: article.sentiment_score || 0.0,
                cluster_id: article.cluster_id || `solo_${index}`,
                index, category
            };
            rawGlobePoints.push(point);
            locatedArticles.push({ article, point, index });
        } else {
            unlocatedArticles.push({ article, index });
        }
    });

    // Render individual pins on globe (no clustering)
    requestAnimationFrame(() => {
        nukeSceneHtmlObjects();
        globeInstance.htmlElementsData(rawGlobePoints);
        globeInstance.labelsData(rawGlobePoints);
    });

    // ── Sidebar section 1: "On the Globe" ──
    // Group located articles by cluster_id for "N sources" badges
    const clusterGroups = {};
    locatedArticles.forEach(({ article, point, index }) => {
        const cid = article.cluster_id || `solo_${index}`;
        if (!clusterGroups[cid]) clusterGroups[cid] = [];
        clusterGroups[cid].push({ article, point });
    });

    if (Object.keys(clusterGroups).length === 0) {
        globeArticlesEl.innerHTML = `<div class="sidebar-empty-sm"><i class="fas fa-map-marker-alt"></i> No geo-located articles for this category</div>`;
    } else {
        Object.values(clusterGroups).forEach(group => {
            const card = createSidebarCard(group[0].article, catConfig, true, group.length);
            card.addEventListener('click', (e) => {
                if (e.target.closest('.read-more-btn')) return;
                stopAutoRotate();
                highlightCard(card);
                showArticlePopup(group[0].point);
            });
            globeArticlesEl.appendChild(card);
        });
    }

    // ── Sidebar section 2: "Latest Headlines" — ALL articles as cards ──
    document.getElementById('section-sidebar').style.display = 'block';
    data.articles.forEach((article, index) => {
        const hasLoc = !!(article.location && article.location.lat && article.location.lon);
        // Find matching globe point for click-to-fly
        const matchedPoint = rawGlobePoints.find(p => p.url === article.url);

        const card = createSidebarCard(article, catConfig, hasLoc, 1);
        card.addEventListener('click', (e) => {
            if (e.target.closest('.read-more-btn')) return;
            highlightCard(card);
            if (matchedPoint) {
                stopAutoRotate();
                showArticlePopup(matchedPoint);
            } else {
                showArticlePopup({
                    title: article.title, summary: article.summary,
                    source: article.source || 'Unknown',
                    published_at: article.published_at,
                    image_url: article.image_url,
                    url: article.url,
                    locationName: 'Unknown', category
                });
            }
        });
        unlocArticlesEl.appendChild(card);
    });

    updateCounts(locatedArticles.length, data.articles.length);

    if (rawGlobePoints.length > 0) {
        globeInstance.pointOfView({ lat: rawGlobePoints[0].lat, lng: rawGlobePoints[0].lng, altitude: 2.0 }, 1000);
    }

    buildTicker(data.articles);
}

// ── CREATE SIDEBAR CARD ───────────────────────────────────────
function createSidebarCard(article, catConfig, hasLocation, sourceCount = 1, group = null) {
    const card = document.createElement('div');
    card.className = `sidebar-card ${hasLocation ? 'has-location' : 'no-location'}`;

    const sentiment = article.sentiment_score || 0.0;
    const sentColor = sentimentColor(sentiment);
    const relTime = timeAgo(article.published_at);
    const summaryPreview = article.summary
        ? (article.summary.length > 100 ? article.summary.substring(0, 100) + '...' : article.summary) : '';
    const locationHtml = hasLocation
        ? `<span class="loc-badge loc-found"><i class="fas fa-map-marker-alt"></i> ${shortLocation(article.location ? article.location.name : '')}</span>`
        : `<span class="loc-badge loc-none"><i class="fas fa-question-circle"></i> No location</span>`;
    const clusterBadge = (sourceCount > 1)
        ? `<span class="cluster-badge"><i class="fas fa-layer-group"></i> ${sourceCount} sources</span>` : '';

    card.innerHTML = `
        <div class="card-inner" style="border-left:3px solid ${catConfig.color}">
            <div class="sentiment-bar" style="background:${sentColor}" title="Sentiment: ${sentiment > 0.2 ? 'Positive' : sentiment < -0.2 ? 'Negative' : 'Neutral'}"></div>
            ${article.image_url ? `<div class="card-img-wrap"><img src="${article.image_url}" class="card-img" onerror="this.parentElement.style.display='none'" alt=""></div>` : ''}
            <div class="card-body">
                <h4 class="card-title">${article.title}</h4>
                ${summaryPreview ? `<p class="card-summary">${summaryPreview}</p>` : ''}
                <div class="card-meta">
                    <span class="card-source">${article.source || 'Unknown'}</span>
                    ${relTime ? `<span class="card-time">${relTime}</span>` : ''}
                </div>
                <div class="card-actions">
                    ${locationHtml}
                    ${clusterBadge}
                    <a href="${article.url}" target="_blank" class="read-more-btn">Read <i class="fas fa-external-link-alt"></i></a>
                </div>
            </div>
        </div>`;
    return card;
}

function highlightCard(card) {
    document.querySelectorAll('.sidebar-card').forEach(c => c.classList.remove('active-card'));
    card.classList.add('active-card');
    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function updateCounts(globe, sidebar) {
    document.querySelector('#globe-pin-count span').textContent = globe;
    document.querySelector('#sidebar-only-count span').textContent = sidebar;
    document.getElementById('sidebar-badge').textContent = globe + sidebar;
}

// ── NEWS TICKER ───────────────────────────────────────────────
function buildTicker(articles) {
    const track = document.getElementById('ticker-track');
    if (!articles || articles.length === 0) return;
    const items = [...articles, ...articles].map(a =>
        `<a class="ticker-item" href="${a.url}" target="_blank" rel="noopener">
            ${a.source ? `<strong style="color:#4fc3f7">${a.source}</strong>` : ''}
            ${a.title}
        </a>`
    ).join('');
    track.innerHTML = items;
    const trackWidth = track.scrollWidth / 2;
    track.style.animationDuration = `${Math.max(40, trackWidth / 8)}s`;
}

// ── FETCH NEWS ────────────────────────────────────────────────
let pendingCategory = null;

function fetchNewsData(category) {
    pendingCategory = category;

    if (clientCache[category] && clientCache[category].articles && clientCache[category].articles.length > 0) {
        renderNewsData(clientCache[category], category);
        return;
    }

    document.getElementById('loading').classList.remove('hidden');

    fetch(`/api/news?category=${category}`)
        .then(r => r.json())
        .then(data => {
            if (!data) return;
            if (pendingCategory === category) document.getElementById('loading').classList.add('hidden');
            if (data.status === 'success') {
                if (data.articles && data.articles.length > 0) clientCache[category] = data;
                if (pendingCategory === category) renderNewsData(data, category);
            } else {
                if (pendingCategory === category) console.error('API Error:', data.error);
            }
        })
        .catch(err => {
            if (pendingCategory === category) {
                document.getElementById('loading').classList.add('hidden');
                console.error('Fetch error:', err);
            }
        });
}

// ── SIDEBAR TOGGLE ────────────────────────────────────────────
function syncSearchBarWidth() {
    const bar = document.getElementById('bottom-search-bar');
    const sidebarHidden = document.getElementById('news-sidebar').classList.contains('sidebar-hidden');
    bar.classList.toggle('sidebar-hidden-mode', sidebarHidden);
}

document.getElementById('sidebar-collapse-btn').addEventListener('click', () => {
    document.getElementById('news-sidebar').classList.add('sidebar-hidden');
    document.getElementById('sidebar-open-btn').classList.remove('hidden');
    resizeGlobe(); syncSearchBarWidth();
});

document.getElementById('sidebar-open-btn').addEventListener('click', () => {
    document.getElementById('news-sidebar').classList.remove('sidebar-hidden');
    document.getElementById('sidebar-open-btn').classList.add('hidden');
    resizeGlobe(); syncSearchBarWidth();
});

function resizeGlobe() {
    setTimeout(() => {
        const c = document.getElementById('globe-container');
        if (globeInstance) {
            globeInstance.width(c.clientWidth);
            globeInstance.height(c.clientHeight);
        }
    }, 350);
}

// ── CATEGORY BUTTONS ──────────────────────────────────────────
document.querySelectorAll('.filter-btn').forEach(button => {
    button.addEventListener('click', (e) => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        fetchNewsData(e.currentTarget.getAttribute('data-category'));
    });
});

// ── SEARCH ────────────────────────────────────────────────────
function performSearch(query) {
    if (!query || query.length < 2) return;
    currentCategory = 'search';
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('loading').classList.remove('hidden');

    // Save to history
    saveSearchHistory(query);
    renderSearchHistory();

    fetch(`/api/search?q=${encodeURIComponent(query)}`)
        .then(r => r.json())
        .then(data => {
            document.getElementById('loading').classList.add('hidden');
            if (data.status === 'success') {
                renderNewsData(data, 'search');
            } else {
                console.error('Search Error:', data.error);
            }
        })
        .catch(err => {
            document.getElementById('loading').classList.add('hidden');
            console.error('Search error:', err);
        });
}

// ── SEARCH HISTORY ────────────────────────────────────────────
function saveSearchHistory(query) {
    let history = JSON.parse(localStorage.getItem('geonews_search_history') || '[]');
    history = [query, ...history.filter(q => q !== query)].slice(0, 6);
    localStorage.setItem('geonews_search_history', JSON.stringify(history));
}

function renderSearchHistory() {
    const container = document.getElementById('search-history-chips');
    if (!container) return;
    const history = JSON.parse(localStorage.getItem('geonews_search_history') || '[]');
    container.innerHTML = history.map(q =>
        `<button class="history-chip" onclick="searchInput.value='${q.replace(/'/g,"\\'")}'; performSearch('${q.replace(/'/g,"\\'")}');">${q}</button>`
    ).join('');
    container.style.display = history.length > 0 ? 'flex' : 'none';
}

const searchInput = document.getElementById('news-search-input');
const clearBtn = document.getElementById('search-clear-btn');
const submitBtn = document.getElementById('search-submit-btn');

if (searchInput) {
    // Debounced search-as-you-type (300ms)
    searchInput.addEventListener('input', () => {
        clearBtn.classList.toggle('hidden', searchInput.value.length === 0);
        clearTimeout(searchDebounceTimer);
        const q = searchInput.value.trim();
        if (q.length >= 3) {
            searchDebounceTimer = setTimeout(() => performSearch(q), 300);
        }
    });
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            clearTimeout(searchDebounceTimer);
            performSearch(searchInput.value.trim());
        }
    });
    searchInput.addEventListener('focus', renderSearchHistory);
}
if (clearBtn) {
    clearBtn.addEventListener('click', () => {
        searchInput.value = '';
        clearBtn.classList.add('hidden');
        searchInput.focus();
    });
}
if (submitBtn) {
    submitBtn.addEventListener('click', () => {
        clearTimeout(searchDebounceTimer);
        performSearch(searchInput.value.trim());
    });
}

// ── INIT ──────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
    initGlobe();
    fetchNewsData('general');
    renderSearchHistory();
});
