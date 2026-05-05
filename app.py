import os
import time
import logging
import threading
import hashlib
import json
import requests
from datetime import datetime, timedelta, date
from collections import defaultdict
from urllib.parse import urlparse

from flask import Flask, jsonify, request, render_template, make_response
from flask_cors import CORS
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from apscheduler.schedulers.background import BackgroundScheduler

import db
from metrics import APP_METRICS, APP_START_TIME

# ─── LOGGING ────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ─── ENVIRONMENT ─────────────────────────────────────────────
load_dotenv()
WORLD_NEWS_API_KEY = os.getenv("WORLD_NEWS_API")

# ─── FLASK ───────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# ─── VADER SENTIMENT ─────────────────────────────────────────
try:
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
    import nltk
    nltk.download('vader_lexicon', quiet=True)
    _sia = SentimentIntensityAnalyzer()
    def get_sentiment(text: str) -> float:
        """Return compound sentiment score in [-1.0, 1.0]."""
        if not text:
            return 0.0
        return _sia.polarity_scores(text)['compound']
    logger.info("VADER sentiment analyzer loaded")
except Exception as e:
    logger.warning(f"VADER unavailable: {e}. Sentiment will default to 0.0")
    def get_sentiment(text: str) -> float:
        return 0.0

# ─── TF-IDF STORY CLUSTERING ─────────────────────────────────
def cluster_articles(articles: list, threshold: float = 0.35) -> list:
    """
    Group articles by topic similarity using TF-IDF + cosine similarity.
    Assigns a cluster_id to each article. Articles in the same cluster
    are covering the same story from different sources.
    """
    if len(articles) < 2:
        for a in articles:
            a['cluster_id'] = a.get('url', str(id(a)))[:40]
        return articles

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        corpus = [f"{a.get('title','')} {a.get('summary','')}" for a in articles]
        vectorizer = TfidfVectorizer(stop_words='english', max_features=3000)
        matrix = vectorizer.fit_transform(corpus)
        sim = cosine_similarity(matrix)

        visited = [False] * len(articles)
        cluster_map = {}  # article_index -> cluster_id

        cluster_num = 0
        for i in range(len(articles)):
            if visited[i]:
                continue
            cluster_id = f"c{cluster_num}"
            cluster_num += 1
            cluster_map[i] = cluster_id
            visited[i] = True
            for j in range(i + 1, len(articles)):
                if not visited[j] and sim[i, j] >= threshold:
                    cluster_map[j] = cluster_id
                    visited[j] = True

        for i, art in enumerate(articles):
            art['cluster_id'] = cluster_map.get(i, f"c{i}")

    except ImportError:
        for i, art in enumerate(articles):
            art['cluster_id'] = f"c{i}"

    return articles


# ─── CONFIGURATION ──────────────────────────────────────────
REFRESH_INTERVAL_HOURS = 4
KEEP_DAYS = 3
ALL_CATEGORIES = ['general', 'politics', 'sports', 'technology', 'entertainment', 'health', 'business']

CATEGORY_KEYWORDS = {
    'general':       'world news today',
    'politics':      'politics election government parliament',
    'sports':        'sports cricket football IPL olympics',
    'technology':    'technology AI software startup',
    'entertainment': 'entertainment movies celebrity music',
    'health':        'health medical disease WHO healthcare',
    'business':      'business economy market finance stock',
}

