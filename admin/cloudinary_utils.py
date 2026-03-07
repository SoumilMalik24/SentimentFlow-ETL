"""
admin/cloudinary_utils.py
Cloudinary setup and the shared image upload + 1:1 crop widget.
"""
import io
import streamlit as st
import cloudinary
import cloudinary.uploader
from PIL import Image
from streamlit_cropper import st_cropper
from src.core.config import settings


def init_cloudinary() -> bool:
    """
    Configures the Cloudinary SDK from settings.
    Returns True if credentials are present, False otherwise.
    """
    ready = all([
        settings.CLOUDINARY_CLOUD_NAME,
        settings.CLOUDINARY_API_KEY,
        settings.CLOUDINARY_API_SECRET,
    ])
    if ready:
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True,
        )
    return ready


def upload_to_cloudinary(image: Image.Image, startup_id: str) -> str | None:
    """
    Saves a PIL image to a BytesIO buffer and uploads it to Cloudinary.
    Uses a stable public_id so re-uploads overwrite the old image.

    Returns the secure_url string or None on failure.
    """
    try:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        result = cloudinary.uploader.upload(
            buf.read(),
            public_id=f"sentimentflow/startups/{startup_id}",
            overwrite=True,
            resource_type="image",
        )
        return result["secure_url"]
    except Exception as e:
        st.error(f"Cloudinary upload failed: {e}")
        return None


def image_crop_and_upload_widget(
    startup_id: str,
    widget_key_prefix: str,
    cloudinary_ready: bool,
) -> str | None:
    """
    Renders:
      file uploader → 1:1 crop tool → Cloudinary upload button

    Returns the Cloudinary secure_url on successful upload, else None.

    Args:
        startup_id:          Used as the Cloudinary public_id.
        widget_key_prefix:   Unique prefix to avoid Streamlit key conflicts between tabs.
        cloudinary_ready:    Whether Cloudinary is configured (from init_cloudinary()).
    """
    if not cloudinary_ready:
        st.warning("Cloudinary not configured — image upload is unavailable.")
        return None

    uploaded = st.file_uploader(
        "Upload image (jpg, png, webp)",
        type=["jpg", "jpeg", "png", "webp"],
        key=f"{widget_key_prefix}_uploader",
    )
    if not uploaded:
        return None

    pil_image = Image.open(uploaded).convert("RGB")
    st.markdown("**Crop to 1:1 square** — drag the box corners, then click Upload.")
    cropped = st_cropper(
        pil_image,
        realtime_update=True,
        box_color="#6C63FF",
        aspect_ratio=(1, 1),
        key=f"{widget_key_prefix}_cropper",
    )
    st.image(cropped, caption="Cropped preview", width=180)

    if st.button("⬆️ Upload Cropped Image to Cloudinary", key=f"{widget_key_prefix}_upload_btn"):
        with st.spinner("Uploading..."):
            url = upload_to_cloudinary(cropped, startup_id)
            if url:
                st.success("✅ Uploaded!")
                st.code(url, language=None)
                return url
    return None
