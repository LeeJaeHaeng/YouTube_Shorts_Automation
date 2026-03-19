"""
영상 편집 모듈
MoviePy + Pillow를 사용하여 배경 영상 위에 오디오, 자막, 배경음악을 합성한다.

스타일: 실사 배경 이미지 + 상단 대형 제목 + 하단 자막 (뉴스 캡션 스타일)
"""

import io
import os
import textwrap
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
)


# ─────────────────────────────────────────
# 배경 이미지 생성 (Gemini)
# ─────────────────────────────────────────

def generate_background_image(script: dict, config: dict, w: int, h: int) -> np.ndarray:
    """
    Gemini Imagen으로 주제에 어울리는 실사 배경 이미지를 생성한다.
    실패 시 그라데이션 배경으로 폴백한다.
    """
    topic = script.get("topic", "")

    cache_dir = Path("assets/backgrounds")
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() else "_" for c in topic[:40])
    cache_path = cache_dir / f"bg_{safe_name}.jpg"

    if cache_path.exists():
        print(f"[editor] 캐시된 배경 이미지 사용: {cache_path.name}")
        img = Image.open(cache_path).convert("RGB").resize((w, h), Image.LANCZOS)
        return _darken_image(np.array(img))

    result = _try_imagen(topic, cache_path, w, h)
    if result is None:
        print("[editor] 이미지 생성 실패 → 그라데이션 배경 사용")
        return _gradient_array(w, h)

    return _darken_image(result)


