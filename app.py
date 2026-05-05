import os
from flask import Flask, jsonify, request, render_template
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from collections import Counter
from datetime import datetime, timedelta, date
import threading
import time
import logging
import requests

# Configure production logging
logging.basicConfig(level=logging.INFO, 
                    format='[%(asctime)s] %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Load Environment Variables
load_dotenv()
WORLD_NEWS_API_KEY = os.getenv("WORLD_NEWS_API")

# Initialize Flask Server
app = Flask(__name__)
from flask_cors import CORS
CORS(app)

from metrics import APP_METRICS, APP_START_TIME
import db  # SQLite database layer

# ─── CONFIGURATION ──────────────────────────────────────────
REFRESH_INTERVAL_HOURS = 4        # Fetch fresh news every 4 hours
CLEANUP_HOUR = 0                  # Run cleanup at midnight (00:00)
KEEP_DAYS = 3                     # Keep articles for 3 days
ALL_CATEGORIES = ['general', 'politics', 'sports', 'technology', 'entertainment', 'health', 'business']

# ─── SOURCE → LOCATION FALLBACK MAP ─────────────────────────
# When NLP can't find a location, use the news source as a hint
SOURCE_LOCATION_MAP = {
    # Indian sources
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
    # International sources
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
    # Entertainment / Health / Sports generic sources
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


def get_location_from_source(source_name):
    """Try to get a location from the news source name."""
    if not source_name:
        return None
    key = source_name.lower().strip()
    # Exact match
    if key in SOURCE_LOCATION_MAP:
        return SOURCE_LOCATION_MAP[key].copy()
    # Partial match (e.g., 'The Times of India - Sports' matches 'times of india')
    for src, loc in SOURCE_LOCATION_MAP.items():
        if src in key or key in src:
            return loc.copy()
    return None


# ─── INITIALIZE MODELS & DATABASE ───────────────────────────
logger.info("Initializing database...")
geolocator = Nominatim(user_agent="geo_news_dashboard_flask_api")

# Initialize SQLite database tables
db.init_db()

# Global lock for Nominatim API rate limiting
geocode_lock = threading.Lock()


def geocode_location(place_name):
    """Geocode a place name using cache → Nominatim fallback."""
    if not place_name or not geolocator:
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
    """Serve the interactive Map Dashboard."""
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
    API Endpoint: /api/news?category=technology
    
    Serves news INSTANTLY from SQLite database.
    If no data exists yet (first run), triggers a live fetch.
    """
    category = request.args.get('category', 'general')
    logger.info(f"Request received for category: {category}")
    
    # ── STEP 1: Try to serve from database (INSTANT — < 50ms) ──
    db_data = db.get_articles(category)
    if db_data and db_data["total_results"] > 0:
        APP_METRICS["cache_hits"] += 1
        logger.info(f"Serving {db_data['total_results']} articles from DATABASE for '{category}' (instant)")
        return jsonify(db_data)
    
    # ── STEP 2: No data in DB yet — do a live fetch (first-time only) ──
    logger.info(f"No DB data for '{category}', performing live fetch...")
    response_data = fetch_and_store_category(category)
    if "error" in response_data:
        APP_METRICS["api_errors"] += 1
        return jsonify(response_data), 500
        
    return jsonify(response_data)


@app.route('/api/search', methods=['GET'])
def search_news():
    """
    API Endpoint: /api/search?q=keyword
    
    Searches news using World News API, processes them for geo-location,
    and returns them immediately (no persistent DB caching to avoid clutter, 
    or you could cache if desired, but transient is fine for search).
    """
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({"error": "Query parameter 'q' is required"}), 400
        
    logger.info(f"Search request received for: {query}")
    
    if not WORLD_NEWS_API_KEY:
        logger.error("WORLD_NEWS_API key is missing.")
        return jsonify({"error": "World News API key not configured"}), 500
        
    response_data = fetch_world_news_search(query)
    if "error" in response_data:
        APP_METRICS["api_errors"] += 1
        return jsonify(response_data), 500
        
    return jsonify(response_data)


@app.route('/api/status', methods=['GET'])
def get_data_status():
    """
    Frontend can poll this to check if data is ready.
    Returns which categories have data in the DB.
    """
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
    """API Endpoint for Server Health and Monitoring."""
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
#  CORE FETCH + STORE LOGIC
# ═══════════════════════════════════════════════════════════════

def fetch_and_store_category(category: str) -> dict:
    """
    Fetch news from World News API, optionally geocode, store in SQLite.
    """
    if not WORLD_NEWS_API_KEY:
        return {"error": "WORLD_NEWS_API key not configured"}

    # Category → search keywords mapping
    category_keywords = {
        'general':       'world news',
        'politics':      'politics election government parliament',
        'sports':        'sports cricket football IPL olympics',
        'technology':    'technology AI software startup',
        'entertainment': 'entertainment movies celebrity music',
        'health':        'health medical disease WHO healthcare',
        'business':      'business economy market finance stock',
    }
    keyword = category_keywords.get(category, 'world news')

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
        processed_news = []

        for a in raw_articles:
            title = a.get('title', '')
            url   = a.get('url', '')
            if not title or not url:
                continue

            # World News API provides lat/lon directly
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
                source_name = a.get('source_country') or ''
                try:
                    domain = a.get('url', '')
                    from urllib.parse import urlparse
                    domain = urlparse(domain).netloc.replace('www.', '')
                    location_info = get_location_from_source(domain)
                except Exception:
                    pass

            summary = a.get('summary') or a.get('text', '')
            if len(summary) > 500:
                summary = summary[:500] + '...'

            # Extract source from URL domain
            try:
                from urllib.parse import urlparse
                source = urlparse(url).netloc.replace('www.', '')
            except Exception:
                source = 'Unknown'

            processed_news.append({
                "title": title,
                "url": url,
                "image_url": a.get('image', ''),
                "source": source,
                "published_at": a.get('publish_date', ''),
                "summary": summary or 'No summary available.',
                "keywords": [],
                "location": location_info
            })

        db.save_articles(category, processed_news)
        return {
            "status": "success",
            "category": category,
            "total_results": len(processed_news),
            "articles": processed_news
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


def fetch_world_news_search(query: str) -> dict:
    """
    Fetch news from World News API based on search query, process articles for location.
    """
    try:
        url = "https://api.worldnewsapi.com/search-news"
        params = {
            "text": query,
            "language": "en",
            "api-key": WORLD_NEWS_API_KEY,
            "number": 15
        }
        
        response = requests.get(url, params=params, timeout=15)
        if response.status_code != 200:
            logger.error(f"World News API Error: {response.text}")
            return {"error": "Failed to fetch from World News API"}
            
        data = response.json()
        articles_data = data.get('news', [])
        
        processed_news = []
        for article in articles_data:
            title = article.get('title', '')
            url = article.get('url', '')
            image_url = article.get('image', '')
            source = article.get('author', 'Unknown') # World News API sometimes uses author or source
            if not source or source == 'Unknown':
                # Try to extract domain as source
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc
                    source = domain.replace('www.', '') if domain else 'Unknown'
                except:
                    pass
            
            published_at = article.get('publish_date', '')
            summary = article.get('summary') or article.get('text', '')
            
            if not title or not url:
                continue
                
            # Truncate summary if it's too long (World News API 'text' can be the full article)
            if len(summary) > 500:
                summary = summary[:500] + "..."
                
            # Extract location directly from World News API response
            lat = article.get('latitude')
            lon = article.get('longitude')
            location_info = None

            if lat and lon:
                location_info = {
                    "name": article.get('location_name') or f"{lat:.2f},{lon:.2f}",
                    "lat": lat,
                    "lon": lon
                }
            else:
                if source:
                    location_info = get_location_from_source(source)
                 
            processed_news.append({
                "title": title,
                "url": url,
                "image_url": image_url,
                "source": source,
                "published_at": published_at,
                "summary": summary if summary else "No summary available.",
                "keywords": [], # WorldNewsAPI doesn't return keywords in basic search usually
                "location": location_info
            })
            
        return {
            "status": "success",
            "category": "search",
            "query": query,
            "total_results": len(processed_news),
            "articles": processed_news
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
#  BACKGROUND SCHEDULER
# ═══════════════════════════════════════════════════════════════

def should_refresh(category: str) -> bool:
    """Check if a category needs refreshing (older than REFRESH_INTERVAL_HOURS)."""
    last_fetch = db.get_last_fetch_time(category)
    if last_fetch is None:
        return True
    return (datetime.now() - last_fetch) > timedelta(hours=REFRESH_INTERVAL_HOURS)


def run_background_scheduler():
    """
    Background daemon thread that:
    1. On startup: Fetches ALL categories to warm the database
    2. Every 4 hours: Refreshes stale categories
    3. At midnight: Cleans up articles older than KEEP_DAYS
    """
    logger.info("=" * 50)
    logger.info("BACKGROUND SCHEDULER STARTED")
    logger.info("=" * 50)
    
    # ── INITIAL WARM-UP: Pre-fetch all categories ──
    for cat in ALL_CATEGORIES:
        if should_refresh(cat):
            logger.info(f"[Startup] Pre-fetching '{cat}' into database...")
            fetch_and_store_category(cat)
            time.sleep(3)  # Be gentle with APIs
        else:
            logger.info(f"[Startup] '{cat}' already fresh in database, skipping")
    
    logger.info("=" * 50)
    logger.info("ALL CATEGORIES LOADED — Ready to serve instantly!")
    logger.info("=" * 50)
    
    # ── CONTINUOUS LOOP ──
    last_cleanup_date = None
    
    while True:
        now = datetime.now()
        
        # ── MIDNIGHT CLEANUP ──
        if now.hour == CLEANUP_HOUR and last_cleanup_date != date.today():
            logger.info("Running midnight cleanup...")
            db.cleanup_old_articles(keep_days=KEEP_DAYS)
            last_cleanup_date = date.today()
        
        # ── REFRESH STALE CATEGORIES ──
        for cat in ALL_CATEGORIES:
            if should_refresh(cat):
                logger.info(f"[Scheduler] Refreshing '{cat}'...")
                fetch_and_store_category(cat)
                time.sleep(5)  # Pause between categories
        
        # Sleep for 15 minutes, then check again
        logger.info("Scheduler sleeping for 15 minutes...")
        time.sleep(900)


# ═══════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Start the background scheduler thread
    scheduler_thread = threading.Thread(target=run_background_scheduler, daemon=True)
    scheduler_thread.start()

    logger.info("=" * 50)
    logger.info("FLASK BACKEND RUNNING ON http://127.0.0.1:5000")
    logger.info("=" * 50)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
