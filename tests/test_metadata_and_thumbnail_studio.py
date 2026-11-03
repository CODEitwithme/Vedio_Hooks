"""
Comprehensive Test Suite for AI Metadata & SEO Generator,
AI Thumbnail & Cover Studio, and Publishing Readiness Engine in VedioHooks AI.
"""

import os
import sys
import json
import zipfile
from pathlib import Path
import pytest
from PIL import Image
import numpy as np

# Ensure workspace root in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.metadata_generator import (
    generate_video_metadata,
    generate_youtube_metadata,
    generate_instagram_metadata,
    generate_tiktok_metadata,
    build_title_variations,
    evaluate_metadata_quality,
    extract_keywords_from_text,
    PLATFORM_LIMITS
)
from src.thumbnail_studio import (
    generate_thumbnail_suite,
    extract_candidate_frames,
    analyze_frame_quality,
    composite_thumbnail,
    generate_grid_crop_preview,
    generate_thumbnail_headline,
    CANVAS_DIMENSIONS,
    FrameCandidate
)
from src.publishing_validator import (
    validate_publishing_readiness,
    export_publishing_bundle
)
from src.db import (
    init_db,
    save_video_metadata,
    get_video_metadata,
    list_video_metadata,
    update_video_metadata_field,
    delete_video_metadata,
    save_thumbnail_asset,
    get_thumbnail_asset,
    list_thumbnail_assets,
    select_thumbnail_asset,
    delete_thumbnail_asset,
    get_database_stats
)


SAMPLE_TRANSCRIPT = (
    "The number one reason most people never become successful in their career or business "
    "is because they give up right before the breakthrough. When you encounter friction or resistance, "
    "that is not a signal to quit; it is a signal that your skills are being tested and refined. "
    "Every single mentor I worked with had the exact same habit: progressive discipline and ruthless focus. "
    "So ask yourself: are you willing to endure the pain of discipline today, or will you suffer the pain of regret forever?"
)


def test_keyword_extraction_and_title_variations():
    """Verifies that keywords are accurately extracted and 4 distinct title variations are generated."""
    keywords = extract_keywords_from_text(SAMPLE_TRANSCRIPT, top_n=6)
    assert len(keywords) >= 3
    assert any(k in ["discipline", "successful", "breakthrough", "habits", "mentor"] for k in keywords)

    title_vars = build_title_variations(
        base_title="Why Most People Never Become Successful",
        niche="Motivation",
        keywords=keywords
    )

    # 4 distinct variations
    assert title_vars.curiosity_driven
    assert title_vars.seo_focused
    assert title_vars.emotional
    assert title_vars.bold_attention

    # Check constraint: all titles <= 100 characters
    assert len(title_vars.curiosity_driven) <= 100
    assert len(title_vars.seo_focused) <= 100
    assert len(title_vars.emotional) <= 100
    assert len(title_vars.bold_attention) <= 100

    # Test series suffix inclusion
    series_vars = build_title_variations(
        base_title="The Rise of an Entrepreneur",
        niche="Motivation",
        keywords=keywords,
        series_info={"episode_number": 2, "is_final_episode": False}
    )
    assert "Part 2" in series_vars.curiosity_driven or "Part 2" in series_vars.seo_focused


def test_youtube_metadata_generation():
    """Verifies YouTube and YouTube Shorts metadata generation adheres to character limits."""
    yt_shorts = generate_youtube_metadata(
        title="Why 99% of People Quit",
        text=SAMPLE_TRANSCRIPT,
        niche="Motivation",
        is_short=True
    )

    assert len(yt_shorts.title) <= PLATFORM_LIMITS["youtube"]["title_max"]
    assert len(yt_shorts.description) <= PLATFORM_LIMITS["youtube"]["description_max"]
    assert "#Shorts" in yt_shorts.hashtags
    assert len(yt_shorts.primary_keywords) >= 2
    assert len(yt_shorts.tags) >= 3
    assert yt_shorts.category == "People & Blogs"

    # Verify tags character limit (< 500 chars total)
    total_tags_chars = len(",".join(yt_shorts.tags))
    assert total_tags_chars <= PLATFORM_LIMITS["youtube"]["tags_max_chars"]

    # Verify long-form description has chapters
    mock_words = [
        {"word": "The", "start": 0.0, "end": 0.5},
        {"word": "number", "start": 0.5, "end": 1.0},
        {"word": "habit", "start": 30.0, "end": 30.5},
        {"word": "discipline", "start": 60.0, "end": 60.5}
    ]
    yt_long = generate_youtube_metadata(
        title="Complete Guide to Discipline",
        text=SAMPLE_TRANSCRIPT,
        niche="Motivation",
        is_short=False,
        duration=90.0,
        words=mock_words * 4
    )
    assert len(yt_long.chapters) >= 2
    assert "TIMESTAMPS" in yt_long.description


