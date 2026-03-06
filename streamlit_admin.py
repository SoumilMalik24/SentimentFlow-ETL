import streamlit as st
import sys
import os
import json
import io
import cloudinary
import cloudinary.uploader
from PIL import Image
from streamlit_cropper import st_cropper

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    from src.core.logger import logging
    from src.core.config import settings
    from src.utils import db_utils
    from src.utils import text_utils
except ImportError as e:
    st.error(f"Failed to import project modules: {e}")
    st.error("Please make sure you are running streamlit from the project's root directory.")
    st.stop()

# =========================================================
# Page Config
# =========================================================
st.set_page_config(
    page_title="SentimentFlow — Admin",
    page_icon="🛠️",
    layout="wide"
)

# =========================================================
# Cloudinary Setup
# =========================================================
_cloudinary_ready = all([
    settings.CLOUDINARY_CLOUD_NAME,
    settings.CLOUDINARY_API_KEY,
    settings.CLOUDINARY_API_SECRET
])
if _cloudinary_ready:
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True
    )

# =========================================================
# Cached DB Loaders
# =========================================================
@st.cache_data(ttl=600)
def get_sectors():
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
    conn = None
    try:
        conn = db_utils.get_connection()
        return db_utils.fetch_all_startups(conn)
    except Exception as e:
        st.error(f"Failed to fetch startups: {e}")
        return []
    finally:
        if conn: conn.close()

# =========================================================
# Shared Helper: Crop UI + Cloudinary Upload
# Returns the uploaded Cloudinary URL or None
# =========================================================
def image_upload_and_crop_widget(startup_id: str, widget_key_prefix: str) -> str | None:
    """
    Renders a file uploader → 1:1 crop tool → Cloudinary upload button.
    Returns the Cloudinary secure_url on successful upload, else None.
    """
    if not _cloudinary_ready:
        st.warning("Cloudinary not configured — image upload is unavailable.")
        return None

    uploaded = st.file_uploader(
        "Upload image (jpg, png, webp)",
        type=["jpg", "jpeg", "png", "webp"],
        key=f"{widget_key_prefix}_uploader"
    )
    if not uploaded:
        return None

    # 1:1 crop tool
    pil_image = Image.open(uploaded).convert("RGB")
    st.markdown("**Crop to 1:1 square** — drag the box corners then click Upload.")
    cropped_img = st_cropper(
        pil_image,
        realtime_update=True,
        box_color="#6C63FF",
        aspect_ratio=(1, 1),
        key=f"{widget_key_prefix}_cropper"
    )
    st.image(cropped_img, caption="Cropped preview", width=180)

    if st.button("⬆️ Upload Cropped Image to Cloudinary", key=f"{widget_key_prefix}_upload_btn"):
        with st.spinner("Uploading..."):
            try:
                buf = io.BytesIO()
                cropped_img.save(buf, format="PNG")
                buf.seek(0)
                public_id = f"sentimentflow/startups/{startup_id}"
                result = cloudinary.uploader.upload(
                    buf.read(),
                    public_id=public_id,
                    overwrite=True,
                    resource_type="image"
                )
                url = result["secure_url"]
                st.success("✅ Uploaded successfully!")
                st.code(url, language=None)
                return url
            except Exception as e:
                st.error(f"Cloudinary upload failed: {e}")
                return None
    return None

# =========================================================
# Misc Helper
# =========================================================
def process_startup_from_json(startup, sector_name_to_id, conn):
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
        "findingKeywords": startup.get("keywords", [])
    })
    return True

# =========================================================
# Page Header
# =========================================================
st.title("🛠️ SentimentFlow Admin Dashboard")
st.caption("Manage startups, bulk upload data, and update company images.")
st.divider()

sectors = get_sectors()
if not sectors:
    st.error("No sectors found. Please run `scripts/seed_sector.py` first.")
    st.stop()