# ─── SOURCE → LOCATION FALLBACK MAP ─────────────────────────
SOURCE_LOCATION_MAP = {
    "times of india":       {"name": "India", "lat": 20.5937, "lon": 78.9629},
    "the times of india":   {"name": "India", "lat": 20.5937, "lon": 78.9629},
    "hindustan times":      {"name": "New Delhi, India", "lat": 28.6139, "lon": 77.2090},
    "ndtv":                 {"name": "New Delhi, India", "lat": 28.6139, "lon": 77.2090},
    "india today":          {"name": "New Delhi, India", "lat": 28.6139, "lon": 77.2090},
    "the hindu":            {"name": "Chennai, India", "lat": 13.0827, "lon": 80.2707},
    "indian express":       {"name": "India", "lat": 20.5937, "lon": 78.9629},
    "the indian express":   {"name": "India", "lat": 20.5937, "lon": 78.9629},
    "zee news":             {"name": "India", "lat": 20.5937, "lon": 78.9629},
    "republic world":       {"name": "Mumbai, India", "lat": 19.0760, "lon": 72.8777},
    "mint":                 {"name": "Mumbai, India", "lat": 19.0760, "lon": 72.8777},
    "livemint":             {"name": "Mumbai, India", "lat": 19.0760, "lon": 72.8777},
    "economic times":       {"name": "Mumbai, India", "lat": 19.0760, "lon": 72.8777},
    "the economic times":   {"name": "Mumbai, India", "lat": 19.0760, "lon": 72.8777},
    "business standard":    {"name": "Mumbai, India", "lat": 19.0760, "lon": 72.8777},
    "moneycontrol":         {"name": "Mumbai, India", "lat": 19.0760, "lon": 72.8777},
    "scroll.in":            {"name": "India", "lat": 20.5937, "lon": 78.9629},
    "the wire":             {"name": "New Delhi, India", "lat": 28.6139, "lon": 77.2090},
    "firstpost":            {"name": "India", "lat": 20.5937, "lon": 78.9629},
    "deccan herald":        {"name": "Bengaluru, India", "lat": 12.9716, "lon": 77.5946},
    "the quint":            {"name": "India", "lat": 20.5937, "lon": 78.9629},
    "news18":               {"name": "India", "lat": 20.5937, "lon": 78.9629},
    "aaj tak":              {"name": "New Delhi, India", "lat": 28.6139, "lon": 77.2090},
    "dna india":            {"name": "India", "lat": 20.5937, "lon": 78.9629},
    "outlook india":        {"name": "New Delhi, India", "lat": 28.6139, "lon": 77.2090},
    "the print":            {"name": "New Delhi, India", "lat": 28.6139, "lon": 77.2090},
    "wion":                 {"name": "New Delhi, India", "lat": 28.6139, "lon": 77.2090},
    "ani":                  {"name": "New Delhi, India", "lat": 28.6139, "lon": 77.2090},
    "pti":                  {"name": "New Delhi, India", "lat": 28.6139, "lon": 77.2090},
    "bbc":                  {"name": "London, UK", "lat": 51.5074, "lon": -0.1278},
    "bbc news":             {"name": "London, UK", "lat": 51.5074, "lon": -0.1278},
    "cnn":                  {"name": "Atlanta, USA", "lat": 33.7490, "lon": -84.3880},
    "reuters":              {"name": "London, UK", "lat": 51.5074, "lon": -0.1278},
    "al jazeera":           {"name": "Doha, Qatar", "lat": 25.2854, "lon": 51.5310},
    "the guardian":         {"name": "London, UK", "lat": 51.5074, "lon": -0.1278},
    "associated press":     {"name": "New York, USA", "lat": 40.7128, "lon": -74.0060},
    "the washington post":  {"name": "Washington DC, USA", "lat": 38.9072, "lon": -77.0369},
    "new york times":       {"name": "New York, USA", "lat": 40.7128, "lon": -74.0060},
    "bloomberg":            {"name": "New York, USA", "lat": 40.7128, "lon": -74.0060},
    "cnbc":                 {"name": "New Jersey, USA", "lat": 40.7357, "lon": -74.1724},
    "forbes":               {"name": "New York, USA", "lat": 40.7128, "lon": -74.0060},
    "bollywood hungama":    {"name": "Mumbai, India", "lat": 19.0760, "lon": 72.8777},
    "pinkvilla":            {"name": "Mumbai, India", "lat": 19.0760, "lon": 72.8777},
    "koimoi":               {"name": "Mumbai, India", "lat": 19.0760, "lon": 72.8777},
    "cricbuzz":             {"name": "Bengaluru, India", "lat": 12.9716, "lon": 77.5946},
    "sportskeeda":          {"name": "Bengaluru, India", "lat": 12.9716, "lon": 77.5946},
    "espncricinfo":         {"name": "Mumbai, India", "lat": 19.0760, "lon": 72.8777},
    "healthline":           {"name": "New York, USA", "lat": 40.7128, "lon": -74.0060},
    "medical news today":   {"name": "Brighton, UK", "lat": 50.8225, "lon": -0.1371},
    "webmd":                {"name": "Atlanta, USA", "lat": 33.7490, "lon": -84.3880},
    "cbssports.com":        {"name": "USA", "lat": 37.0902, "lon": -95.7129},
    "espn":                 {"name": "USA", "lat": 37.0902, "lon": -95.7129},
}


