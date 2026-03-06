import re
import uuid
import hashlib
from src.core.logger import logging


# =========================================================
# CONTEXT-AWARE STARTUP MATCHING (Regex with Word Boundaries)
# =========================================================
def find_startups_in_text(text: str, candidates: list) -> list:
    """
    Confirms which candidate startups are actually mentioned in the article text,
    using regex word-boundary matching.

    This is CONTEXT-AWARE — it only checks the 1–3 startups that were part of the
    NewsAPI query that produced this article, not all 37+ startups in the DB.
    This prevents false positives like 'StripeAPI' matching 'Stripe'.

    Args:
        text:       Article text to search (title + content combined).
        candidates: List of startup dicts [{"id": "...", "name": "..."}, ...]
                    (the startups that were in the query that fetched this article)

    Returns:
        List of matched startup dicts. Empty list if none confirmed.
    """
    if not text or not candidates:
        return []

    found = []
    for startup in candidates:
        name = startup.get('name', '')
        if not name:
            continue
        # \b enforces word boundaries — "Stripe" won't match inside "StripeAPI"
        pattern = r'\b' + re.escape(name) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            found.append(startup)

    return found


# =========================================================
# DETERMINISTIC STARTUP ID GENERATOR
# =========================================================
def generate_startup_id(name: str, sector_id: str) -> str:
    """
    Generates a deterministic, readable, unique ID based on startup name and sector ID.
    Example: swiggy-51f4a2-9f2d

    Used by streamlit_admin.py when adding/updating startups.
    """
    base_str = f"{name.lower()}|{str(sector_id).lower()}"

    namespace = uuid.UUID("12345678-1234-5678-1234-567812345678")
    stable_uuid = uuid.uuid5(namespace, base_str)

    short_hash = hashlib.md5(base_str.encode()).hexdigest()[:6]
    suffix = str(stable_uuid).split('-')[-1][:4]

    readable_name = name.lower().replace(" ", "-").replace(".", "")
    final_id = f"{readable_name}-{short_hash}-{suffix}"
    return final_id
