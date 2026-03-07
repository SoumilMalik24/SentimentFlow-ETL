"""
streamlit_admin.py — SentimentFlow Admin Dashboard
Pure UI layer. All business logic lives in the admin/ package.

Pages (tabs):
  1. Add / Edit Startup       — single startup upsert with optional image upload
  2. Bulk Upload JSON         — batch upsert from a JSON file
  3. Upload Company Image     — Cloudinary image upload for startups missing an image
"""
import sys
import os
import json
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- Project module imports ---
try:
    from src.utils import db_utils
    from src.utils import text_utils
    from admin.db_loaders import get_sectors, get_all_startups
    from admin.cloudinary_utils import init_cloudinary, upload_to_cloudinary, image_crop_and_upload_widget
    from admin.startup_helpers import build_startup_dict, upsert_single_startup, process_startup_from_json
except ImportError as e:
    st.error(f"Failed to import project modules: {e}")
    st.error("Run streamlit from the project root: `streamlit run streamlit_admin.py`")
    st.stop()

# =========================================================
# Page Config
# =========================================================
st.set_page_config(
    page_title="SentimentFlow — Admin",
    page_icon="🛠️",
    layout="wide",
)

# =========================================================
# Cloudinary Init (once per app session)
# =========================================================
cloudinary_ready = init_cloudinary()

# =========================================================
# Page Header
# =========================================================
st.title("🛠️ SentimentFlow Admin Dashboard")
st.caption("Manage startups, bulk upload data, and update company images.")
st.divider()

# =========================================================
# Base Data
# =========================================================
sectors = get_sectors()
if not sectors:
    st.error("No sectors found. Please run `scripts/seed_sector.py` first.")
    st.stop()

sector_names      = [s["name"] for s in sectors]
sector_name_to_id = {s["name"]: s["id"] for s in sectors}

# =========================================================
# Tabs
# =========================================================
tab1, tab2, tab3 = st.tabs([
    "➕ Add / Edit Startup",
    "📂 Bulk Upload JSON",
    "🖼️ Upload Company Image",
])


# =========================================================================
# TAB 1 — Add / Edit Single Startup
# =========================================================================
with tab1:
    st.header("Add or Edit a Single Startup")
    st.markdown("`Name` + `Sector` generate a unique ID — same pair will **overwrite** an existing entry.")

    col_left, col_right = st.columns(2)
    with col_left:
        t1_name     = st.text_input("Startup Name *", key="t1_name")
        t1_sector   = st.selectbox("Sector *", options=sector_names, key="t1_sector")
        t1_keywords = st.text_input("Finding Keywords (comma-separated)", key="t1_keywords")
    with col_right:
        t1_desc      = st.text_area("Description *", height=130, key="t1_desc")
        t1_manual_url = st.text_input("Image URL (paste, or upload below)", key="t1_url")

    st.divider()

    # Optional image upload + 1:1 crop
    with st.expander("📷 Upload & Crop Image (optional)", expanded=False):
        if t1_name and t1_sector:
            _sid = text_utils.generate_startup_id(t1_name, str(sector_name_to_id.get(t1_sector, "")))
            _url = image_crop_and_upload_widget(_sid, "tab1", cloudinary_ready)
            if _url:
                st.session_state["t1_auto_image_url"] = _url
                st.info("Image uploaded! Click **Save Startup** below to commit.")
        else:
            st.info("Enter Name and Sector first to enable image upload.")

    final_image_url = st.session_state.get("t1_auto_image_url", "") or t1_manual_url

    st.divider()
    if st.button("💾 Save Startup", type="primary", key="t1_save"):
        startup_dict = build_startup_dict(
            t1_name, t1_sector, sector_name_to_id, t1_desc, t1_keywords, final_image_url
        )
        if startup_dict:
            if upsert_single_startup(startup_dict):
                st.session_state.pop("t1_auto_image_url", None)
                st.balloons()
                st.cache_data.clear()