# TLD → country location fallback (for domains not in the explicit map)
TLD_COUNTRY_MAP = {
    ".co.uk": {"name": "United Kingdom", "lat": 51.5074, "lon": -0.1278},
    ".uk":    {"name": "United Kingdom", "lat": 51.5074, "lon": -0.1278},
    ".in":    {"name": "India", "lat": 20.5937, "lon": 78.9629},
    ".au":    {"name": "Australia", "lat": -25.2744, "lon": 133.7751},
    ".ca":    {"name": "Canada", "lat": 56.1304, "lon": -106.3468},
    ".de":    {"name": "Germany", "lat": 51.1657, "lon": 10.4515},
    ".fr":    {"name": "France", "lat": 46.2276, "lon": 2.2137},
    ".jp":    {"name": "Japan", "lat": 36.2048, "lon": 138.2529},
    ".cn":    {"name": "China", "lat": 35.8617, "lon": 104.1954},
    ".ru":    {"name": "Russia", "lat": 61.5240, "lon": 105.3188},
    ".br":    {"name": "Brazil", "lat": -14.2350, "lon": -51.9253},
    ".za":    {"name": "South Africa", "lat": -30.5595, "lon": 22.9375},
    ".pk":    {"name": "Pakistan", "lat": 30.3753, "lon": 69.3451},
    ".bd":    {"name": "Bangladesh", "lat": 23.6850, "lon": 90.3563},
    ".sg":    {"name": "Singapore", "lat": 1.3521, "lon": 103.8198},
    ".ae":    {"name": "UAE", "lat": 23.4241, "lon": 53.8478},
    ".il":    {"name": "Israel", "lat": 31.0461, "lon": 34.8516},
    ".ng":    {"name": "Nigeria", "lat": 9.0820, "lon": 8.6753},
    ".ke":    {"name": "Kenya", "lat": -0.0236, "lon": 37.9062},
    ".az":    {"name": "Azerbaijan", "lat": 40.1431, "lon": 47.5769},
    ".tv":    {"name": "Global", "lat": 25.0, "lon": 55.0},
    ".ie":    {"name": "Ireland", "lat": 53.1424, "lon": -7.6921},
    ".it":    {"name": "Italy", "lat": 41.8719, "lon": 12.5674},
    ".es":    {"name": "Spain", "lat": 40.4637, "lon": -3.7492},
    ".nl":    {"name": "Netherlands", "lat": 52.1326, "lon": 5.2913},
    ".kr":    {"name": "South Korea", "lat": 35.9078, "lon": 127.7669},
    ".se":    {"name": "Sweden", "lat": 60.1282, "lon": 18.6435},
    ".no":    {"name": "Norway", "lat": 60.4720, "lon": 8.4689},
    ".nz":    {"name": "New Zealand", "lat": -40.9006, "lon": 174.886},
    ".com":   {"name": "United States", "lat": 37.0902, "lon": -95.7129},
    ".org":   {"name": "United States", "lat": 38.9072, "lon": -77.0369},
    ".net":   {"name": "United States", "lat": 37.0902, "lon": -95.7129},
}

