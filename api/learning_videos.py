import json
import logging
import boto3
import os
import re

from fastapi import APIRouter, HTTPException, Depends
from config.auth import verify_token

logger = logging.getLogger("fastapi_app")

router = APIRouter()

BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
FOLDER      = "learning-videos"

SUPPORTED_LANGUAGES = [
    "english",
    "kannada",
    "telugu",
    "tamil",
    "malayalam",
    "Hindi"
]

SUPPORTED_CROPS = [
    "rice", "chilli", "cashew", "tulsi"
    # add more as the workflow generates them
]

# Regex patterns to detect gaming/non-real farming content.
# Only specific gaming keywords are used to prevent false positives with real crop terms.
GAMING_KEYWORDS = [
    # Gaming
    r"\bminecraft\b",
    r"\broblox\b",
    r"\bstardew\b",
    r"\bfarming\s+simulator\b",
    r"\bfs[0-9]{2}\b",
    r"\bhay\s*day\b",
    r"\banimal\s+crossing\b",
    r"\bskyblock\b",
    r"\bredstone\b",
    r"\bmob\s+farm\b",
    r"\bxp\s+farm\b",
    r"\biron\s+farm\b",
    r"\bgold\s+farm\b",
    r"\bafk\s+farm\b",
    r"\bbedrock\s+edition\b",
    r"\bjava\s+edition\b",
    r"\bmcpe\b",
    r"\blets\s*play\b",
    r"\bgameplay\b",
    r"\bgaming\b",
    r"\bspeedrun\b",
    r"\bmodded\b",
    r"\bpc\s+gameplay\b",
    r"\bwalkthrough\s+part\b",

    # Dairy farming / milk business
    r"\bdairy\b",
    r"\bdairy\s+farm\b",
    r"\bdairy\s+farming\b",
    r"\bdairy\s+business\b",
    r"\bmilk\s+production\b",
    r"\bmilk\s+business\b",
    r"\bmilk\s+farm\b",
    r"\bmilk\s+farming\b",
    r"\bmilking\b",
    r"\bcow\s+farm\b",
    r"\bcow\s+farming\b",
    r"\bcattle\s+farm\b",
    r"\bcattle\s+farming\b",
    r"\bbuffalo\s+farm\b",
    r"\bbuffalo\s+farming\b",

    # Livestock
    r"\blivestock\b",
    r"\banimal\s+husbandry\b",
    r"\bgoat\s+farm\b",
    r"\bgoat\s+farming\b",
    r"\bsheep\s+farm\b",
    r"\bsheep\s+farming\b",
    r"\bpig\s+farm\b",
    r"\bpiggery\b",

    # Poultry
    r"\bpoultry\b",
    r"\bpoultry\s+farm\b",
    r"\bpoultry\s+farming\b",
    r"\bchicken\s+farm\b",
    r"\bbroiler\b",
    r"\blayer\s+farm\b",
    r"\begg\s+production\b",

    # Dairy products
    r"\bcheese\b",
    r"\bbutter\b",
    r"\bghee\b",
    r"\byogurt\b",
    r"\bcurd\b",
    r"\bice\s*cream\b"
]
GAMING_RE = re.compile("|".join(GAMING_KEYWORDS), re.IGNORECASE)


def get_s3_client():
    return boto3.client(
        "s3",
        region_name=os.getenv("AWS_REGION", "ap-south-1")
    )


def is_real_farming_video(video: dict) -> bool:
    """
    Checks if a video appears to be gaming or non-real farming content.
    Analyzes title, description, and channel name.

    Returns:
        True if the video appears to be real farming.
        False if it contains gaming keywords.
    """
    title = video.get("title", "")
    description = video.get("description", "")
    channel = (
        video.get("channel_name", "") or
        video.get("channelName", "") or
        video.get("channel", "")
    )

    # Combine relevant text for regex check
    content_to_check = f"{title} {description} {channel}"

    # If a gaming pattern matches, it's not a real farming video
    if GAMING_RE.search(content_to_check):
        return False

    return True


def fetch_videos_from_s3(crop_name: str, language: str) -> dict:
    """
    Fetches the pre-generated JSON file from S3.
    File naming: learning-videos/rice_kannada.json
    """
    file_name = f"{crop_name.lower()}_{language.lower()}.json"
    s3_key    = f"{FOLDER}/{file_name}"

    try:
        s3  = get_s3_client()
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        raw = obj["Body"].read().decode("utf-8")
        raw = raw.lstrip("=").strip()
        return json.loads(raw)

    except s3.exceptions.NoSuchKey:
        raise HTTPException(
            status_code=404,
            detail=f"No videos found for crop '{crop_name}' in '{language}'. "
                   f"Please try another language or crop."
        )
    except Exception as e:
        logger.error(f"[learning_videos] S3 fetch error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch videos. Please try again later."
        )