# =========================================================================
# TAB 2 — Bulk Upload JSON
# =========================================================================
with tab2:
    st.header("Bulk Upload Startups via JSON")
    st.markdown("Upload a JSON file containing an array of startup objects.")

    with st.expander("📋 Example JSON format"):
        st.code("""
[
  {
    "name": "Swiggy",
    "sector": "FoodTech",
    "description": "An Indian online food ordering and delivery platform.",
    "keywords": ["food delivery", "quick commerce"],
    "imageUrl": "https://example.com/swiggy.png"
  }
]
        """, language="json")

    uploaded_json = st.file_uploader("Upload JSON file", type=["json"], key="bulk_json")
    if uploaded_json:
        if st.button("🚀 Process JSON File", type="primary"):
            conn = None
            try:
                try:
                    startups_list = json.load(uploaded_json)
                    if not isinstance(startups_list, list):
                        st.error("File must contain a JSON array.")
                        st.stop()
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON: {e}")
                    st.stop()

                with st.spinner(f"Processing {len(startups_list)} startups..."):
                    conn = db_utils.get_connection()
                    success = 0
                    bar = st.progress(0.0, "Starting...")
                    for i, s in enumerate(startups_list):
                        if process_startup_from_json(s, sector_name_to_id, conn):
                            success += 1
                        bar.progress((i + 1) / len(startups_list), f"Processing '{s.get('name', '...')}'")
                    conn.commit()
                    st.success(f"✅ Upserted **{success}** of **{len(startups_list)}** startups.")
                    st.cache_data.clear()
            except Exception as e:
                if conn: conn.rollback()
                st.error(f"An error occurred: {e}")
            finally:
                if conn: conn.close()


# =========================================================================
# TAB 3 — Upload Company Image (only startups missing an image)
# =========================================================================
with tab3:
    st.header("Upload Company Image")
    st.markdown("Shows only companies **without an image** set. Upload, crop to square, and save.")

    if not cloudinary_ready:
        st.error("Cloudinary not configured. Set credentials in `.env`.")
        st.stop()

    all_startups = get_all_startups()
    missing_image = [s for s in all_startups if not (s.get("imageUrl") or "").strip()]

    if not missing_image:
        st.success("🎉 All startups already have an image!")
        st.stop()

    st.info(f"**{len(missing_image)}** startup(s) still need an image.")

    options = {f"{s['sectorName'] or 'Unknown'}  —  {s['name']}": s for s in missing_image}
    selected = options[st.selectbox("Select Company", options=list(options.keys()))]

    st.divider()

    from PIL import Image as PILImage
    from streamlit_cropper import st_cropper
    import io

    uploaded = st.file_uploader("Upload image", type=["jpg", "jpeg", "png", "webp"], key="t3_file")

    if uploaded:
        pil = PILImage.open(uploaded).convert("RGB")
        st.markdown("**Crop to 1:1 square**")
        cropped = st_cropper(pil, realtime_update=True, box_color="#6C63FF", aspect_ratio=(1, 1), key="t3_crop")

        col_a, col_b = st.columns(2)
        with col_a:
            st.image(pil, caption="Original", use_container_width=True)
        with col_b:
            st.image(cropped, caption="Cropped (1:1)", use_container_width=True)

        st.divider()

        if st.button("⬆️ Upload & Save to Database", type="primary", use_container_width=True):
            with st.spinner("Uploading to Cloudinary..."):
                cloudinary_url = upload_to_cloudinary(cropped, selected["id"])

            if cloudinary_url:
                with st.spinner("Saving to database..."):
                    conn = None
                    try:
                        conn = db_utils.get_connection()
                        db_utils.update_startup_image_url(conn, selected["id"], cloudinary_url)
                        conn.commit()
                        st.cache_data.clear()
                    except Exception as e:
                        if conn: conn.rollback()
                        st.error(f"Database update failed: {e}")
                        st.stop()
                    finally:
                        if conn: conn.close()

                st.success(f"✅ Image saved for **{selected['name']}**!")
                st.image(cloudinary_url, caption="Live on Cloudinary", width=220)
                st.code(cloudinary_url, language=None)
                st.rerun()
    else:
        st.info("👆 Select a company and upload an image to get started.")
