import os
from dotenv import load_dotenv
from newsapi import NewsApiClient
from newspaper import Article
import nltk

# NLTK punkt is required for newspaper3k's built-in summarization feature
try:
    nltk.download('punkt', quiet=True)
except Exception:
    pass

# Load environment variables
load_dotenv()
API_KEY = os.getenv("NEWS_API_KEY")

def fetch_and_process_news():
    """
    Fetches top headlines, scrapes the full text, and uses NLP to summarize them.
    """
    if not API_KEY:
        print("Error: Please set your NEWS_API_KEY in the .env file.")
        return []

    print("Initializing Lightweight NLP Summarizer...\n")
    
    # Initialize the client
    newsapi = NewsApiClient(api_key=API_KEY)

    print("Fetching breaking headlines...\n")
    try:
        # Fetch top headlines
        response = newsapi.get_top_headlines(language='en', page_size=2)
        
        if response['status'] == 'ok':
            articles = response['articles']
            
            for i, article_data in enumerate(articles, 1):
                url = article_data['url']
                title = article_data['title']
                
                print(f"{'='*50}")
                print(f"Article {i}: {title}")
                print(f"Link: {url}")
                print("Status: Scraping and Summarizing...")
                
                try:
                    # Configure scraper to look like a real Google Chrome browser
                    # This prevents websites like Bloomberg from blocking us!
                    from newspaper import Config
                    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'
                    config = Config()
                    config.browser_user_agent = user_agent
                    config.request_timeout = 10
                    
                    # Scraping: Download and Parse the full article
                    article = Article(url, config=config)
                    article.download()
                    article.parse()
                    
                    full_text = article.text
                    
                    if len(full_text) < 150:
                        print("Result: Article text was too short or blocked. Skipping.\n")
                        continue
                    
                    # Extract NLP features
                    article.nlp()
                    
                    summary = article.summary
                    keywords = article.keywords
                    
                    # Formatting the output
                    print(f"\n[*] Extracted Keywords: {', '.join(keywords[:5])}")
                    print(f"[*] Quick Summary:\n {summary[:500]}...\n")
                    
                except Exception as scrape_error:
                    print(f"Result:Failed to process this article. Error: {scrape_error}\n")
            
        else:
            print("Failed to fetch news from NewsAPI.")
            
    except Exception as e:
        print(f"An API error occurred: {e}")

if __name__ == "__main__":
    fetch_and_process_news()
