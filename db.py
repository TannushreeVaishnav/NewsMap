"""
SQLite Database Layer for Geo-News Dashboard.
Stores fetched news articles so the API can serve them in milliseconds
instead of waiting for live scraping + geocoding on every request.

Tables:
    - articles:       Processed news articles with geo-tags, sentiment, cluster info
    - geocode_cache:  Caches location lookups to avoid repeated Nominatim calls
    - fetch_log:      Tracks when each category was last refreshed (for stale-while-revalidate)
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
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-8000")
    return conn


def init_db():
    """Create all tables if they don't exist, and migrate schema for new columns."""
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
                sentiment_score REAL DEFAULT 0.0,
                cluster_id TEXT DEFAULT NULL,
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
                article_count INTEGER DEFAULT 0,
                etag TEXT DEFAULT NULL
            );
        """)
        # Migrate existing tables to add new columns if they don't exist
        _migrate_schema(conn)
        conn.commit()
        logger.info(f"Database initialized at: {DB_PATH}")
    finally:
        conn.close()


def _migrate_schema(conn: sqlite3.Connection):
    """Safely add new columns to existing tables without data loss."""
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(articles)").fetchall()}
    migrations = [
        ("sentiment_score", "REAL DEFAULT 0.0"),
        ("cluster_id", "TEXT DEFAULT NULL"),
    ]
    for col_name, col_def in migrations:
        if col_name not in existing_cols:
            conn.execute(f"ALTER TABLE articles ADD COLUMN {col_name} {col_def}")
            logger.info(f"Schema migrated: added column '{col_name}' to articles")

    fetch_log_cols = {row[1] for row in conn.execute("PRAGMA table_info(fetch_log)").fetchall()}
    if "etag" not in fetch_log_cols:
        conn.execute("ALTER TABLE fetch_log ADD COLUMN etag TEXT DEFAULT NULL")


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
        conn.execute(
            "DELETE FROM articles WHERE category = ? AND fetch_date = ?",
            (category, today)
        )

        for art in articles:
            location = art.get("location")
            conn.execute("""
                INSERT INTO articles
                    (category, title, url, image_url, source, published_at,
                     summary, keywords, location_name, location_lat, location_lon,
                     sentiment_score, cluster_id, fetch_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                art.get("sentiment_score", 0.0),
                art.get("cluster_id", None),
                today
            ))

        # Compute a simple ETag from count + current timestamp
        etag = f"{category}-{len(articles)}-{today}"
        conn.execute("""
            INSERT OR REPLACE INTO fetch_log (category, last_fetched_at, article_count, etag)
            VALUES (?, ?, ?, ?)
        """, (category, datetime.now().isoformat(), len(articles), etag))

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
    Also returns an ETag for conditional requests.
    """
    conn = get_connection()
    try:
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

        # Fetch ETag
        etag_row = conn.execute(
            "SELECT etag FROM fetch_log WHERE category = ?", (category,)
        ).fetchone()
        etag = etag_row["etag"] if etag_row else None

        articles = [_row_to_article(row) for row in rows]

        return {
            "status": "success",
            "category": category,
            "total_results": len(articles),
            "articles": articles,
            "etag": etag,
            "fetch_date": max_date
        }

    finally:
        conn.close()


def _row_to_article(row) -> Dict[str, Any]:
    """Convert a DB row to an article dict."""
    article = {
        "title": row["title"],
        "url": row["url"],
        "image_url": row["image_url"],
        "source": row["source"],
        "published_at": row["published_at"],
        "summary": row["summary"],
        "keywords": json.loads(row["keywords"]) if row["keywords"] else [],
        "sentiment_score": row["sentiment_score"] if row["sentiment_score"] is not None else 0.0,
        "cluster_id": row["cluster_id"],
        "location": None
    }
    if row["location_lat"] is not None and row["location_lon"] is not None:
        article["location"] = {
            "name": row["location_name"],
            "lat": row["location_lat"],
            "lon": row["location_lon"]
        }
    return article


def search_articles_local(query: str, limit: int = 15) -> List[Dict[str, Any]]:
    """
    TF-IDF powered local search across all cached articles.
    Falls back to simple LIKE substring match if scikit-learn is unavailable.
    Returns a list of article dicts sorted by relevance.
    """
    conn = get_connection()
    try:
        # Pull all cached article titles + summaries
        rows = conn.execute(
            "SELECT * FROM articles ORDER BY fetch_date DESC, id DESC LIMIT 500"
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        corpus = [
            f"{row['title']} {row['summary'] or ''}" for row in rows
        ]
        vectorizer = TfidfVectorizer(stop_words='english', max_features=5000)
        tfidf_matrix = vectorizer.fit_transform(corpus + [query])

        # Last vector = query; compute cosine similarity with all corpus entries
        query_vec = tfidf_matrix[-1]
        scores = cosine_similarity(query_vec, tfidf_matrix[:-1]).flatten()

        # Get top results with score > 0.01
        top_indices = np.argsort(scores)[::-1]
        results = []
        for idx in top_indices:
            if scores[idx] < 0.01:
                break
            if len(results) >= limit:
                break
            results.append(_row_to_article(rows[idx]))

        return results

    except ImportError:
        # Fallback: simple LIKE search
        conn2 = get_connection()
        try:
            like_query = f"%{query}%"
            fallback_rows = conn2.execute(
                "SELECT * FROM articles WHERE title LIKE ? OR summary LIKE ? ORDER BY fetch_date DESC LIMIT ?",
                (like_query, like_query, limit)
            ).fetchall()
            return [_row_to_article(r) for r in fallback_rows]
        finally:
            conn2.close()


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


def get_etag(category: str) -> Optional[str]:
    """Get the current ETag for a category."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT etag FROM fetch_log WHERE category = ?", (category,)
        ).fetchone()
        return row["etag"] if row else None
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
            return {"name": row["address"], "lat": row["lat"], "lon": row["lon"]}
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
    """Remove articles older than `keep_days` to keep the DB small."""
    conn = get_connection()
    try:
        cutoff = date.today().isoformat()
        result = conn.execute(
            "DELETE FROM articles WHERE fetch_date < date(?, ?)",
            (cutoff, f"-{keep_days} days")
        )
        deleted = result.rowcount
        conn.execute("VACUUM")
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