sector_names = [s['name'] for s in sectors]
sector_name_to_id = {s['name']: s['id'] for s in sectors}

# =========================================================
# Tabs
# =========================================================
tab1, tab2, tab3 = st.tabs(["➕ Add / Edit Startup", "📂 Bulk Upload JSON", "🖼️ Upload Company Image"])


# =========================================================================
# TAB 1 — Add / Edit Single Startup (with optional image upload)
# =========================================================================
with tab1:
    st.header("Add or Edit a Single Startup")
    st.markdown(
        "`Name` + `Sector` generate a unique ID — same pair will **overwrite** an existing entry."
    )

    # --- Text inputs (outside form for dynamic image handling) ---
    col_left, col_right = st.columns(2)
    with col_left:
        t1_name        = st.text_input("Startup Name *", key="t1_name")
        t1_sector      = st.selectbox("Sector *", options=sector_names, key="t1_sector")
        t1_keywords    = st.text_input("Finding Keywords (comma-separated)", key="t1_keywords")
    with col_right:
        t1_description = st.text_area("Description *", height=130, key="t1_desc")
        t1_manual_url  = st.text_input("Image URL (paste directly, or upload below)", key="t1_url")

    st.divider()

    # --- Image upload + crop (optional) ---
    with st.expander("📷 Upload & Crop Image for this Startup (optional)", expanded=False):
        if t1_name and t1_sector:
            _t1_sector_id = sector_name_to_id.get(t1_sector)
            _t1_startup_id = text_utils.generate_startup_id(t1_name, str(_t1_sector_id))
            _t1_cloudinary_url = image_upload_and_crop_widget(_t1_startup_id, "tab1")
            if _t1_cloudinary_url:
                # Store in session so the save below picks it up
                st.session_state["t1_auto_image_url"] = _t1_cloudinary_url
                st.info("Image uploaded! Click **Save Startup** below to commit.")
        else:
            st.info("Enter the Startup Name and Sector above first to enable image upload.")

    final_image_url = st.session_state.get("t1_auto_image_url", "") or t1_manual_url

    st.divider()
    if st.button("💾 Save Startup", type="primary", key="t1_save"):
        if not t1_name or not t1_sector or not t1_description:
            st.error("Please fill in all required fields: Name, Sector, and Description.")
        else:
            with st.spinner("Saving..."):
                conn = None
                try:
                    conn = db_utils.get_connection()
                    sector_id = sector_name_to_id.get(t1_sector)
                    keywords_list = [k.strip() for k in t1_keywords.split(',') if k.strip()]
                    startup_id = text_utils.generate_startup_id(t1_name, str(sector_id))
                    db_utils.upsert_startup(conn, {
                        "id": startup_id,
                        "name": t1_name,
                        "sectorId": sector_id,
                        "description": t1_description,
                        "imageUrl": final_image_url,
                        "findingKeywords": keywords_list
                    })
                    conn.commit()
                    # Clear auto-image session after save
                    st.session_state.pop("t1_auto_image_url", None)
                    st.success(f"✅ Saved: **{t1_name}**")
                    st.caption(f"ID: `{startup_id}`")
                    st.balloons()
                    st.cache_data.clear()
                except Exception as e:
                    if conn: conn.rollback()
                    st.error(f"An error occurred: {e}")
                finally:
                    if conn: conn.close()


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

    if uploaded_json is not None:
        if st.button("🚀 Process JSON File", type="primary"):
            conn = None
            try:
                try:
                    startups_list = json.load(uploaded_json)
                    if not isinstance(startups_list, list):
                        st.error("Invalid JSON: file must contain a JSON array.")
                        st.stop()
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON file: {e}")
                    st.stop()

                with st.spinner(f"Processing {len(startups_list)} startups..."):
                    conn = db_utils.get_connection()
                    success = 0
                    bar = st.progress(0.0, "Starting...")
                    for i, s in enumerate(startups_list):
                        if process_startup_from_json(s, sector_name_to_id, conn):
                            success += 1
                        bar.progress((i + 1) / len(startups_list), f"Processing '{s.get('name','...')}'")
                    conn.commit()
                    st.success(f"✅ Upserted **{success}** of **{len(startups_list)}** startups.")
                    st.cache_data.clear()
            except Exception as e:
                if conn: conn.rollback()
                st.error(f"An error occurred: {e}")
            finally:
                if conn: conn.close()


