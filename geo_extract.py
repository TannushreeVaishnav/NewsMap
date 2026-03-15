import os
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

# Load environment variables
load_dotenv()
API_KEY = os.getenv("NEWS_API_KEY")

# Initialize SpaCy and Geopy for Geography Extraction
print("Loading Geography Models (SpaCy & GeoPy)...")
try:
    nlp = spacy.load("en_core_web_sm")
    geolocator = Nominatim(user_agent="geo_news_dashboard_123")
except Exception as e:
    print(f"Failed to load geography models: {e}")
    exit(1)

def extract_primary_location(text):
    """
    Uses SpaCy NLP to find the most frequently mentioned location (GPE),
    then uses GeoPy to find the Latitude and Longitude.
    """
    doc = nlp(text)
    
    # Extract all Geopolitical Entities (Countries, Cities, States)
    locations = [ent.text for ent in doc.ents if ent.label_ == "GPE"]
    
    if not locations:
        return None
        
    # Find the most commonly mentioned location in the article
    most_common_location = Counter(locations).most_common(1)[0][0]
    
    # Geocode it (Turn "Paris" into Lat: 48.85, Lon: 2.35)
    try:
        location_data = geolocator.geocode(most_common_location)
        if location_data:
            return {
                "name": location_data.address,
                "lat": location_data.latitude,
                "lon": location_data.longitude
            }
    except Exception as e:
        print(f"   [Geo Error]: Could not geocode '{most_common_location}': {e}")
        
    return None

def fetch_and_process_geo_news():
    """
    Fetches news, summarizes it, and maps it geographically.
    """
    if not API_KEY:
        print("Error: Please set your NEWS_API_KEY in the .env file.")
        return []

    print("Fetching breaking headlines for Geo-Extraction...\n")
    newsapi = NewsApiClient(api_key=API_KEY)

    try:
        response = newsapi.get_top_headlines(language='en', page_size=2)
        
        if response['status'] == 'ok':
            articles = response['articles']
            
            for i, article_data in enumerate(articles, 1):
                url = article_data['url']
                title = article_data['title']
                
                print(f"{'='*50}")
                print(f"Article {i}: {title}")
                print(f"Link: {url}")
                print("Status: Reading and Extracting Details...")
                
                try:
                    # Fake User-Agent to bypass some 403 Forbidden blocks
                    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'
                    config = Config()
                    config.browser_user_agent = user_agent
                    config.request_timeout = 10
                    
                    article = Article(url, config=config)
                    article.download()
                    article.parse()
                    
                    full_text = article.text
                    
                    if len(full_text) < 150:
                        print("Result: [X] Article text was too short or paywalled. Skipping.\n")
                        continue
                    
                    article.nlp()
                    
                    print(f"\n[*] Quick Summary:\n {article.summary[:300]}...\n")
                    
                    #Geographic Extraction
                    print("Status: Pinpointing Geographic Location...")
                    location_info = extract_primary_location(full_text)
                    
                    if location_info:
                        print(f"[*] Map Pin Location Found: {location_info['name']}")
                        print(f"[*] Coordinates: Latitude {location_info['lat']}, Longitude {location_info['lon']}")
                    else:
                        print("[*] No primary geographic location found in this article.")
                        
                except Exception as scrape_error:
                    print(f"Result: [!] Failed to process this article. Error: {scrape_error}\n")
            
        else:
            print("Failed to fetch news from NewsAPI.")
            
    except Exception as e:
        print(f"An API error occurred: {e}")

if __name__ == "__main__":
    fetch_and_process_geo_news()
