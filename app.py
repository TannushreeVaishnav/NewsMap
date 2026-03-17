import os
from flask import Flask, jsonify, request, render_template
from dotenv import load_dotenv
from newsapi import NewsApiClient
from newspaper import Article, Config
import nltk
import spacy
from geopy.geocoders import Nominatim
from collections import Counter
import concurrent.futures
from datetime import datetime, timedelta
import threading
import time
import logging

# Configure production logging
logging.basicConfig(level=logging.INFO, 
                    format='[%(asctime)s] %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    nltk.download('punkt', quiet=True)
except Exception:
    pass

# Load Environment Variables
load_dotenv()
API_KEY = os.getenv("NEWS_API_KEY")

# Initialize Flask Server
app = Flask(__name__)
from flask_cors import CORS
CORS(app)

from metrics import NEWS_CACHE, APP_METRICS, APP_START_TIME
CACHE_TIMEOUT = timedelta(hours=4) # Cache news for 4 hours to avoid API limits

logger.info("Initializing models...")
try:
    nlp = spacy.load("en_core_web_sm")
    geolocator = Nominatim(user_agent="geo_news_dashboard_flask_api")
except Exception as e:
    logger.error(f"Error loading models: {e}")

# Global lock to prevent Nominatim API rate limiting errors
geocode_lock = threading.Lock()

def extract_primary_location(summary, title=""):
    if not title:
        title = ""
    if not summary:
        summary = ""
        
    title_doc = nlp(title)
    title_locations = [ent.text for ent in title_doc.ents if ent.label_ == "GPE"]
    
    summary_doc = nlp(summary)
    summary_locations = [ent.text for ent in summary_doc.ents if ent.label_ == "GPE"]
    
    # Give the Title 3x weight since it usually contains the primary subject
    locations = (title_locations * 3) + summary_locations
    
    if not locations:
        return None
        
    most_common_location = Counter(locations).most_common(1)[0][0]
    
    try:
        with geocode_lock:
            time.sleep(1.2) 
            location_data = geolocator.geocode(most_common_location, language='en', timeout=10)
            
        if location_data:
            return {
                "name": location_data.address,
                "lat": location_data.latitude,
                "lon": location_data.longitude
            }
    except Exception as e:
        logger.warning(f"Geocoding failed for '{most_common_location}': {e}")
        pass
        
    return None

@app.route('/', methods=['GET'])
def home():
    """ Serve the stunning interactive Map Dashboard """
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

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """ API Endpoint for Server Health and Monitoring """
    return jsonify({
        "status": "healthy",
        "metrics": {
            "total_requests": APP_METRICS["total_requests"],
            "cache_hits": APP_METRICS["cache_hits"],
            "api_errors": APP_METRICS["api_errors"],
            "start_time": APP_START_TIME.isoformat(),
            "cache_size": len(NEWS_CACHE),
            "uptime_seconds": (datetime.now() - APP_START_TIME).total_seconds()
        }
    })

def fetch_category_data(category: str):
    """ Core processing function: fetches, scrapes, summarizes and geo-tags articles for a given category. """
    newsapi = NewsApiClient(api_key=API_KEY)
    
    try:
        valid_category = category if category in ['business', 'entertainment', 'general', 'health', 'science', 'sports', 'technology'] else 'general'
        yesterday_dt = datetime.now() - timedelta(days=1)
        yesterday_str = yesterday_dt.strftime('%Y-%m-%d')
        filter_start_time = yesterday_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if category == 'politics':
            response = newsapi.get_everything(q='india politics', language='en', sort_by='relevancy', page_size=15, from_param=yesterday_str)
        else:
            response = newsapi.get_top_headlines(language='en', country='in', category=valid_category, page_size=15)
            
            if response['status'] == 'ok' and len(response['articles']) < 5:
                response = newsapi.get_top_headlines(language='en', category=valid_category, page_size=15)
        
        if response.get('status') != 'ok':
            logger.error(f"NewsAPI Error: {response}")
            return {"error": response.get('message', "Failed to fetch from NewsAPI")}
            
        articles_data = response['articles']
        
        # Fake User-Agent to prevent getting blocked by anti-scraping websites
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'
        config = Config()
        config.browser_user_agent = user_agent
        config.request_timeout = 10
        
        def process_single_article(article_data):
            url = article_data['url']
            title = article_data['title']
            image_url = article_data.get('urlToImage', '')
            source = article_data.get('source', {}).get('name', 'Unknown')
            published_at = article_data.get('publishedAt', '')
            
            # Filter out old news (older than yesterday)
            try:
                if published_at:
                    pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00')).replace(tzinfo=None)
                    if pub_date < filter_start_time:
                        logger.info(f"Dropping old news: '{title}' ({published_at})")
                        return None
            except Exception:
                pass
            
            try:
                # Scrape it
                article = Article(url, config=config)
                article.download()
                article.parse()
                
                # If paywalled or too short, skip it
                if len(article.text) < 150:
                    return None
                    
                # Summarize it
                article.nlp()
                summary = article.summary
                keywords = article.keywords
                
                # Geo-Tag it using the Title and Summary instead of full text
                location_info = extract_primary_location(summary, title)
                
                # Package it into our clean dictionary
                return {
                    "title": title,
                    "url": url,
                    "image_url": image_url,
                    "source": source,
                    "published_at": published_at,
                    "summary": summary,
                    "keywords": keywords[:5],
                    "location": location_info
                }
                
            except Exception as e:
                logger.warning(f"Skipped '{title}' due to error: {e}")
                return None

        processed_news = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_results = executor.map(process_single_article, articles_data)
            
            for result in future_results:
                if result is not None:
                    processed_news.append(result)
                
        response_data = {
            "status": "success",
            "category": category,
            "total_results": len(processed_news),
            "articles": processed_news
        }
        
        NEWS_CACHE[category] = {
            'timestamp': datetime.now(),
            'data': response_data
        }
        
        return response_data
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

@app.route('/api/news', methods=['GET'])
def get_news():
    """ 
    API Endpoint: http://localhost:5000/api/news?category=technology 
    Returns summarized and geo-tagged news as JSON.
    """
    # Grab the category from the URL (default to general news)
    category = request.args.get('category', 'general')
    
    logger.info(f"Request received for category: {category}")
    
    # --- CHECK CACHE FIRST ---
    now = datetime.now()
    if category in NEWS_CACHE:
        cached_data = NEWS_CACHE[category]
        timestamp = cached_data.get('timestamp')
        if isinstance(timestamp, datetime) and now - timestamp < CACHE_TIMEOUT:
            logger.info(f"Returning INSTANTLY from cache for category: {category}")
            APP_METRICS["cache_hits"] += 1
            return jsonify(cached_data['data'])
    # -------------------------
    
    # If not in cache or expired, fetch it live
    response_data = fetch_category_data(category)
    if "error" in response_data:
        APP_METRICS["api_errors"] += 1
        return jsonify(response_data), 500
        
    return jsonify(response_data)

def run_background_prefetch():
    categories = ['general', 'politics', 'sports', 'technology', 'entertainment', 'health', 'business']
    logger.info("Starting background daemon...")
    
    while True:
        for cat in categories:
            now = datetime.now()
            is_expired = True
            if cat in NEWS_CACHE:
                timestamp = NEWS_CACHE[cat].get('timestamp')
                if isinstance(timestamp, datetime):
                    is_expired = (now - timestamp > CACHE_TIMEOUT)
                    
            if is_expired:
                logger.info(f"Pre-fetching '{cat}' news into cache...")
                fetch_category_data(cat)
                time.sleep(5)
        
        logger.info("Waiting 4 hours for next refresh.")
        time.sleep(14400)

if __name__ == '__main__':
    # Start the continuous Background Pre-Fetching thread daemon
    prefetch_thread = threading.Thread(target=run_background_prefetch, daemon=True)
    prefetch_thread.start()

    logger.info("="*50)
    logger.info("FLASK BACKEND RUNNING ON http://127.0.0.1:5000")
    logger.info("="*50)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