def get_location_from_source(source_name: str):
    """Try to get a location from the news source name or domain TLD."""
    if not source_name:
        return None
    key = source_name.lower().strip()
    # Exact match
    if key in SOURCE_LOCATION_MAP:
        return SOURCE_LOCATION_MAP[key].copy()
    # Partial match
    for src, loc in SOURCE_LOCATION_MAP.items():
        if src in key or key in src:
            return loc.copy()
    # TLD-based fallback (check longest TLDs first like .co.uk before .uk)
    for tld in sorted(TLD_COUNTRY_MAP.keys(), key=len, reverse=True):
        if key.endswith(tld):
            return TLD_COUNTRY_MAP[tld].copy()
    return None


# ─── DATABASE & GEO INIT ─────────────────────────────────────
logger.info("Initializing database...")
db.init_db()

geolocator = Nominatim(user_agent="geo_news_dashboard_v2")
geocode_lock = threading.Lock()


def geocode_location(place_name: str):
    if not place_name:
        return None
    cached = db.get_cached_geocode(place_name)
    if cached:
        return cached
    try:
        with geocode_lock:
            time.sleep(1.1)
            loc = geolocator.geocode(place_name, language='en', timeout=10)
        if loc:
            db.save_geocode(place_name, loc.address, loc.latitude, loc.longitude)
            return {"name": loc.address, "lat": loc.latitude, "lon": loc.longitude}
    except Exception as e:
        logger.warning(f"Geocoding failed for '{place_name}': {e}")
    return None


# ═══════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════

@app.route('/', methods=['GET'])
def home():
    return render_template('index.html')


@app.before_request
def start_timer():
    request.start_time = time.time()
    if request.path.startswith('/api/'):
        APP_METRICS["total_requests"] += 1


@app.after_request
def log_request(response):
    if request.path.startswith('/api/'):
        duration = time.time() - request.start_time
        logger.info(f"Method: {request.method} | Path: {request.path} | Status: {response.status_code} | Duration: {duration:.3f}s")
    return response


@app.route('/api/news', methods=['GET'])
def get_news():
    """
    Serve news from DB instantly (stale-while-revalidate).
    Supports ETag conditional requests to skip rendering if unchanged.
    """
    category = request.args.get('category', 'general')

    # ── Stale-While-Revalidate: serve DB instantly, refresh in background ──
    db_data = db.get_articles(category)

    if db_data and db_data["total_results"] > 0:
        APP_METRICS["cache_hits"] += 1
        etag = db_data.get("etag", "")

        # Check If-None-Match (ETag) header — skip re-render if unchanged
        client_etag = request.headers.get("If-None-Match", "")
        if client_etag and client_etag == etag:
            return make_response("", 304)

        # If stale (older than REFRESH_INTERVAL_HOURS), refresh in background
        last_fetch = db.get_last_fetch_time(category)
        if last_fetch and (datetime.now() - last_fetch) > timedelta(hours=REFRESH_INTERVAL_HOURS):
            logger.info(f"Stale data for '{category}', triggering background refresh")
            t = threading.Thread(target=fetch_and_store_category, args=(category,), daemon=True)
            t.start()

        logger.info(f"Serving {db_data['total_results']} articles from DB for '{category}'")
        response = make_response(jsonify(db_data))
        if etag:
            response.headers["ETag"] = etag
        return response

    # ── First-time fetch ──
    logger.info(f"No DB data for '{category}', performing live fetch...")
    result = fetch_and_store_category(category)
    if "error" in result:
        APP_METRICS["api_errors"] += 1
        return jsonify(result), 500
    return jsonify(result)