def test_instagram_and_tiktok_metadata_generation():
    """Verifies Instagram Reels and TikTok metadata generation conforms to mobile layout constraints."""
    ig = generate_instagram_metadata(
        title="The Habit of Ruthless Focus",
        text=SAMPLE_TRANSCRIPT,
        niche="Motivation",
        handle="@apexmotivation"
    )

    assert len(ig.first_line_hook) <= 85
    assert len(ig.caption) <= PLATFORM_LIMITS["instagram"]["caption_max"]
    assert 1 <= len(ig.hashtags) <= PLATFORM_LIMITS["instagram"]["hashtags_max"]
    assert "@apexmotivation" in ig.caption
    assert "\n\n" in ig.caption  # Clean line breaks for mobile readability

    tt = generate_tiktok_metadata(
        title="Stop Giving Up Right Before The Breakthrough",
        text=SAMPLE_TRANSCRIPT,
        niche="Motivation"
    )
    assert len(tt.caption) <= PLATFORM_LIMITS["tiktok"]["caption_max"]
    assert any(h in tt.hashtags for h in ["#fyp", "#foryou", "#trending"])


def test_series_aware_metadata_continuity():
    """Verifies consistent series naming, episode badges, and next-episode teasers."""
    series_info = {
        "series_id": "series_test_101",
        "series_title": "The Road to Greatness",
        "episode_number": 1,
        "total_episodes": 3,
        "is_final_episode": False,
        "next_teaser": "the critical failure that changed everything"
    }

    full_meta = generate_video_metadata(
        target_type="episode",
        target_id=1,
        title="How He Started With Nothing",
        text=SAMPLE_TRANSCRIPT,
        niche="Motivation",
        series_info=series_info
    )

    # YouTube should contain part indicator
    assert "Part 1" in full_meta.youtube.title or "Part 1" in full_meta.title_variations.curiosity_driven
    # Instagram should contain next-episode follow teaser
    assert "Part 2 drops" in full_meta.instagram.caption or "our series" in full_meta.instagram.caption

    # Final episode verification
    final_series_info = {
        "series_id": "series_test_101",
        "series_title": "The Road to Greatness",
        "episode_number": 3,
        "total_episodes": 3,
        "is_final_episode": True
    }
    final_meta = generate_video_metadata(
        target_type="episode",
        target_id=3,
        title="The Final Breakthrough",
        text=SAMPLE_TRANSCRIPT,
        niche="Motivation",
        series_info=final_series_info
    )
    assert "FINAL" in final_meta.instagram.caption or "Final" in final_meta.youtube.title


def test_metadata_quality_scoring():
    """Verifies that Metadata Quality Scorer computes 7 dimensions and a composite score."""
    full_meta = generate_video_metadata(
        target_type="short",
        target_id=10,
        title="Why 99% Give Up",
        text=SAMPLE_TRANSCRIPT,
        niche="Motivation"
    )

    q = full_meta.quality
    assert 50 <= q.overall_score <= 100
    assert 50 <= q.content_relevance <= 100
    assert 50 <= q.keyword_relevance <= 100
    assert 50 <= q.readability <= 100
    assert 50 <= q.hook_strength <= 100
    assert 50 <= q.platform_suitability <= 100
    assert 50 <= q.accuracy <= 100
    assert 50 <= q.audience_relevance <= 100


def test_thumbnail_frame_analysis_and_safe_zone(tmp_path):
    """Verifies that frame quality analyzer computes sharpness and face detection."""
    # Create synthetic test frame image
    test_frame_path = str(tmp_path / "test_frame.jpg")
    img = Image.new("RGB", (1280, 720), (30, 45, 60))
    img.save(test_frame_path)

    cand = analyze_frame_quality(test_frame_path, timestamp_sec=2.5)
    assert cand.timestamp_sec == 2.5
    assert cand.quality_score >= 50
    assert isinstance(cand.sharpness_score, float)

    # Test Safe Zone Headline Placement in PIL Composite
    out_thumb = str(tmp_path / "rendered_thumb_9x16.jpg")
    composite_thumbnail(
        frame_path=test_frame_path,
        output_path=out_thumb,
        headline="STOP QUITTING NOW",
        aspect_ratio="9:16",
        style_mode="auto",
        niche="Motivation",
        face_candidate=cand,
        brand_handle="@apexdiscipline"
    )

    assert os.path.exists(out_thumb)
    rendered_img = Image.open(out_thumb)
    assert rendered_img.size == CANVAS_DIMENSIONS["9:16"]