# =========================================================================
# TAB 3 — Upload Company Image (Only Missing Images, with 1:1 Crop)
# =========================================================================
with tab3:
    st.header("Upload Company Image")
    st.markdown(
        "Shows only companies **without an image** set. "
        "Upload a logo, crop it to a square, and save it."
    )

    if not _cloudinary_ready:
        st.error(
            "Cloudinary is not configured. "
            "Set `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` in `.env`."
        )
        st.stop()

    all_startups = get_all_startups()

    # Filter: only startups WITHOUT an imageUrl
    startups_without_image = [
        s for s in all_startups
        if not s.get("imageUrl") or s["imageUrl"].strip() == ""
    ]

    if not startups_without_image:
        st.success("🎉 All startups already have an image set!")
        st.stop()

    st.info(f"**{len(startups_without_image)}** startup(s) still need an image.")

    startup_options = {
        f"{s['sectorName'] or 'Unknown'}  —  {s['name']}": s
        for s in startups_without_image
    }

    selected_label = st.selectbox(
        "Select Company (no image set)",
        options=list(startup_options.keys()),
        help="Only companies without an image are shown."
    )
    selected = startup_options[selected_label]

    st.divider()

    # Upload + crop
    uploaded_img = st.file_uploader(
        "Upload image (jpg, png, webp)",
        type=["jpg", "jpeg", "png", "webp"],
        key="t3_uploader"
    )

    if uploaded_img:
        pil_img = Image.open(uploaded_img).convert("RGB")
        st.markdown("**Crop to 1:1 square** — drag the handles to frame the logo.")
        cropped = st_cropper(
            pil_img,
            realtime_update=True,
            box_color="#6C63FF",
            aspect_ratio=(1, 1),
            key="t3_cropper"
        )

        col_a, col_b = st.columns(2)
        with col_a:
            st.image(pil_img, caption="Original", use_container_width=True)
        with col_b:
            st.image(cropped, caption="Cropped (1:1)", use_container_width=True)

        st.divider()

        if st.button("⬆️ Upload & Save to Database", type="primary", use_container_width=True):

            # Upload cropped image to Cloudinary
            with st.spinner("Uploading to Cloudinary..."):
                try:
                    buf = io.BytesIO()
                    cropped.save(buf, format="PNG")
                    buf.seek(0)
                    public_id = f"sentimentflow/startups/{selected['id']}"
                    result = cloudinary.uploader.upload(
                        buf.read(),
                        public_id=public_id,
                        overwrite=True,
                        resource_type="image"
                    )
                    cloudinary_url = result["secure_url"]
                except Exception as e:
                    st.error(f"❌ Cloudinary upload failed: {e}")
                    st.stop()

            # Save URL to DB
            with st.spinner("Saving to database..."):
                conn = None
                try:
                    conn = db_utils.get_connection()
                    db_utils.update_startup_image_url(conn, selected["id"], cloudinary_url)
                    conn.commit()
                    st.cache_data.clear()
                except Exception as e:
                    if conn: conn.rollback()
                    st.error(f"❌ Database update failed: {e}")
                    st.stop()
                finally:
                    if conn: conn.close()

            st.success(f"✅ Image saved for **{selected['name']}**!")
            st.image(cloudinary_url, caption="Live on Cloudinary", width=220)
            st.code(cloudinary_url, language=None)
            st.rerun()
    else:
        st.info("👆 Select a company above and upload an image to get started.")
