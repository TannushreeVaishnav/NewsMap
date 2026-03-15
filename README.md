# Global Geo-News Map Dashboard 
**Live Demo:** [https://newsmap-if9v.onrender.com/](https://newsmap-if9v.onrender.com/)

An interactive, full-stack web application that fetches live breaking news, processes the articles using NLP to extract their geographic locations, and visualizes them on an interactive global map. 

I built this project to bridge the gap between heavy, text-dense news aggregators and spatial data visualization, giving users an instant "birds-eye view" of world events.

![Map Dashboard Preview](preview.png)

---

## Key Features

* **Interactive Global Mapping:** Replaced traditional list-based feeds with a dynamic `Leaflet.js` map. News articles are rendered as color-coded pins based on their category (Technology, Politics, Health, etc.).
* **AI/NLP Processing Pipeline:** Uses `spaCy` (Named Entity Recognition) to scan article titles and summaries, automatically pinpointing the primary geographic region (GPE) being discussed.
* **Extractive Summarization:** Integrates `newspaper3k` to scrape raw article HTML and generate 1-2 sentence summaries, so users don't have to read the full text just to understand the context.
* **Concurrent Processing:** Implemented Python's `ThreadPoolExecutor` to fetch and parse up to 10 articles concurrently. This decreased the API response time by over 80% compared to sequential processing.
* **Daemon Background Caching:** Engineered a background thread that pre-fetches and caches global news every 4 hours. This achieves instant `<100ms` frontend load times and entirely avoids third-party rate limits.
* **Production Deployment:** Containerized the entire application stack using Docker and deployed it via a `gunicorn` WSGI server.

---

## Tech Stack & Architecture

**Backend (Python/Flask)**
* **Flask & Gunicorn:** Handles API routing and serves the application in a production environment.
* **Concurrent.futures:** Powers the multi-threaded web scraping engine.
* **NewsAPI:** Serves as the primary data ingestion source for live headlines.

**Data & NLP**
* **SpaCy (en_core_web_sm):** performs NER (Named Entity Recognition) to extract physical locations from unstructured string data.
* **Newspaper3k & NLTK:** Handles the heavy lifting of downloading raw HTML, parsing the DOM tree, and summarizing the text.
* **Geopy (Nominatim):** Translates extracted city/country names into exact `[Latitude, Longitude]` coordinates.

**Frontend (JavaScript/HTML/CSS)**
* **Leaflet.js & CARTO Voyager:** Renders the map UI and handles clustered plotting of custom SVG markers.

**DevOps**
* **Docker:** Containerized for predictable, OS-agnostic deployments.

---

## Technical Challenges & Lessons Learned

**1. The API Rate-Limiting Bottleneck**
* **Problem:** Every time a user loaded the map, the backend fetched news, scraped it, parsed the NLP, and Geocoded the locations. This was slow and rapidly exhausted my free-tier daily API limits.
* **Solution:** I decoupled the data ingestion from the user request. I built a background Daemon thread (`threading.Thread`) that silently wakes up every 4 hours, processes all categories, and stores the processed JSON objects into a shared memory dictionary (`NEWS_CACHE`). Now, when a user clicks a button, the Flask endpoint instantly serves the cached JSON.

**2. Network Bound Latency**
* **Problem:** Downloading 15 external article webpages and running them through the NER parser sequentially took roughly 15-20 seconds per category.
* **Solution:** I implemented `concurrent.futures.ThreadPoolExecutor(max_workers=10)`. By mapping my processing function across the dataset, the system waits for all network requests in parallel, dropping the total processing time down right to the speed of the slowest individual article.

**3. Location Accuracy**
* **Problem:** Scanning the entire article body for locations yielded far too much noise (e.g., passing mentions of foreign countries). 
* **Solution:** I adjusted the NLP weighting system to strictly evaluate the Article **Title** and **Summary**, multiplying the Title's entities by a weight of 3 before running a `Counter().most_common()` check. This resulted in highly accurate, primary-subject geolocation.

---

## How to Run Locally

If you'd like to run this environment on your own machine:

**1. Clone the repository**
```bash
git clone https://github.com/yourusername/geo-news-dashboard.git
cd geo-news-dashboard
```

**2. Setup the Environment**
Create a `.env` file in the root directory and add your NewsAPI key:
```env
NEWS_API_KEY=your_api_key_here
```

**3. Run via Docker**
```bash
docker build -t geo-news-dashboard .
docker run -p 5000:5000 --env-file .env geo-news-dashboard
```

**4. Or Run Manually using Python**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python app.py
```

Finally, open your browser and navigate to `http://localhost:5000`.