def test_thumbnail_variations_and_grid_crop_preview(tmp_path):
    """Verifies 3 psychological variations (Emotional, Curiosity, Professional) and 1:1 Instagram grid crop."""
    test_frame_path = str(tmp_path / "source_frame.jpg")
    img = Image.new("RGB", (1080, 1920), (15, 20, 25))
    img.save(test_frame_path)

    # Test headlines for all 3 variations
    emo_head = generate_thumbnail_headline("Why Discipline Beats Motivation", "Motivation", "emotional")
    cur_head = generate_thumbnail_headline("Why Discipline Beats Motivation", "Motivation", "curiosity")
    pro_head = generate_thumbnail_headline("Why Discipline Beats Motivation", "Motivation", "professional")

    assert emo_head
    assert cur_head
    assert pro_head
    assert 1 <= len(emo_head.split()) <= 6

    # Test 1:1 Instagram Profile Grid Preview
    grid_preview_path = str(tmp_path / "grid_preview.jpg")
    generate_grid_crop_preview(test_frame_path, grid_preview_path)
    assert os.path.exists(grid_preview_path)
    grid_img = Image.open(grid_preview_path)
    assert grid_img.size == (1080, 1080)


def test_publishing_readiness_validation_and_bundle(tmp_path):
    """Verifies pre-flight validation across 8 criteria and publishing package ZIP export."""
    # Create mock video and thumbnail
    dummy_video = str(tmp_path / "clip_render.mp4")
    with open(dummy_video, "wb") as f:
        f.write(b"MOCK_MP4_DATA_" * 200)

    dummy_thumb = str(tmp_path / "cover_thumb.jpg")
    img = Image.new("RGB", (1080, 1920), (10, 10, 20))
    img.save(dummy_thumb)

    mock_metadata = {
        "title": "Why 99% Never Succeed",
        "youtube": {
            "title": "Why 99% Never Succeed",
            "description": "Full breakdown of mental toughness and discipline habits.",
            "tags": ["motivation", "discipline", "mindset"]
        },
        "instagram": {
            "first_line_hook": "🔥 WHY 99% NEVER SUCCEED",
            "caption": "Why 99% never succeed.\n\nDrop your perspective below!",
            "hashtags": ["#motivation", "#mindset", "#shorts", "#reels"]
        },
        "tiktok": {
            "caption": "Wait till the end! 😳 #fyp #discipline",
            "search_keywords": ["discipline", "success"]
        }
    }

    report = validate_publishing_readiness(
        target_type="short",
        target_id=1,
        video_path=dummy_video,
        metadata=mock_metadata,
        thumbnail_path=dummy_thumb,
        platform="instagram"
    )

    assert report.has_video is True
    assert report.has_metadata is True
    assert report.has_thumbnail is True
    assert report.overall_score >= 80
    assert report.readiness_status in ("ready", "needs_review")
    assert len(report.checks) == 8

    # Test ZIP export package
    export_dir = str(tmp_path / "exports")
    zip_pkg = export_publishing_bundle(
        target_type="short",
        target_id=1,
        video_path=dummy_video,
        metadata=mock_metadata,
        thumbnail_path=dummy_thumb,
        output_dir=export_dir
    )

    assert os.path.exists(zip_pkg)
    with zipfile.ZipFile(zip_pkg, "r") as zf:
        namelist = zf.namelist()
        assert any(n.startswith("video_") for n in namelist)
        assert any(n.startswith("cover_") for n in namelist)
        assert "metadata_manifest.json" in namelist
        assert "Instagram_Publishing.txt" in namelist
        assert "YouTube_Publishing.txt" in namelist


