import requests
from requests.adapters import HTTPAdapter, Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
from itertools import cycle, groupby
from operator import itemgetter
from datetime import datetime, timedelta
from src.core.config import settings
from src.core.logger import logging
from src.constants import FETCH_TIMEOUT, API_PAGE_SIZE, THREAD_COUNT

# Max startups per API query to avoid 400 Bad Request (URL too long)
MAX_STARTUPS_PER_QUERY = 3

# Domains excluded from NewsAPI results — non-news sources like package repos,
# code hosting, developer forums, and social media.
EXCLUDED_DOMAINS = ",".join([
    "github.com",
    "gitlab.com",
    "githubusercontent.com",
    "pypi.org",
    "python.org",
    "readthedocs.io",
    "stackoverflow.com",
    "stackexchange.com",
    "npmjs.com",
    "reddit.com",
    "news.ycombinator.com",
    "wikipedia.org",
    "youtube.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
])

def _chunk_list(lst, chunk_size):
    """Split a list into chunks of a given max size."""
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

# =========================================================
# SETUP: Session with Retry Adapter
# =========================================================
session = requests.Session()
retries = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)
adapter = HTTPAdapter(max_retries=retries)
session.mount("https://", adapter)
session.mount("http://", adapter)

# =========================================================
# KEY ROTATION (Thread-safe round-robin across API keys)
# =========================================================
api_keys = settings.NEWS_API_KEYS
if not api_keys or len(api_keys) == 0:
    raise ValueError("No NEWS_API_KEYS provided in .env")

_key_cycle = cycle(api_keys)
_key_lock = threading.Lock()

def get_api_key():
    """Return the next NewsAPI key (thread-safe round-robin)."""
    with _key_lock:
        return next(_key_cycle)

# =========================================================
# BUILD NEWSAPI QUERIES
# =========================================================
def build_sector_queries(all_startups_data, existing_startup_ids):
    """
    Builds smart queries based on the logic:
    - New Startups (not in existing_ids): Fetch 30 days of news
    - Existing Startups (in existing_ids): Fetch 1 day of news

    Query Format: (Startup A OR Startup B) AND ("Sector" OR "Keyword1" OR "Keyword2")

    Returns:
        List of tuples: (query_string, from_date, to_date, candidate_startups)
        where candidate_startups is the list of startup dicts in this query chunk.
    """
    logging.info("Building API queries with 1-day/30-day logic...")

    # 1. Separate startups into new vs. existing
    new_startups = []
    existing_startups = []

    for startup in all_startups_data:
        if startup['id'] in existing_startup_ids:
            existing_startups.append(startup)
        else:
            new_startups.append(startup)

    logging.info(f"Found {len(new_startups)} new startups (30-day) and {len(existing_startups)} existing startups (1-day).")

    # 2. Define dates
    today = datetime.now()
    one_day_ago = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    # 28 days keeps us safely within the NewsAPI free plan 29-day limit
    thirty_days_ago = (today - timedelta(days=28)).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    # 3. Create query groups (sectorId, from_date, startups_list)
    query_groups = []

    if new_startups:
        sorted_new = sorted(new_startups, key=itemgetter('sectorId'))
        for sector_id, group in groupby(sorted_new, key=itemgetter('sectorId')):
            for chunk in _chunk_list(list(group), MAX_STARTUPS_PER_QUERY):
                query_groups.append((sector_id, thirty_days_ago, today_str, chunk))

    if existing_startups:
        sorted_existing = sorted(existing_startups, key=itemgetter('sectorId'))
        for sector_id, group in groupby(sorted_existing, key=itemgetter('sectorId')):
            for chunk in _chunk_list(list(group), MAX_STARTUPS_PER_QUERY):
                query_groups.append((sector_id, one_day_ago, today_str, chunk))

    # 4. Build the final query tuples — NOW INCLUDING candidate_startups
    final_queries = []

    for sector_id, from_date, to_date, startups_in_group in query_groups:

        startup_names = [f'"{s["name"]}"' for s in startups_in_group]
        startup_query = " OR ".join(startup_names)

        all_keywords = {s['sectorName'] for s in startups_in_group if s['sectorName']}
        for s in startups_in_group:
            all_keywords.update(s.get('findingKeywords') or [])

        quoted_keywords = [f'"{k}"' for k in all_keywords if k]

        if not quoted_keywords:
            logging.warning(f"No sector or keywords for sectorId {sector_id}, skipping.")
            continue

        keyword_query = " OR ".join(quoted_keywords)
        final_query_str = f"({startup_query}) AND ({keyword_query})"

        # Extract minimal startup info needed for matching + sentiment
        candidate_startups = [{"id": s["id"], "name": s["name"]} for s in startups_in_group]

        logging.info(f"Built query for sector {sector_id} ({from_date}): {final_query_str}")
        final_queries.append((final_query_str, from_date, to_date, candidate_startups))

    return final_queries

