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


def _flatten_frame(png_path: Path, background: tuple[int, int, int]) -> None:
    from PIL import Image

    with Image.open(png_path) as frame:
        frame = frame.convert("RGBA")
        flattened = Image.new("RGB", frame.size, background)
        flattened.paste(frame, mask=frame.split()[-1])
        flattened.save(png_path)


def convert_to_video_sticker(
    source_bytes: bytes, background: tuple[int, int, int] = (255, 255, 255)
) -> bytes:
    """Convert GIF/MP4 animation bytes into WEBM/VP9 sticker bytes that fit
    Telegram's video-sticker limits.

    Any transparency in the source is flattened onto ``background`` first.
    WebM/VP9 alpha (``-pix_fmt yuva420p``) does encode and decode correctly
    through ffmpeg itself - verified directly by re-decoding a converted
    file with ffmpeg's libvpx-vp9 decoder - but Telegram's own video-sticker
    renderer doesn't honor it in practice: a real device showed a solid
    black box where the transparent background should have been, instead
    of seeing through. So instead of relying on that, each frame is
    composited onto an opaque background before encoding, the same way
    ``image_to_video_sticker`` handles a single still image.

    Raises RuntimeError if ffmpeg fails, or if the file can't be shrunk
    under the size limit even at the lowest attempted bitrate.
    """
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = Path(tmpdir) / "source"
        src_path.write_bytes(source_bytes)
        frames_dir = Path(tmpdir) / "frames"
        frames_dir.mkdir()

        scale_filter = (
            f"scale='if(gt(iw,ih),{STICKER_SIZE},-2)':'if(gt(iw,ih),-2,{STICKER_SIZE})',fps=30"
        )
        extract_cmd = [
            ffmpeg_exe, "-y",
            "-i", str(src_path),
            "-t", str(MAX_DURATION_SECONDS),
            "-vf", scale_filter,
            "-pix_fmt", "rgba",
            str(frames_dir / "frame_%04d.png"),
        ]
        try:
            result = subprocess.run(extract_cmd, capture_output=True, timeout=FFMPEG_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            raise RuntimeError("vaqt tugadi (ffmpeg juda uzoq ishladi)") from None
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode(errors="ignore")[-500:])

        frame_paths = sorted(frames_dir.glob("frame_*.png"))
        if not frame_paths:
            raise RuntimeError("GIFdan birorta ham kadr chiqmadi")
        for frame_path in frame_paths:
            _flatten_frame(frame_path, background)

        out_path = Path(tmpdir) / "out.webm"
        last_error = "noma'lum xatolik"
        for bitrate_kbps in BITRATE_ATTEMPTS_KBPS:
            cmd = [
                ffmpeg_exe, "-y",
                "-framerate", "30",
                "-i", str(frames_dir / "frame_%04d.png"),
                "-c:v", "libvpx-vp9",
                "-b:v", f"{bitrate_kbps}k",
                "-pix_fmt", "yuv420p",
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


def image_to_video_sticker(
    png_bytes: bytes,
    duration: float = 1.0,
    background: tuple[int, int, int] = (255, 255, 255),
) -> bytes:
    """Wrap a single still PNG (e.g. a rendered text sticker) into a minimal
    WEBM/VP9 "video" sticker.

    Telegram sticker sets can only hold one format at a time - if a pack was
    started with a GIF (making it "video" format), a text/photo sticker has
    to become a trivial looping video too instead of being rejected outright.

    Any transparency is flattened onto ``background`` first rather than kept
    as real WebM/VP9 alpha: ffmpeg itself encodes and decodes that alpha
    correctly (verified directly with its libvpx-vp9 decoder), but Telegram's
    own video-sticker renderer doesn't honor it on a real device - it shows
    a solid black box instead of seeing through - so flattening is the only
    approach that reliably looks right for users.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        frame_path = Path(tmpdir) / "frame.png"
        frame_path.write_bytes(png_bytes)
        _flatten_frame(frame_path, background)

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        out_path = Path(tmpdir) / "out.webm"

        scale_filter = f"scale='if(gt(iw,ih),{STICKER_SIZE},-2)':'if(gt(iw,ih),-2,{STICKER_SIZE})'"

        last_error = "noma'lum xatolik"
        for bitrate_kbps in BITRATE_ATTEMPTS_KBPS:
            cmd = [
                ffmpeg_exe, "-y",
                "-loop", "1",
                "-i", str(frame_path),
                "-t", str(duration),
                "-vf", f"{scale_filter},fps=30",
                "-c:v", "libvpx-vp9",
                "-b:v", f"{bitrate_kbps}k",
                "-pix_fmt", "yuv420p",
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
