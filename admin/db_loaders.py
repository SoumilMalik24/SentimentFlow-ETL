"""
admin/db_loaders.py
Cached Streamlit data loaders — thin wrappers around db_utils
that handle connection lifecycle and st.cache_data.
"""
import streamlit as st
from src.utils import db_utils


@st.cache_data(ttl=600)
def get_sectors():
    """Fetches all sectors. Cached for 10 minutes."""
    conn = None
    try:
        conn = db_utils.get_connection()
        return db_utils.fetch_all_sectors(conn)
    except Exception as e:
        st.error(f"Failed to fetch sectors: {e}")
        return []
    finally:
        if conn: conn.close()


@st.cache_data(ttl=300)
def get_all_startups():
    """Fetches all startups with imageUrl. Cached for 5 minutes."""
    conn = None
    try:
        conn = db_utils.get_connection()
        return db_utils.fetch_all_startups(conn)
    except Exception as e:
        st.error(f"Failed to fetch startups: {e}")
        return []
    finally:
        if conn: conn.close()
