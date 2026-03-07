import os
from dotenv import load_dotenv
from newsapi import NewsApiClient

# Load environment variables from .env file
load_dotenv()

# Get the API key
API_KEY = os.getenv("NEWS_API_KEY")

def fetch_top_headlines():
    """
    Fetches the top headlines from NewsAPI.
    """
    if not API_KEY:
        print("Error: Please set your NEWS_API_KEY in the .env file.")
        return []

    # Initialize the client
    newsapi = NewsApiClient(api_key=API_KEY)

    print("Fetching top headlines...")
    try:
        # Fetch top headlines in English
        response = newsapi.get_top_headlines(language='en', page_size=5)
        
        if response['status'] == 'ok':
            articles = response['articles']
            print(f"Successfully fetched {len(articles)} articles!\n")
            
            # Print a quick preview
            for i, article in enumerate(articles, 1):
                print(f"{i}. {article['title']}")
                print(f"   Source: {article['source']['name']}")
                print(f"   URL: {article['url']}\n")
            
            return articles
        else:
            print("Failed to fetch news.")
            return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

if __name__ == "__main__":
    fetch_top_headlines()
