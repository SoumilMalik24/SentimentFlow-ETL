import sys
from os.path import dirname, abspath

# Add the project root to the Python path
project_root = dirname(dirname(abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.core.logger import logging
from src.utils import api_utils, db_utils, sentiment_utils, text_utils


def main_pipeline():
    """
    Runs the full E-T-L pipeline for SentimentFlow.

    Steps:
      1. Connect to DB and fetch startup/sector data
      2. Build NewsAPI queries (1-day for existing, 30-day for new startups)
      3. Fetch articles (threaded) — each article is tagged with its query's candidate startups
      4. Deduplicate by URL — merging candidates across overlapping queries
      5. Insert new articles into DB
      6. Confirm startup presence using regex word-boundary matching (context-aware)
      7. Run bulk NLI sentiment analysis
      8. Batch insert sentiment records and commit
    """
    logging.info("===== STARTING SENTIMENT FLOW PIPELINE =====")
    conn = None
    try:
        # =========================================================
        # STEP 1: Connect and Fetch Initial Data
        # =========================================================
        conn = db_utils.get_connection()
        if conn is None:
            raise Exception("Failed to get database connection.")

        all_startups_data = db_utils.fetch_startups_for_api(conn)
        existing_startup_ids = db_utils.fetch_startup_ids_with_sentiment(conn)

        if not all_startups_data:
            logging.error("No startups found in 'Startups' table. Exiting.")
            return

        # =========================================================
        # STEP 2: Build API Queries (with candidate startup lists)
        # =========================================================
        sector_queries = api_utils.build_sector_queries(
            all_startups_data,
            existing_startup_ids
        )

        if not sector_queries:
            logging.error("No API queries could be built. Exiting.")
            return

        # =========================================================
        # STEP 3: Fetch Articles (threaded) — tagged with candidates
        # Each result: (article_dict, [candidate_startup_dict, ...])
        # =========================================================
        tagged_articles = api_utils.fetch_articles_threaded(sector_queries)

        # =========================================================
        # STEP 4: Deduplicate by URL — merging candidates
        # Result: { url: {"article": {...}, "candidates": [...]} }
        # =========================================================
        unique_tagged = api_utils.deduplicate_articles(tagged_articles)

        existing_urls = db_utils.fetch_existing_urls(conn)

        new_tagged = {
            url: data
            for url, data in unique_tagged.items()
            if url not in existing_urls
        }

        if not new_tagged:
            logging.info("No new articles found. Pipeline complete.")
            return

        logging.info(f"Found {len(new_tagged)} new articles to process.")

        # =========================================================
        # STEP 5: Insert New Articles into DB
        # =========================================================
        new_article_data = [data['article'] for data in new_tagged.values()]
        db_utils.batch_insert_articles(conn, new_article_data)

        new_urls = list(new_tagged.keys())
        articles_from_db = db_utils.get_articles_by_urls(conn, new_urls)

        # =========================================================
        # STEP 6: Context-Aware Startup Matching (Regex)
        # Only checks the 1–3 candidate startups per article,
        # not all 37+ in the DB. Enforces word boundaries so
        # "OpenAIChat" does NOT match "OpenAI".
        # =========================================================
        logging.info("Confirming startup mentions using context-aware regex matching...")
        articles_to_process = []

        for url, tagged_data in new_tagged.items():
            article_row = articles_from_db.get(url)
            if not article_row:
                continue

            try:
                text_to_search = f"{article_row['title']}. {article_row['content']}"
                candidates = tagged_data['candidates']
                confirmed_startups = text_utils.find_startups_in_text(text_to_search, candidates)

                if not confirmed_startups:
                    logging.info(
                        f"No startup name confirmed in: {article_row.get('title', 'No Title')[:40]}... "
                        f"(candidates checked: {[c['name'] for c in candidates]})"
                    )
                    continue

                articles_to_process.append({
                    "article": article_row,
                    "startups_to_analyze": confirmed_startups
                })
                logging.info(
                    f"Confirmed {len(confirmed_startups)} startup(s) in: "
                    f"{article_row.get('title', 'No Title')[:40]}... "
                    f"→ {[s['name'] for s in confirmed_startups]}"
                )

            except Exception as e:
                logging.error(f"Failed to match startups in article {url}: {e}")

        # =========================================================
        # STEP 7: Run Bulk NLI Sentiment Analysis
        # =========================================================
        if not articles_to_process:
            logging.info("No startups confirmed in any new articles. Pipeline complete.")
            return

        all_sentiment_records = sentiment_utils.analyze_all_articles_in_bulk(articles_to_process)

        # =========================================================
        # STEP 8: Batch Insert All Sentiments and Commit
        # =========================================================
        if not all_sentiment_records:
            logging.info("No new sentiment records to insert.")
        else:
            logging.info(f"Batch inserting {len(all_sentiment_records)} sentiment records...")
            db_utils.batch_insert_article_sentiments(conn, all_sentiment_records)

        logging.info("Committing transaction...")
        conn.commit()
        logging.info("===== SENTIMENT FLOW PIPELINE FINISHED SUCCESSFULLY =====")

    except Exception as e:
        logging.critical(f"Pipeline failed critically: {e}", exc_info=True)
        if conn:
            logging.warning("Rolling back transaction...")
            conn.rollback()
    finally:
        if conn:
            conn.close()
            logging.info("Database connection closed.")


if __name__ == "__main__":
    # To run: python -m src.pipeline
    main_pipeline()