def test_database_metadata_and_thumbnail_crud():
    """Verifies SQLite persistence, updates, selection, and deletion for metadata and thumbnails."""
    init_db()

    # 1. Save & retrieve metadata
    meta_id = save_video_metadata(
        target_type="short",
        target_id="test_short_99",
        title="Test Viral Hook",
        niche="Cricket",
        youtube_data={"title": "Kohli Masterclass", "tags": ["cricket", "ipl"]},
        instagram_data={"caption": "🏏 What a knock! Follow for more.", "hashtags": ["#cricket"]},
        tiktok_data={"caption": "Cricket magic #fyp"},
        title_variations={"curiosity_driven": "The Secret Over Nobody Saw"},
        quality_score=94
    )
    assert meta_id > 0

    fetched = get_video_metadata("short", "test_short_99")
    assert fetched is not None
    assert fetched["title"] == "Test Viral Hook"
    assert fetched["niche"] == "Cricket"
    assert fetched["youtube"]["title"] == "Kohli Masterclass"

    # 2. Update specific field
    ok = update_video_metadata_field("short", "test_short_99", "youtube", "title", "Updated Masterclass Title")
    assert ok is True
    updated = get_video_metadata("short", "test_short_99")
    assert updated["youtube"]["title"] == "Updated Masterclass Title"

    # 3. Save, list & select thumbnail assets
    asset_id_1 = save_thumbnail_asset(
        target_type="short",
        target_id="test_short_99",
        image_path="output/thumbnails/test_thumb_1.jpg",
        headline="UNBELIEVABLE FINISH!",
        variation_type="emotional",
        aspect_ratio="9:16",
        is_selected=0
    )
    asset_id_2 = save_thumbnail_asset(
        target_type="short",
        target_id="test_short_99",
        image_path="output/thumbnails/test_thumb_2.jpg",
        headline="THE TURNING POINT",
        variation_type="curiosity",
        aspect_ratio="9:16",
        is_selected=0
    )
    assert asset_id_1 > 0
    assert asset_id_2 > 0

    thumbs = list_thumbnail_assets(target_type="short", target_id="test_short_99")
    assert len(thumbs) >= 2

    # Select asset 2 as active
    select_ok = select_thumbnail_asset(asset_id_2, "short", "test_short_99")
    assert select_ok is True
    active_thumb = get_thumbnail_asset(asset_id_2)
    assert active_thumb["is_selected"] == 1
    other_thumb = get_thumbnail_asset(asset_id_1)
    assert other_thumb["is_selected"] == 0

    # 4. Check telemetry in stats
    stats = get_database_stats()
    assert "total_metadata_records" in stats
    assert "total_thumbnail_assets" in stats
    assert stats["total_metadata_records"] >= 1
    assert stats["total_thumbnail_assets"] >= 2

    # 5. Clean up
    delete_thumbnail_asset(asset_id_1)
    delete_thumbnail_asset(asset_id_2)
    delete_video_metadata("short", "test_short_99")
    assert get_video_metadata("short", "test_short_99") is None


def test_api_metadata_and_thumbnail_endpoints():
    """Verifies FastAPI REST endpoints for Metadata Studio, Thumbnail Studio, and Publishing."""
    from fastapi.testclient import TestClient
    from src.server import app

    client = TestClient(app)

    # 1. Generate Metadata
    res_meta = client.post("/api/metadata/generate", json={
        "target_type": "short",
        "target_id": "test_api_short",
        "niche": "Motivation",
        "custom_title": "The Power of Ruthless Focus"
    })
    assert res_meta.status_code == 200
    meta_json = res_meta.json()
    assert meta_json["success"] is True
    assert "metadata" in meta_json

    # 2. Get Metadata
    res_get = client.get("/api/metadata/short/test_api_short")
    assert res_get.status_code == 200
    assert res_get.json()["metadata"]["niche"] == "Motivation"

    # 3. Save Metadata
    res_save = client.post("/api/metadata/short/test_api_short/save", json={
        "target_type": "short",
        "target_id": "test_api_short",
        "title": "Edited Title",
        "niche": "Motivation",
        "youtube": {"title": "Edited Title", "description": "Custom Description", "tags": ["mindset"]},
        "instagram": {"caption": "Custom IG Caption #mindset", "hashtags": ["#mindset"]},
        "tiktok": {"caption": "Custom TikTok Caption #fyp"}
    })
    assert res_save.status_code == 200
    assert res_save.json()["success"] is True

    # 4. Check Readiness
    res_ready = client.get("/api/publishing/readiness/short/test_api_short")
    assert res_ready.status_code == 200
    report = res_ready.json()["report"]
    assert "overall_score" in report
    assert "checks" in report

    # 5. Verify Dashboard HTML contains Metadata Studio & Thumbnail Studio
    res_dash = client.get("/")
    assert res_dash.status_code == 200
    html = res_dash.text
    assert "AI Metadata & SEO Studio" in html
    assert "AI Thumbnail & Cover Studio" in html
    assert 'id="tab-metadata-studio"' in html
    assert 'id="tab-thumbnail-studio"' in html
    assert 'id="readinessModal"' in html

