"""
admin/startup_helpers.py
Business logic for creating and processing startup records.
No Streamlit UI code here — only pure data helpers.
"""
import streamlit as st
from src.utils import db_utils, text_utils


def build_startup_dict(
    name: str,
    sector_name: str,
    sector_name_to_id: dict,
    description: str,
    keywords_str: str,
    image_url: str,
) -> dict | None:
    """
    Validates inputs and builds a startup dict ready for db_utils.upsert_startup().
    Returns None and shows an st.error if validation fails.
    """
    if not name or not sector_name or not description:
        st.error("Please fill in all required fields: Name, Sector, and Description.")
        return None

    sector_id = sector_name_to_id.get(sector_name)
    if not sector_id:
        st.error(f"Sector '{sector_name}' not found in DB.")
        return None

    keywords_list = [k.strip() for k in keywords_str.split(",") if k.strip()]
    startup_id = text_utils.generate_startup_id(name, str(sector_id))

    return {
        "id": startup_id,
        "name": name,
        "sectorId": sector_id,
        "description": description,
        "imageUrl": image_url,
        "findingKeywords": keywords_list,
    }


def upsert_single_startup(startup_dict: dict) -> bool:
    """
    Opens a DB connection, upserts a startup, commits, and closes.
    Shows st.success / st.error based on result.
    Returns True on success.
    """
    conn = None
    try:
        conn = db_utils.get_connection()
        db_utils.upsert_startup(conn, startup_dict)
        conn.commit()
        st.success(f"✅ Saved: **{startup_dict['name']}**")
        st.caption(f"ID: `{startup_dict['id']}`")
        return True
    except Exception as e:
        if conn: conn.rollback()
        st.error(f"An error occurred: {e}")
        return False
    finally:
        if conn: conn.close()


def process_startup_from_json(startup: dict, sector_name_to_id: dict, conn) -> bool:
    """
    Processes a single startup dict from a bulk JSON upload.
    Uses a shared connection (caller commits after all rows).
    """
    name = startup.get("name")
    sector_name = startup.get("sector")
    description = startup.get("description")

    if not name or not sector_name or not description:
        st.warning(f"Skipping `{name or 'Unknown'}` — missing name, sector, or description.")
        return False

    sector_id = sector_name_to_id.get(sector_name)
    if not sector_id:
        st.warning(f"Skipping `{name}` — sector '{sector_name}' not found in DB.")
        return False

    startup_id = text_utils.generate_startup_id(name, str(sector_id))
    db_utils.upsert_startup(conn, {
        "id": startup_id,
        "name": name,
        "sectorId": sector_id,
        "description": description,
        "imageUrl": startup.get("imageUrl", ""),
        "findingKeywords": startup.get("keywords", []),
    })
    return True