# ================================================================
#  GET /api/learning/videos
#  Client calls this with crop_name + language query params
#  Returns initial 4 videos
#  Protected by JWT — user must be logged in
# ================================================================

@router.get("/learning/videos")
def get_learning_videos(
    crop_name: str,
    language: str,
    user_id: str = Depends(verify_token)
):
    """
    Returns the first 4 videos (initial batch) for the given
    crop + language combination from S3, filtered of any gaming content.

    Query params:
        crop_name  — e.g. Rice
        language   — e.g. Kannada

    Response includes meta + initial videos list.
    """
    if language.lower() not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Language '{language}' not supported. "
                   f"Supported: {', '.join(SUPPORTED_LANGUAGES)}"
        )

    data = fetch_videos_from_s3(crop_name, language)

    initial_videos = data.get("initial", [])
    load_more_videos = data.get("load_more", [])

    # Pool all videos and filter gaming content
    all_videos = initial_videos + load_more_videos
    filtered_all = [v for v in all_videos if is_real_farming_video(v)]

    # Re-slice into new initial batch (first 4 videos) and new load_more batch
    new_initial = filtered_all[:4]
    new_load_more = filtered_all[4:]

    return {
        "status": "ok",
        "data": {
            "meta":         data.get("meta", {}),
            "videos":       new_initial,
            "has_more":     len(new_load_more) > 0,
            "total_initial": len(new_initial)
        }
    }


# ================================================================
#  GET /api/learning/videos/more
#  Client calls this when user taps "Load More"
#  Returns remaining videos (load_more batch)
# ================================================================

@router.get("/learning/videos/more")
def get_more_learning_videos(
    crop_name: str,
    language: str,
    user_id: str = Depends(verify_token)
):
    """
    Returns the load_more batch (videos 5 onwards) for the given
    crop + language combination, filtered of gaming content.

    Query params:
        crop_name  — e.g. Rice
        language   — e.g. Kannada
    """
    if language.lower() not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Language '{language}' not supported. "
                   f"Supported: {', '.join(SUPPORTED_LANGUAGES)}"
        )

    data = fetch_videos_from_s3(crop_name, language)

    initial_videos = data.get("initial", [])
    load_more_videos = data.get("load_more", [])

    # Pool all videos and filter gaming content to ensure consistency with first batch
    all_videos = initial_videos + load_more_videos
    filtered_all = [v for v in all_videos if is_real_farming_video(v)]

    # The load more batch contains everything after the first 4
    new_load_more = filtered_all[4:]

    if not new_load_more:
        return {
            "status": "ok",
            "data": {
                "videos":    [],
                "has_more":  False,
                "message":   "No more videos available."
            }
        }

    return {
        "status": "ok",
        "data": {
            "videos":   new_load_more,
            "has_more": False
        }
    }


# ================================================================
#  GET /api/learning/languages
#  Returns list of supported languages
#  Client uses this to build the language selector dropdown
# ================================================================

@router.get("/learning/languages")
def get_supported_languages(
    user_id: str = Depends(verify_token)
):
    return {
        "status": "ok",
        "data": {
            "languages": [
                {"code": "english",   "label": "English",   "native": "English"},
                {"code": "kannada",   "label": "Kannada",   "native": "ಕನ್ನಡ"},
                {"code": "telugu",    "label": "Telugu",    "native": "తెలుగు"},
                {"code": "tamil",     "label": "Tamil",     "native": "தமிழ்"},
                {"code": "malayalam", "label": "Malayalam", "native": "മലയാളം"},
                {"code": "konkani",   "label": "Konkani",   "native": "कोंकणी"},
            ]
        }
    }


# ================================================================
#  GET /api/learning/check
#  Check if videos exist for a crop+language before calling /videos
#  Client uses this to show a loader or "not available" message
# ================================================================

@router.get("/learning/check")
def check_videos_available(
    crop_name: str,
    language: str,
    user_id: str = Depends(verify_token)
):
    file_name = f"{crop_name.lower()}_{language.lower()}.json"
    s3_key    = f"{FOLDER}/{file_name}"

    try:
        s3 = get_s3_client()
        s3.head_object(Bucket=BUCKET_NAME, Key=s3_key)
        return {
            "status":    "ok",
            "available": True,
            "message":   f"Videos available for {crop_name} in {language}"
        }
    except Exception:
        return {
            "status":    "ok",
            "available": False,
            "message":   f"Videos not yet available for {crop_name} in {language}. "
                         f"Try English or another language."
        }