@app.route('/api/search', methods=['GET'])
def search_news():
    """
    Hybrid search: TF-IDF local cache first, then World News API fallback.
    """
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400

    logger.info(f"Search request: '{query}'")

    # ── Step 1: Local TF-IDF search ──
    local_results = db.search_articles_local(query, limit=15)

    if len(local_results) >= 5:
        logger.info(f"Local TF-IDF search returned {len(local_results)} results for '{query}'")
        # Enrich with sentiment scores for search results too
        for art in local_results:
            if art.get('sentiment_score', 0.0) == 0.0:
                art['sentiment_score'] = get_sentiment(f"{art.get('title','')} {art.get('summary','')}")
        return jsonify({
            "status": "success",
            "category": "search",
            "query": query,
            "source": "local_cache",
            "total_results": len(local_results),
            "articles": local_results
        })

    # ── Step 2: Fallback to World News API ──
    logger.info(f"Local results sparse ({len(local_results)}), falling back to World News API")
    if not WORLD_NEWS_API_KEY:
        return jsonify({"error": "World News API key not configured"}), 500

    api_results = _fetch_world_news_search(query)
    if "error" in api_results:
        # If API also fails but we have local results, return them
        if local_results:
            return jsonify({
                "status": "success",
                "category": "search",
                "query": query,
                "source": "local_cache_fallback",
                "total_results": len(local_results),
                "articles": local_results
            })
        return jsonify(api_results), 500

    # Merge: put API results first, then unique local results
    api_urls = {a['url'] for a in api_results.get('articles', [])}
    extra_local = [a for a in local_results if a['url'] not in api_urls]
    merged = api_results.get('articles', []) + extra_local
    api_results['articles'] = merged[:15]
    api_results['total_results'] = len(api_results['articles'])
    api_results['source'] = 'api+local'
    return jsonify(api_results)


@app.route('/api/status', methods=['GET'])
def get_data_status():
    ready_categories = []
    for cat in ALL_CATEGORIES:
        data = db.get_articles(cat)
        if data and data["total_results"] > 0:
            ready_categories.append(cat)
    return jsonify({
        "ready": len(ready_categories) == len(ALL_CATEGORIES),
        "ready_categories": ready_categories,
        "total_categories": len(ALL_CATEGORIES)
    })


@app.route('/metrics', methods=['GET'])
def get_metrics():
    db_stats = db.get_db_stats()
    return jsonify({
        "status": "healthy",
        "metrics": {
            "total_requests": APP_METRICS["total_requests"],
            "cache_hits": APP_METRICS["cache_hits"],
            "api_errors": APP_METRICS["api_errors"],
            "start_time": APP_START_TIME.isoformat(),
            "uptime_seconds": (datetime.now() - APP_START_TIME).total_seconds()
        },
        "database": db_stats
    })


# ═══════════════════════════════════════════════════════════════
#  CORE FETCH + PROCESS LOGIC
# ═══════════════════════════════════════════════════════════════

def _process_raw_articles(raw_articles: list, category: str) -> list:
    """
    Shared processing pipeline: extract location, sentiment, keywords.
    Used by both category fetches and search.
    """
    processed = []
    for a in raw_articles:
        title = a.get('title', '')
        url = a.get('url', '')
        if not title or not url:
            continue

        # ── Location: use API-provided lat/lon first ──
        lat = a.get('latitude')
        lon = a.get('longitude')
        location_info = None
        if lat and lon:
            location_info = {
                "name": a.get('location_name') or f"{lat:.2f},{lon:.2f}",
                "lat": lat,
                "lon": lon
            }
        else:
            # Fallback: source headquarters
            try:
                domain = urlparse(url).netloc.replace('www.', '')
                location_info = get_location_from_source(domain)
            except Exception:
                pass

        # ── Summary ──
        summary = a.get('summary') or a.get('text', '')
        if len(summary) > 500:
            summary = summary[:500] + '...'

        # ── Source domain ──
        try:
            source = urlparse(url).netloc.replace('www.', '')
        except Exception:
            source = a.get('author', 'Unknown')

        # ── Sentiment ──
        sentiment = get_sentiment(f"{title} {summary}")

        processed.append({
            "title": title,
            "url": url,
            "image_url": a.get('image', ''),
            "source": source,
            "published_at": a.get('publish_date', ''),
            "summary": summary or 'No summary available.',
            "keywords": [],
            "location": location_info,
            "sentiment_score": sentiment,
            "cluster_id": None  # Set by cluster_articles()
        })

    # ── Story Clustering ──
    processed = cluster_articles(processed)
    return processed


