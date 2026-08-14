"""Convert an animated GIF (or Telegram "GIF", which is really a silent MP4)
into a Telegram video sticker: WEBM container, VP9 codec, no audio.

Telegram's rules for a "video" sticker:
  - WEBM, VP9, no audio track.
  - At most 3 seconds long.
  - Exactly one side must be 512px, the other side must be <= 512px.
  - File size at most 256 KB.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg

STICKER_SIZE = 512
MAX_DURATION_SECONDS = 3.0
MAX_FILE_SIZE_BYTES = 256 * 1024
FFMPEG_TIMEOUT_SECONDS = 120

# Tried in order until the encoded file fits under MAX_FILE_SIZE_BYTES.
BITRATE_ATTEMPTS_KBPS = [500, 350, 250, 180, 130, 90, 60, 40]


def extract_first_frame(source_bytes: bytes) -> bytes:
    """Grab the first frame of a GIF/animation as a plain PNG.

    Used the other way around from ``convert_to_video_sticker``: if a pack
    was already started with static (image/text) stickers, a GIF sent to it
    can't join as a video sticker (Telegram allows only one format per
    pack), so it's added as a still image instead of being rejected.
    """
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = Path(tmpdir) / "source"
        src_path.write_bytes(source_bytes)
        out_path = Path(tmpdir) / "frame.png"

        cmd = [ffmpeg_exe, "-y", "-i", str(src_path), "-vframes", "1", str(out_path)]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=FFMPEG_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            raise RuntimeError("vaqt tugadi (ffmpeg juda uzoq ishladi)") from None

        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode(errors="ignore")[-500:])

        return out_path.read_bytes()


def convert_to_video_sticker(source_bytes: bytes) -> bytes:
    """Convert GIF/MP4 animation bytes into WEBM/VP9 sticker bytes that fit
    Telegram's video-sticker limits.

    Raises RuntimeError if ffmpeg fails, or if the file can't be shrunk
    under the size limit even at the lowest attempted bitrate.
    """
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = Path(tmpdir) / "source"
        src_path.write_bytes(source_bytes)
        out_path = Path(tmpdir) / "out.webm"

        scale_filter = (
            f"scale='if(gt(iw,ih),{STICKER_SIZE},-2)':'if(gt(iw,ih),-2,{STICKER_SIZE})',fps=30"
        )

        last_error = "noma'lum xatolik"
        for bitrate_kbps in BITRATE_ATTEMPTS_KBPS:
            cmd = [
                ffmpeg_exe, "-y",
                "-i", str(src_path),
                "-t", str(MAX_DURATION_SECONDS),
                "-vf", scale_filter,
                "-c:v", "libvpx-vp9",
                "-b:v", f"{bitrate_kbps}k",
                "-pix_fmt", "yuva420p",
                "-auto-alt-ref", "0",
                "-an",
                "-deadline", "good",
                "-cpu-used", "4",
                str(out_path),
            ]
            try:
                result = subprocess.run(
                    cmd, capture_output=True, timeout=FFMPEG_TIMEOUT_SECONDS
                )
            except subprocess.TimeoutExpired:
                last_error = "vaqt tugadi (ffmpeg juda uzoq ishladi)"
                continue

            if result.returncode != 0:
                last_error = result.stderr.decode(errors="ignore")[-500:]
                continue

            size = out_path.stat().st_size
            if size <= MAX_FILE_SIZE_BYTES:
                return out_path.read_bytes()
            last_error = f"{size} bayt > {MAX_FILE_SIZE_BYTES} bayt chegarasi ({bitrate_kbps}kbps'da)"

        raise RuntimeError(f"GIFni video-stikerga o'girib bo'lmadi: {last_error}")


def image_to_video_sticker(png_bytes: bytes, duration: float = 1.0) -> bytes:
    """Wrap a single still PNG (e.g. a rendered text sticker) into a minimal
    WEBM/VP9 "video" sticker, keeping its transparency.

    Telegram sticker sets can only hold one format at a time - if a pack was
    started with a GIF (making it "video" format), a text/photo sticker has
    to become a trivial looping video too instead of being rejected outright.

    VP9 alpha via ffmpeg (``-pix_fmt yuva420p -auto-alt-ref 0``) does survive
    the round trip - an earlier check here got fooled by ffmpeg's default
    "vp9" decoder, which silently drops the alpha plane; explicitly decoding
    with "-c:v libvpx-vp9" (as done in ``extract_first_frame`` too) preserves
    it. So the source's real transparency is kept instead of being flattened
    onto a solid color.
    """
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = Path(tmpdir) / "frame.png"
        src_path.write_bytes(png_bytes)
        out_path = Path(tmpdir) / "out.webm"

        scale_filter = f"scale='if(gt(iw,ih),{STICKER_SIZE},-2)':'if(gt(iw,ih),-2,{STICKER_SIZE})'"

        last_error = "noma'lum xatolik"
        for bitrate_kbps in BITRATE_ATTEMPTS_KBPS:
            cmd = [
                ffmpeg_exe, "-y",
                "-loop", "1",
                "-i", str(src_path),
                "-t", str(duration),
                "-vf", f"{scale_filter},fps=30",
                "-c:v", "libvpx-vp9",
                "-b:v", f"{bitrate_kbps}k",
                "-pix_fmt", "yuva420p",
                "-auto-alt-ref", "0",
                "-an",
                "-deadline", "good",
                "-cpu-used", "4",
                str(out_path),
            ]
            try:
                result = subprocess.run(
                    cmd, capture_output=True, timeout=FFMPEG_TIMEOUT_SECONDS
                )
            except subprocess.TimeoutExpired:
                last_error = "vaqt tugadi (ffmpeg juda uzoq ishladi)"
                continue

            if result.returncode != 0:
                last_error = result.stderr.decode(errors="ignore")[-500:]
                continue

            size = out_path.stat().st_size
            if size <= MAX_FILE_SIZE_BYTES:
                return out_path.read_bytes()
            last_error = f"{size} bayt > {MAX_FILE_SIZE_BYTES} bayt chegarasi ({bitrate_kbps}kbps'da)"

        raise RuntimeError(f"Stikerni video formatga o'girib bo'lmadi: {last_error}")