# =========================================================
# FETCH ARTICLES (Single Query)
# =========================================================
def fetch_sector_articles(query, from_date, to_date, candidate_startups):
    """
    Fetch all articles for a given query and date range with pagination.

    Args:
        query:              The NewsAPI query string.
        from_date:          Start date (YYYY-MM-DD).
        to_date:            End date (YYYY-MM-DD).
        candidate_startups: List of startup dicts that were in this query.

    Returns:
        List of (article_dict, candidate_startups) tuples.
        Each article is tagged with the startups it was fetched for.
    """
    query_log_name = f'query "{query[:50]}..."'
    logging.info(f"Fetching articles for {query_log_name} (from: {from_date})")

    tagged_articles = []
    page = 1

    while True:
        api_key = get_api_key()
        params = {
            "q": query,
            "language": "en",
            "from": from_date,
            "to": to_date,
            "sortBy": "publishedAt",
            "searchIn": "title,description",
            "pageSize": API_PAGE_SIZE,
            "page": page,
            "apiKey": api_key,
            "excludeDomains": EXCLUDED_DOMAINS,
        }

        try:
            response = session.get(
                "https://newsapi.org/v2/everything",
                params=params,
                timeout=FETCH_TIMEOUT,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logging.warning(f"Request failed for {query_log_name} page {page}: {e}")
            break

        data = response.json()
        if "articles" not in data or not data["articles"]:
            break

        articles = data["articles"]
        # Tag each article with this query's candidate startups
        tagged_articles.extend((article, candidate_startups) for article in articles)
        logging.info(f"{len(articles)} articles fetched for {query_log_name} (page {page})")

        if len(articles) < API_PAGE_SIZE:
            break

        page += 1
        time.sleep(1.2)

    logging.info(f"Total fetched for {query_log_name}: {len(tagged_articles)} articles.")
    return tagged_articles

# =========================================================
# MULTI-THREADED FETCHING (Sector-Level)
# =========================================================
def fetch_articles_threaded(sector_queries):
    """
    sector_queries: list of tuples (query_string, from_date, to_date, candidate_startups)
    Runs each query in its own thread and aggregates tagged results.

    Returns:
        Flat list of (article_dict, candidate_startups) tuples.
    """
    all_tagged_articles = []

    with ThreadPoolExecutor(max_workers=THREAD_COUNT) as executor:
        futures = {
            executor.submit(fetch_sector_articles, query, from_date, to_date, candidates): query
            for query, from_date, to_date, candidates in sector_queries
        }

        for future in as_completed(futures):
            query_str = futures[future]
            try:
                tagged = future.result()
                all_tagged_articles.extend(tagged)
                logging.info(f"Completed sector fetch: {query_str[:50]}... ({len(tagged)} articles)")
            except Exception as e:
                logging.error(f"Failed to fetch sector query {query_str[:50]}...: {e}")

    logging.info(f"Total fetched across sectors: {len(all_tagged_articles)} articles.")
    return all_tagged_articles

# =========================================================
# DEDUPLICATION BY URL (with Candidate Merging)
# =========================================================
def deduplicate_articles(tagged_articles):
    """
    Deduplicates tagged articles by URL. If the same URL appears across multiple
    queries (e.g., an article mentioning both Stripe and Paytm), the candidate
    startup lists are MERGED so no association is lost.

    Args:
        tagged_articles: List of (article_dict, candidate_startups) tuples.

    Returns:
        Dict { url: {"article": article_dict, "candidates": [startup_dict, ...]} }
    """
    unique = {}
    for article, candidates in tagged_articles:
        url = article.get("url")
        if not url:
            continue

        if url not in unique:
            unique[url] = {
                "article": article,
                "candidates": list(candidates)
            }
        else:
            # Merge candidates from multiple queries — deduplicate by startup id
            existing_ids = {c['id'] for c in unique[url]['candidates']}
            for c in candidates:
                if c['id'] not in existing_ids:
                    unique[url]['candidates'].append(c)
                    existing_ids.add(c['id'])

    logging.info(f"Deduplicated articles: {len(unique)} unique URLs.")
    return unique