def _try_imagen(topic: str, cache_path: Path, w: int, h: int):
    """Gemini Imagen으로 배경 이미지 생성."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client()
        prompt = (
            f"A cinematic vertical background image for a Korean YouTube Shorts video. "
            f"Debate topic: '{topic}'. "
            f"Style: dramatic photorealistic scene, dark moody atmosphere, "
            f"relevant symbolic objects, vibrant colors, no text, no human faces. "
            f"Dark enough to overlay white subtitle text on top."
        )
        print(f"[editor] Gemini Imagen으로 배경 이미지 생성 중...")
        response = client.models.generate_images(
            model="imagen-4.0-fast-generate-001",
            prompt=prompt,
            config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio="9:16"),
        )
        image_bytes = response.generated_images[0].image.image_bytes
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((w, h), Image.LANCZOS)
        img.save(str(cache_path), "JPEG", quality=90)
        print(f"[editor] Imagen 배경 생성 완료: {cache_path.name}")
        return np.array(img)
    except Exception as e:
        print(f"[editor] Imagen 실패: {e.__class__.__name__}: {str(e)[:120]}")
        return None


def _darken_image(arr: np.ndarray, factor: float = 0.40) -> np.ndarray:
    """자막 가독성을 위해 배경을 어둡게."""
    return (arr * factor).clip(0, 255).astype(np.uint8)


def _gradient_array(w: int, h: int) -> np.ndarray:
    gradient = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        r = y / h
        gradient[y, :] = [int(10 + 20 * r), int(8 + 8 * r), int(30 + 40 * r)]
    return gradient


# ─────────────────────────────────────────
# 텍스트 렌더링 헬퍼
# ─────────────────────────────────────────

def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except (OSError, IOError):
        return ImageFont.load_default(size)


def _draw_text_with_stroke(draw, pos, text, font, fill, stroke_color, stroke_width):
    """외곽선 있는 텍스트 렌더링."""
    x, y = pos
    for dx in range(-stroke_width, stroke_width + 1):
        for dy in range(-stroke_width, stroke_width + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=stroke_color)
    draw.text((x, y), text, font=font, fill=fill)


def _make_title_overlay(topic: str, font_path: str, w: int, h: int) -> np.ndarray:
    """
    상단 대형 제목 오버레이 이미지 생성.
    참고 영상 스타일: 노란색 + 흰색 조합, 굵은 글씨, 화면 상단 1/3 차지.
    """
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_large = _load_font(font_path, 90)
    font_small = _load_font(font_path, 54)

    # 제목 줄바꿈 (최대 8자씩)
    lines = textwrap.fill(topic, width=9).split("\n")

    # 첫 번째 줄: 노란색
    # 이후 줄: 흰색
    padding_top = int(h * 0.04)
    y = padding_top

    for i, line in enumerate(lines):
        color = "#FFE033" if i == 0 else "white"
        font = font_large if i < 2 else font_small
        stroke = 4

        bb = draw.textbbox((0, 0), line, font=font)
        lw = bb[2] - bb[0]
        lh = bb[3] - bb[1]
        x = (w - lw) // 2

        _draw_text_with_stroke(draw, (x, y), line, font, color, "black", stroke)
        y += lh + 12

    return np.array(img)


def _make_subtitle_image(
    speaker_name: str,
    text: str,
    name_color: str,
    font_path: str,
    w: int,
) -> np.ndarray:
    """
    하단 자막 이미지 생성.
    반투명 검정 박스 + 캐릭터명 + 대사.
    """
    font_name = _load_font(font_path, 40)
    font_text = _load_font(font_path, 56)

    max_chars = 14
    wrapped = textwrap.fill(text, width=max_chars)
    text_lines = wrapped.split("\n")

    # 크기 계산
    dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    name_bb = dummy.textbbox((0, 0), speaker_name, font=font_name)
    name_h = name_bb[3] - name_bb[1]

    text_bbs = [dummy.textbbox((0, 0), l, font=font_text) for l in text_lines]
    text_heights = [bb[3] - bb[1] for bb in text_bbs]
    text_widths  = [bb[2] - bb[0] for bb in text_bbs]

    pad_x, pad_y = 40, 20
    spacing = 8
    box_w = min(w - 40, max(max(text_widths), name_bb[2] - name_bb[0]) + pad_x * 2)
    box_h = name_h + 10 + sum(text_heights) + spacing * (len(text_lines) - 1) + pad_y * 2

    img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 반투명 배경 박스
    draw.rounded_rectangle([(0, 0), (box_w - 1, box_h - 1)], radius=18,
                            fill=(0, 0, 0, 185))

    # 캐릭터 이름
    cx = (box_w - (name_bb[2] - name_bb[0])) // 2
    draw.text((cx, pad_y), speaker_name, font=font_name, fill=name_color)
    y = pad_y + name_h + 10

    # 대사 텍스트
    for i, line in enumerate(text_lines):
        lw = text_bbs[i][2] - text_bbs[i][0]
        tx = (box_w - lw) // 2
        _draw_text_with_stroke(draw, (tx, y), line, font_text, "white", "black", 3)
        y += text_heights[i] + spacing

    return np.array(img)


# ─────────────────────────────────────────
# 메인 영상 생성
# ─────────────────────────────────────────

def create_video(script: dict, audio_entries: list[dict], config: dict) -> str:
    """최종 쇼츠 영상을 생성하고 파일 경로를 반환한다."""
    ed_cfg  = config["editor"]
    W, H    = ed_cfg["width"], ed_cfg["height"]
    fps     = ed_cfg["fps"]
    sub_cfg = ed_cfg["subtitle"]
    name_cfg = ed_cfg["name_tag"]
    font_path = sub_cfg["font"]

    # 1) 배경 이미지 생성
    bg_arr = generate_background_image(script, config, W, H)
    bg_static = ImageClip(bg_arr)

    # 2) 상단 고정 제목 오버레이
    title_arr = _make_title_overlay(script.get("topic", ""), font_path, W, H)
    title_clip = ImageClip(title_arr).with_position(("center", "top"))

    # 3) 오디오 타임라인 구성
    audio_clips = []
    timeline    = []
    gap         = 0.25
    current_time = 0.3

    for entry in audio_entries:
        a_clip = AudioFileClip(entry["audio_path"])
        start = current_time
        end   = start + entry["duration"]
        timeline.append({**entry, "start": start, "end": end})
        audio_clips.append(a_clip.with_start(start))
        current_time = end + gap

    total_duration = current_time + 0.3

    # 쇼츠 59초 제한
    if total_duration > 59.0:
        print(f"[editor] ⚠ {total_duration:.1f}초 → 59초로 자릅니다")
        total_duration = 59.0

    bg_clip = bg_static.with_duration(total_duration).with_fps(fps)
    title_clip = title_clip.with_duration(total_duration)

    # 4) 하단 자막 클립 생성
    subtitle_clips = []
    sub_y_ratio = sub_cfg["position_y_ratio"]  # e.g. 0.70

    for entry in timeline:
        name_color = name_cfg["color_a"] if entry["speaker"] == "a" else name_cfg["color_b"]

        sub_arr = _make_subtitle_image(
            speaker_name=entry["name"],
            text=entry["text"],
            name_color=name_color,
            font_path=font_path,
            w=W,
        )
        sub_h = sub_arr.shape[0]
        sub_y = int(H * sub_y_ratio) - sub_h // 2

        sub_clip = (
            ImageClip(sub_arr)
            .with_duration(entry["end"] - entry["start"])
            .with_start(entry["start"])
            .with_position(("center", sub_y))
        )
        subtitle_clips.append(sub_clip)

    # 5) 오디오 믹싱
    voice_audio = CompositeAudioClip(audio_clips).with_duration(total_duration)

    bgm_path = ed_cfg.get("bgm", "")
    if bgm_path and Path(bgm_path).exists():
        bgm = AudioFileClip(bgm_path).with_volume_scaled(ed_cfg["bgm_volume"])
        if bgm.duration < total_duration:
            bgm = bgm.looped(int(total_duration / bgm.duration) + 1)
        bgm = bgm.subclipped(0, total_duration)
        final_audio = CompositeAudioClip([voice_audio, bgm])
    else:
        final_audio = voice_audio

    # 6) 최종 합성: 배경 + 제목 + 자막
    final = (
        CompositeVideoClip([bg_clip, title_clip] + subtitle_clips, size=(W, H))
        .with_audio(final_audio)
        .with_duration(total_duration)
    )

    # 7) 출력
    out_dir  = Path("output")
    out_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path  = str(out_dir / f"shorts_{timestamp}.mp4")

    print(f"[editor] 렌더링 시작... ({total_duration:.1f}초)")
    final.write_videofile(
        out_path, fps=fps, codec="libx264",
        audio_codec="aac", preset="medium", threads=4,
    )
    print(f"[editor] 영상 생성 완료: {out_path}")
    return out_path


if __name__ == "__main__":
    import json, yaml
    from dotenv import load_dotenv
    load_dotenv()
    with open("config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    from tts import synthesize_voices
    scripts_dir = Path("scripts")
    latest = sorted(scripts_dir.glob("debate_*.json"))[-1]
    with open(latest, encoding="utf-8") as f:
        script = json.load(f)
    audio_entries = synthesize_voices(script, config)
    create_video(script, audio_entries, config)