def fetch_and_store_category(category: str) -> dict:
    """Fetch from World News API, process, and store to DB."""
    if not WORLD_NEWS_API_KEY:
        return {"error": "WORLD_NEWS_API key not configured"}

    keyword = CATEGORY_KEYWORDS.get(category, 'world news')
    try:
        resp = requests.get(
            "https://api.worldnewsapi.com/search-news",
            params={
                "text": keyword,
                "language": "en",
                "api-key": WORLD_NEWS_API_KEY,
                "number": 15,
                "sort": "publish-time",
                "sort-direction": "DESC",
            },
            timeout=15
        )
        if resp.status_code != 200:
            return {"error": f"World News API error {resp.status_code}: {resp.text[:200]}"}

        raw_articles = resp.json().get('news', [])
        processed = _process_raw_articles(raw_articles, category)

        db.save_articles(category, processed)
        return {
            "status": "success",
            "category": category,
            "total_results": len(processed),
            "articles": processed
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


def _fetch_world_news_search(query: str) -> dict:
    """Fetch from World News API for a search query."""
    try:
        resp = requests.get(
            "https://api.worldnewsapi.com/search-news",
            params={
                "text": query,
                "language": "en",
                "api-key": WORLD_NEWS_API_KEY,
                "number": 15
            },
            timeout=15
        )
        if resp.status_code != 200:
            return {"error": f"World News API error {resp.status_code}"}

        raw_articles = resp.json().get('news', [])
        processed = _process_raw_articles(raw_articles, 'search')
        return {
            "status": "success",
            "category": "search",
            "query": query,
            "total_results": len(processed),
            "articles": processed
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
#  APSCHEDULER BACKGROUND JOBS
# ═══════════════════════════════════════════════════════════════

def _refresh_category_job(category: str):
    """Scheduled job to refresh a single category."""
    last_fetch = db.get_last_fetch_time(category)
    if last_fetch and (datetime.now() - last_fetch) < timedelta(hours=REFRESH_INTERVAL_HOURS):
        logger.info(f"[Scheduler] '{category}' still fresh, skipping")
        return
    logger.info(f"[Scheduler] Refreshing '{category}'...")
    fetch_and_store_category(category)


def _cleanup_job():
    """Scheduled midnight cleanup."""
    logger.info("[Scheduler] Running cleanup job...")
    db.cleanup_old_articles(keep_days=KEEP_DAYS)


def start_scheduler():
    """Configure APScheduler with per-category jobs + jitter to avoid thundering herd."""
    scheduler = BackgroundScheduler()

    import random
    for i, cat in enumerate(ALL_CATEGORIES):
        # Stagger initial warmup: 0, 5, 10, 15, ... seconds
        # Then each category refreshes every 4h ± 15min jitter
        jitter_seconds = random.randint(-900, 900)
        interval_seconds = REFRESH_INTERVAL_HOURS * 3600 + jitter_seconds

        scheduler.add_job(
            func=_refresh_category_job,
            args=[cat],
            trigger='interval',
            seconds=interval_seconds,
            id=f"refresh_{cat}",
            replace_existing=True,
            next_run_time=datetime.now() + timedelta(seconds=i * 5)  # stagger startup
        )

    # Daily midnight cleanup
    scheduler.add_job(
        func=_cleanup_job,
        trigger='cron',
        hour=0,
        minute=0,
        id='nightly_cleanup',
        replace_existing=True
    )

    scheduler.start()
    logger.info("APScheduler started with jitter-based refresh jobs")
    return scheduler


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    scheduler = start_scheduler()

    logger.info("=" * 50)
    logger.info("FLASK BACKEND RUNNING ON http://127.0.0.1:5000")
    logger.info("=" * 50)

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
