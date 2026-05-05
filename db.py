"""
SQLite Database Layer for Geo-News Dashboard.
Stores fetched news articles so the API can serve them in milliseconds
instead of waiting for live scraping + geocoding on every request.

Tables:
    - articles: Stores processed news articles with geo-tags
    - geocode_cache: Caches location lookups to avoid repeated Nominatim calls
    - fetch_log: Tracks when each category was last refreshed
"""

import sqlite3
import json
import os
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news_cache.db")


def get_connection() -> sqlite3.Connection:
    """Get a new SQLite connection with WAL mode for concurrent reads."""
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")       # Allow concurrent reads during writes
    conn.execute("PRAGMA synchronous=NORMAL")      # Faster writes, still safe
    conn.execute("PRAGMA cache_size=-8000")         # 8MB cache
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                image_url TEXT DEFAULT '',
                source TEXT DEFAULT 'Unknown',
                published_at TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                keywords TEXT DEFAULT '[]',
                location_name TEXT,
                location_lat REAL,
                location_lon REAL,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fetch_date DATE NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_articles_category_date 
                ON articles(category, fetch_date);
            
            CREATE INDEX IF NOT EXISTS idx_articles_url 
                ON articles(url);

            CREATE TABLE IF NOT EXISTS geocode_cache (
                query TEXT PRIMARY KEY,
                address TEXT,
                lat REAL,
                lon REAL,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS fetch_log (
                category TEXT PRIMARY KEY,
                last_fetched_at TIMESTAMP NOT NULL,
                article_count INTEGER DEFAULT 0
            );
        """)
        conn.commit()
        logger.info(f"Database initialized at: {DB_PATH}")
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
#  ARTICLE CRUD OPERATIONS
# ─────────────────────────────────────────────────────────────

def save_articles(category: str, articles: List[Dict[str, Any]]):
    """
    Save a batch of processed articles for a category.
    Replaces today's articles for that category to avoid duplicates.
    """
    conn = get_connection()
    today = date.today().isoformat()
    try:
        # Remove today's old articles for this category (fresh replacement)
        conn.execute(
            "DELETE FROM articles WHERE category = ? AND fetch_date = ?",
            (category, today)
        )

        for art in articles:
            location = art.get("location")
            conn.execute("""
                INSERT INTO articles 
                    (category, title, url, image_url, source, published_at,
                     summary, keywords, location_name, location_lat, location_lon, fetch_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                category,
                art.get("title", ""),
                art.get("url", ""),
                art.get("image_url", ""),
                art.get("source", "Unknown"),
                art.get("published_at", ""),
                art.get("summary", ""),
                json.dumps(art.get("keywords", [])),
                location["name"] if location else None,
                location["lat"] if location else None,
                location["lon"] if location else None,
                today
            ))

        # Update the fetch log
        conn.execute("""
            INSERT OR REPLACE INTO fetch_log (category, last_fetched_at, article_count)
            VALUES (?, ?, ?)
        """, (category, datetime.now().isoformat(), len(articles)))

        conn.commit()
        logger.info(f"Saved {len(articles)} articles for '{category}' to database")

    except Exception as e:
        logger.error(f"DB save error: {e}")
        conn.rollback()
    finally:
        conn.close()


def get_articles(category: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve the most recently fetched articles for a category from the database.
    Returns the response dict or None if no data exists.
    """
    conn = get_connection()
    try:
        # Get the most recent fetch date
        latest_row = conn.execute(
            "SELECT MAX(fetch_date) as max_date FROM articles WHERE category = ?",
            (category,)
        ).fetchone()
        
        if not latest_row or not latest_row["max_date"]:
            return None
            
        max_date = latest_row["max_date"]
        
        rows = conn.execute(
            "SELECT * FROM articles WHERE category = ? AND fetch_date = ? ORDER BY id",
            (category, max_date)
        ).fetchall()

        if not rows:
            return None

        articles = []
        for row in rows:
            article = {
                "title": row["title"],
                "url": row["url"],
                "image_url": row["image_url"],
                "source": row["source"],
                "published_at": row["published_at"],
                "summary": row["summary"],
                "keywords": json.loads(row["keywords"]) if row["keywords"] else [],
                "location": None
            }
            if row["location_lat"] is not None and row["location_lon"] is not None:
                article["location"] = {
                    "name": row["location_name"],
                    "lat": row["location_lat"],
                    "lon": row["location_lon"]
                }
            articles.append(article)

        return {
            "status": "success",
            "category": category,
            "total_results": len(articles),
            "articles": articles
        }

    finally:
        conn.close()


def get_last_fetch_time(category: str) -> Optional[datetime]:
    """Get the last time a category was refreshed."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT last_fetched_at FROM fetch_log WHERE category = ?",
            (category,)
        ).fetchone()
        if row:
            return datetime.fromisoformat(row["last_fetched_at"])
        return None
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
#  GEOCODE CACHE OPERATIONS
# ─────────────────────────────────────────────────────────────

def get_cached_geocode(query: str) -> Optional[Dict[str, Any]]:
    """Check if a location has already been geocoded before."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT address, lat, lon FROM geocode_cache WHERE query = ?",
            (query,)
        ).fetchone()
        if row:
            return {
                "name": row["address"],
                "lat": row["lat"],
                "lon": row["lon"]
            }
        return None
    finally:
        conn.close()


def save_geocode(query: str, address: str, lat: float, lon: float):
    """Save a geocoded location for future instant lookups."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO geocode_cache (query, address, lat, lon, cached_at) VALUES (?, ?, ?, ?, ?)",
            (query, address, lat, lon, datetime.now().isoformat())
        )
        conn.commit()
    except Exception as e:
        logger.warning(f"Geocode cache save failed: {e}")
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
#  CLEANUP / ARCHIVAL
# ─────────────────────────────────────────────────────────────

def cleanup_old_articles(keep_days: int = 3):
    """
    Remove articles older than `keep_days` to keep the DB small.
    Called at midnight by the scheduler.
    """
    conn = get_connection()
    try:
        cutoff = date.today().isoformat()
        result = conn.execute(
            "DELETE FROM articles WHERE fetch_date < date(?, ?)",
            (cutoff, f"-{keep_days} days")
        )
        deleted = result.rowcount
        conn.execute("VACUUM")  # Reclaim disk space
        conn.commit()
        logger.info(f"Cleanup: removed {deleted} articles older than {keep_days} days")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
    finally:
        conn.close()


def get_db_stats() -> Dict[str, Any]:
    """Get database statistics for the metrics endpoint."""
    conn = get_connection()
    try:
        total_articles = conn.execute("SELECT COUNT(*) as cnt FROM articles").fetchone()["cnt"]
        today_articles = conn.execute(
            "SELECT COUNT(*) as cnt FROM articles WHERE fetch_date = ?",
            (date.today().isoformat(),)
        ).fetchone()["cnt"]
        cached_locations = conn.execute("SELECT COUNT(*) as cnt FROM geocode_cache").fetchone()["cnt"]
        
        # DB file size
        db_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024) if os.path.exists(DB_PATH) else 0

        categories = conn.execute("""
            SELECT category, last_fetched_at, article_count 
            FROM fetch_log ORDER BY last_fetched_at DESC
        """).fetchall()

        return {
            "total_articles": total_articles,
            "today_articles": today_articles,
            "cached_locations": cached_locations,
            "db_size_mb": round(db_size_mb, 2),
            "categories": [
                {
                    "name": row["category"],
                    "last_fetched": row["last_fetched_at"],
                    "count": row["article_count"]
                } for row in categories
            ]
        }
    finally:
        conn.close()
