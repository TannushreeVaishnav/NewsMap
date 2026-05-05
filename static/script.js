// ═══════════════════════════════════════════════════════════════
//  GEO-NEWS 3D GLOBE — Globe.gl powered dark globe
// ═══════════════════════════════════════════════════════════════

const clientCache = {};
let currentCategory = 'general';
let globeInstance = null;
let autoRotating = true;   // earth auto-rotation flag

const categoryConfig = {
    general:       { color: "#00e5ff", icon: "fa-globe",      label: "General" },
    politics:      { color: "#c10027", icon: "fa-landmark",   label: "Politics" },
    sports:        { color: "#ff9900", icon: "fa-futbol",      label: "Sports" },
    technology:    { color: "#ea80fc", icon: "fa-microchip",  label: "Technology" },
    entertainment: { color: "#bd0948", icon: "fa-film",        label: "Entertainment" },
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

        // ── HTML MARKERS ──
        .htmlElementsData([])
        .htmlLat(d => d.lat)
        .htmlLng(d => d.lng)
        .htmlAltitude(0.02)
        .htmlElement(d => {
            const el = document.createElement('div');
            el.className = 'globe-marker';
            el.innerHTML = `
                <div class="marker-pin" style="color:${d.color};font-size:30px;filter:drop-shadow(0 0 6px rgba(0,0,0,0.8));margin-top:-14px;transition:all 0.3s ease;">
                    <i class="fas fa-map-marker-alt"></i>
                </div>
                <div class="marker-label" style="background:${d.color}22;border-color:${d.color}55;color:${d.color};margin-top:-2px;">
                    ${d.locationShort}
                </div>
            `;
            el.onpointerdown = (e) => {
                e.stopPropagation();
                stopAutoRotate();
                showArticlePopup(d);
            };
            el.style.cursor = 'pointer';
            d.element = el;
            return el;
        })

        // ── LOCATION LABELS ──
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

    // Initial view
    globeInstance.pointOfView({ lat: 20.5, lng: 78.9, altitude: 2.2 }, 0);

    // ── START AUTO-ROTATION ──
    startAutoRotate();

    // Stop rotation on user drag, restart after 4s idle
    let dragTimeout;
    container.addEventListener('pointerdown', () => {
        stopAutoRotate();
        clearTimeout(dragTimeout);
    });
    container.addEventListener('pointerup', () => {
        clearTimeout(dragTimeout);
        dragTimeout = setTimeout(startAutoRotate, 4000);
    });

    // Resize
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
    if (rotationRAF) {
        cancelAnimationFrame(rotationRAF);
        rotationRAF = null;
    }
}

// ── TIME AGO ──────────────────────────────────────────────────
function timeAgo(dateStr) {
    if (!dateStr) return '';
    const now = new Date();
    const past = new Date(dateStr);
    const diffMs = now - past;
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHrs = Math.floor(diffMins / 60);
    if (diffHrs < 24) return `${diffHrs}h ago`;
    return `${Math.floor(diffHrs / 24)}d ago`;
}

// ── SHORT LOCATION ────────────────────────────────────────────
function shortLocation(name) {
    if (!name) return 'Unknown';
    let parts = name.split(',').map(s => s.trim()).filter(s => s.length > 0 && !/^[\d\s\-]+$/.test(s));
    if (parts.length <= 2) return parts.join(', ');
    return parts.slice(-2).join(', ');
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

// ── NUKE SCENE HTML OBJECTS ───────────────────────────────────
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

// ── RENDER NEWS DATA ──────────────────────────────────────────
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

    const globePoints = [];
    const locatedArticles = [];
    const unlocatedArticles = [];

    data.articles.forEach((article, index) => {
        if (article.location && article.location.lat && article.location.lon) {
            const locName = article.location.name || 'Unknown';
            const locShort = shortLocation(locName);
            const point = {
                lat: article.location.lat,
                lng: article.location.lon,
                color: catConfig.color,
                title: article.title,
                summary: article.summary,
                source: article.source || 'Unknown',
                published_at: article.published_at,
                image_url: article.image_url,
                url: article.url,
                locationName: locShort,
                locationShort: locShort.split(',')[0],
                index, category
            };
            globePoints.push(point);
            locatedArticles.push({ article, point, index });
        } else {
            unlocatedArticles.push({ article, index });
        }
    });

    requestAnimationFrame(() => {
        nukeSceneHtmlObjects();
        globeInstance.htmlElementsData(globePoints);
        globeInstance.labelsData(globePoints);
    });

    // ── On the Globe section ──
    if (locatedArticles.length === 0) {
        globeArticlesEl.innerHTML = `<div class="sidebar-empty-sm"><i class="fas fa-map-marker-alt"></i> No geo-located articles for this category</div>`;
    } else {
        locatedArticles.forEach(({ article, point }) => {
            const card = createSidebarCard(article, catConfig, true);
            card.addEventListener('click', (e) => {
                if (e.target.closest('.read-more-btn')) return;
                stopAutoRotate();
                highlightCard(card);
                showArticlePopup(point);
            });
            globeArticlesEl.appendChild(card);
        });
    }

    // ── More Headlines section ──
    if (unlocatedArticles.length === 0) {
        document.getElementById('section-sidebar').style.display = 'none';
    } else {
        document.getElementById('section-sidebar').style.display = 'block';
        unlocatedArticles.forEach(({ article }) => {
            const card = createSidebarCard(article, catConfig, false);
            const pseudoPoint = {
                title: article.title,
                summary: article.summary,
                source: article.source || 'Unknown',
                published_at: article.published_at,
                image_url: article.image_url,
                url: article.url,
                locationName: 'Unknown',
                category
            };
            card.addEventListener('click', (e) => {
                if (e.target.closest('.read-more-btn')) return;
                highlightCard(card);
                showArticlePopup(pseudoPoint);
            });
            unlocArticlesEl.appendChild(card);
        });
    }

    updateCounts(locatedArticles.length, unlocatedArticles.length);

    // Fly to first located point
    if (globePoints.length > 0) {
        globeInstance.pointOfView({ lat: globePoints[0].lat, lng: globePoints[0].lng, altitude: 2.0 }, 1000);
        if (category === 'search') {
            setTimeout(() => {
                showArticlePopup(globePoints[0]);
                const firstCard = globeArticlesEl.querySelector('.sidebar-card');
                if (firstCard) highlightCard(firstCard);
            }, 1000);
        }
    } else if (category === 'search' && unlocatedArticles.length > 0) {
        const a = unlocatedArticles[0].article;
        showArticlePopup({ title: a.title, summary: a.summary, source: a.source || 'Unknown', published_at: a.published_at, image_url: a.image_url, url: a.url, locationName: 'Unknown', category });
        const firstCard = unlocArticlesEl.querySelector('.sidebar-card');
        if (firstCard) highlightCard(firstCard);
    }

    // Update ticker with fresh headlines
    buildTicker(data.articles);
}

