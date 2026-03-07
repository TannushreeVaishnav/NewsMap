import os
from flask import Flask, jsonify, request, render_template
from dotenv import load_dotenv
from newsapi import NewsApiClient
from newspaper import Article, Config
import nltk
import spacy
from geopy.geocoders import Nominatim
from collections import Counter

# NLTK punkt is required for newspaper3k's built-in summarization feature
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

# Load AI Models globally so they only load once when the server starts up
print("[INFO] Initializing Spacy and Geo models...")
try:
    nlp = spacy.load("en_core_web_sm")
    geolocator = Nominatim(user_agent="geo_news_dashboard_flask_api")
except Exception as e:
    print(f"Error loading models: {e}")

def extract_primary_location(text):
    """ Helper Function: Extracts Geo location using SpaCy and Geopy """
    doc = nlp(text)
    locations = [ent.text for ent in doc.ents if ent.label_ == "GPE"]
    
    if not locations:
        return None
        
    most_common_location = Counter(locations).most_common(1)[0][0]
    
    try:
        # Ask the Geocoder to specifically return the English version of the location name
        location_data = geolocator.geocode(most_common_location, language='en')
        if location_data:
            return {
                "name": location_data.address,
                "lat": location_data.latitude,
                "lon": location_data.longitude
            }
    except Exception:
        pass
        
    return None

@app.route('/', methods=['GET'])
def home():
    """ Serve the stunning interactive Map Dashboard """
    return render_template('index.html')

@app.route('/api/news', methods=['GET'])
def get_news():
    """ 
    API Endpoint: http://localhost:5000/api/news?category=technology 
    Returns summarized and geo-tagged news as JSON.
    """
    # Grab the category from the URL (default to general news)
    category = request.args.get('category', 'general')
    newsapi = NewsApiClient(api_key=API_KEY)
    
    print(f"\n[GET] Request received for category: {category}")
    
    try:
        # NewsAPI built-in categories do not include "politics"
        valid_category = category if category in ['business', 'entertainment', 'general', 'health', 'science', 'sports', 'technology'] else 'general'
        
        # If the user clicks Politics, we have to search for it manually using keywords
        if category == 'politics':
            response = newsapi.get_everything(q='india politics', language='en', sort_by='relevancy', page_size=10)
        else:
            # Try getting Indian specific headlines first
            response = newsapi.get_top_headlines(language='en', country='in', category=valid_category, page_size=10)
            
            # If not enough breaking Indian news in this category, we ask the 'Everything' API to grab from BBC, Times of India, etc.
            if response['status'] == 'ok' and len(response['articles']) < 5:
                # We append "india" to the category word to force the API to give us Indian results
                search_query = f"india {valid_category}"
                response = newsapi.get_everything(q=search_query, language='en', sort_by='relevancy', page_size=10)
        
        if response['status'] != 'ok':
            return jsonify({"error": "Failed to fetch from NewsAPI"}), 500
            
        articles_data = response['articles']
        processed_news = []
        
        # Fake User-Agent to prevent getting blocked by anti-scraping websites
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'
        config = Config()
        config.browser_user_agent = user_agent
        config.request_timeout = 10
        
        # Loop through each article and pass it through our pipeline
        for article_data in articles_data:
            url = article_data['url']
            title = article_data['title']
            image_url = article_data.get('urlToImage', '')
            source = article_data.get('source', {}).get('name', 'Unknown')
            
            try:
                # 1. Scrape it
                article = Article(url, config=config)
                article.download()
                article.parse()
                
                # If paywalled or too short, skip it
                if len(article.text) < 150:
                    continue
                    
                # 2. Summarize it
                article.nlp()
                summary = article.summary
                keywords = article.keywords
                
                # 3. Geo-Tag it
                location_info = extract_primary_location(article.text)
                
                # 4. Package it into our clean dictionary
                processed_news.append({
                    "title": title,
                    "url": url,
                    "image_url": image_url,
                    "source": source,
                    "summary": summary,
                    "keywords": keywords[:5],
                    "location": location_info
                })
                
            except Exception as e:
                print(f"[-] Skipped '{title}' due to error: {e}")
                continue
                
        # Send json back to the web frontend
        return jsonify({
            "status": "success",
            "category": category,
            "total_results": len(processed_news),
            "articles": processed_news
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*50)
    print("FLASK BACKEND RUNNING ON http://127.0.0.1:5000")
    print("="*50 + "\n")
    #app.run(debug=True, host='127.0.0.1', port=5000)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
