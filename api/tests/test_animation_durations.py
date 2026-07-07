"""Tests for animation duration extraction and total_duration_ms.

Covers the message/0008-0010 exchange:
- the WebP regression: Pillow only populates info["duration"] on load(), so
  the extractor must load() after seek() or animated WebP durations read None
- min/max_frame_duration_ms semantics (raw positive stored delays, unchanged)
- total_duration_ms clamp policy: per frame missing-or-<=10ms counts as
  100 ms; a whole-loop total <= 30 ms is stored as 30 ms; None for static
"""

from __future__ import annotations

import io

from PIL import Image

from app.amp.metadata_extraction import (
    collect_frame_durations,
    compute_total_duration_ms,
    extract_metadata,
    _min_max_durations,
)

# --- helpers -----------------------------------------------------------------


def _frames(colors):
    return [Image.new("RGBA", (8, 8), c) for c in colors]


def make_animated_bytes(fmt: str, durations: list[int]) -> bytes:
    """Animated GIF/WebP with one 8x8 frame per duration (distinct colors)."""
    colors = [(10 * (i + 1) % 256, 40, 90, 255) for i in range(len(durations))]
    frames = _frames(colors)
    if fmt == "gif":
        frames = [f.convert("P", palette=Image.Palette.ADAPTIVE) for f in frames]
    buf = io.BytesIO()
    save_kwargs = dict(
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
    )
    if fmt == "webp":
        save_kwargs["lossless"] = True
    frames[0].save(buf, format=fmt.upper(), **save_kwargs)
    return buf.getvalue()


def _open(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


# --- collect_frame_durations ---------------------------------------------------


def test_collect_durations_gif():
    img = _open(make_animated_bytes("gif", [50, 100, 200]))
    assert collect_frame_durations(img, img.n_frames) == [50, 100, 200]


def test_collect_durations_webp_populated_only_on_load():
    """The regression: WebP frame delays must survive extraction (needs load())."""
    img = _open(make_animated_bytes("webp", [50, 100, 200]))
    assert collect_frame_durations(img, img.n_frames) == [50, 100, 200]


def test_collect_durations_static_empty():
    img = Image.new("RGBA", (8, 8), (1, 2, 3, 255))
    assert collect_frame_durations(img, 1) == []


# --- min/max semantics (unchanged: raw, positive entries only) ----------------


def test_min_max_positive_only():
    assert _min_max_durations([0, 50, 200, None]) == (50, 200)


def test_min_max_none_when_no_positive():
    assert _min_max_durations([0, None, 0]) == (None, None)


# --- total_duration_ms clamp policy --------------------------------------------


def test_total_plain_sum():
    assert compute_total_duration_ms([50, 100, 200], 3) == 350


def test_total_clamps_near_zero_frames_to_100():
    # 5 ms and 10 ms are at/below the 10 ms threshold -> 100 ms each
    assert compute_total_duration_ms([5, 10, 50], 3) == 250


def test_total_missing_frame_counts_as_100():
    assert compute_total_duration_ms([None, 50], 2) == 150


def test_total_floor_30ms():
    # 11 ms frames are kept raw; 22 ms total is at/below the floor -> 30
    assert compute_total_duration_ms([11, 11], 2) == 30


def test_total_static_is_none():
    assert compute_total_duration_ms([], 1) is None


def test_total_all_unreadable_defaults_per_frame():
    assert compute_total_duration_ms([None, None, None], 3) == 300


# --- extract_metadata end-to-end -----------------------------------------------


def test_extract_metadata_animated_webp(tmp_path):
    data = make_animated_bytes("webp", [50, 100, 200])
    p = tmp_path / "anim.webp"
    p.write_bytes(data)
    with Image.open(p) as img:
        meta = extract_metadata(p, img)
    assert meta.frame_count == 3
    assert meta.shortest_duration_ms == 50
    assert meta.longest_duration_ms == 200
    assert meta.total_duration_ms == 350


def test_extract_metadata_animated_gif(tmp_path):
    data = make_animated_bytes("gif", [40, 40, 120])
    p = tmp_path / "anim.gif"
    p.write_bytes(data)
    with Image.open(p) as img:
        meta = extract_metadata(p, img)
    assert meta.frame_count == 3
    assert meta.shortest_duration_ms == 40
    assert meta.longest_duration_ms == 120
    assert meta.total_duration_ms == 200


def test_extract_metadata_static_png(tmp_path):
    img = Image.new("RGBA", (8, 8), (1, 2, 3, 255))
    p = tmp_path / "static.png"
    img.save(p, format="PNG")
    with Image.open(p) as img2:
        meta = extract_metadata(p, img2)
    assert meta.frame_count == 1
    assert meta.shortest_duration_ms is None
    assert meta.longest_duration_ms is None
    assert meta.total_duration_ms is None