// ── CREATE SIDEBAR CARD ───────────────────────────────────────
function createSidebarCard(article, catConfig, hasLocation) {
    const card = document.createElement('div');
    card.className = `sidebar-card ${hasLocation ? 'has-location' : 'no-location'}`;

    const relTime = timeAgo(article.published_at);
    const summaryPreview = article.summary
        ? (article.summary.length > 100 ? article.summary.substring(0, 100) + '...' : article.summary)
        : '';
    const locationHtml = hasLocation
        ? `<span class="loc-badge loc-found"><i class="fas fa-map-marker-alt"></i> ${shortLocation(article.location.name)}</span>`
        : `<span class="loc-badge loc-none"><i class="fas fa-question-circle"></i> No location</span>`;

    card.innerHTML = `
        <div class="card-inner" style="border-left:3px solid ${catConfig.color}">
            ${article.image_url ? `<div class="card-img-wrap"><img src="${article.image_url}" class="card-img" onerror="this.parentElement.style.display='none'" alt=""></div>` : ''}
            <div class="card-body">
                <h4 class="card-title">${article.title}</h4>
                ${summaryPreview ? `<p class="card-summary">${summaryPreview}</p>` : ''}
                <div class="card-meta">
                    <span class="card-source">${article.source || 'Unknown'}</span>
                    ${relTime ? `<span class="card-time"><i class="far fa-clock"></i> ${relTime}</span>` : ''}
                </div>
                <div class="card-actions">
                    ${locationHtml}
                    <a href="${article.url}" target="_blank" class="read-more-btn">Read <i class="fas fa-external-link-alt"></i></a>
                </div>
            </div>
        </div>
    `;
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

    // Doubled for seamless infinite scroll; items are clickable <a> links
    const items = [...articles, ...articles].map(a =>
        `<a class="ticker-item" href="${a.url}" target="_blank" rel="noopener" title="${a.title.replace(/"/g,'&quot;')}">
            ${a.source ? `<strong style="color:#4fc3f7">${a.source}</strong>` : ''}
            ${a.title}
        </a>`
    ).join('');

    track.innerHTML = items;
    const trackWidth = track.scrollWidth / 2;
    const speed = Math.max(40, trackWidth / 8);
    track.style.animationDuration = `${speed}s`;
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
            if (pendingCategory === category) document.getElementById('loading').classList.add('hidden');
            if (data.status === 'success') {
                if (data.articles && data.articles.length > 0) clientCache[category] = data;
                if (pendingCategory === category) renderNewsData(data, category);
            } else {
                if (pendingCategory === category) alert('API Error: ' + (data.error || 'Unknown'));
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
    resizeGlobe();
    syncSearchBarWidth();
});

document.getElementById('sidebar-open-btn').addEventListener('click', () => {
    document.getElementById('news-sidebar').classList.remove('sidebar-hidden');
    document.getElementById('sidebar-open-btn').classList.add('hidden');
    resizeGlobe();
    syncSearchBarWidth();
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
    if (!query) return;
    currentCategory = 'search';
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('loading').classList.remove('hidden');

    fetch(`/api/search?q=${encodeURIComponent(query)}`)
        .then(r => r.json())
        .then(data => {
            document.getElementById('loading').classList.add('hidden');
            if (data.status === 'success') {
                renderNewsData(data, 'search');
            } else {
                alert('Search Error: ' + (data.error || 'Unknown'));
            }
        })
        .catch(err => {
            document.getElementById('loading').classList.add('hidden');
            console.error('Search error:', err);
        });
}

const searchInput = document.getElementById('news-search-input');
const clearBtn = document.getElementById('search-clear-btn');
const submitBtn = document.getElementById('search-submit-btn');

if (searchInput) {
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch(searchInput.value.trim());
    });
    searchInput.addEventListener('input', () => {
        clearBtn.classList.toggle('hidden', searchInput.value.length === 0);
    });
}
if (clearBtn) {
    clearBtn.addEventListener('click', () => {
        searchInput.value = '';
        clearBtn.classList.add('hidden');
        searchInput.focus();
    });
}
if (submitBtn) {
    submitBtn.addEventListener('click', () => performSearch(searchInput.value.trim()));
}

// ── INIT ──────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
    initGlobe();
    // Fetch live general news immediately on load
    fetchNewsData('general');
});
