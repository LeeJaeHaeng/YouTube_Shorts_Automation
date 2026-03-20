"""
영상 편집 모듈
MoviePy + Pillow를 사용하여 대사별 배경 이미지 + 오디오 + 자막을 합성한다.

스타일: 대사마다 Imagen 생성 이미지 교체 + 하단 자막 + 마지막 판결 질문 카드
"""

import io
import os
import textwrap
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
)


# ─────────────────────────────────────────
# 이미지 생성 (Gemini Imagen) - 대사별
# ─────────────────────────────────────────

def generate_images_for_lines(script: dict, config: dict, w: int, h: int) -> list:
    """
    각 대사에 맞는 배경 이미지를 Gemini Imagen으로 생성한다.
    캐시된 이미지가 있으면 재사용, 실패하면 이전 이미지 폴백.
    반환: [np.ndarray, ...] (대사 수만큼)
    """
    lines = script.get("lines", [])
    topic = script.get("topic", "scene")
    safe_topic = "".join(c if c.isalnum() else "_" for c in topic[:20])

    cache_dir = Path("assets/backgrounds")
    cache_dir.mkdir(parents=True, exist_ok=True)

    images = []
    prev_img = _gradient_array(w, h)

    for i, line in enumerate(lines):
        cache_path = cache_dir / f"{safe_topic}_line{i:02d}.jpg"

        if cache_path.exists():
            img = Image.open(cache_path).convert("RGB").resize((w, h), Image.LANCZOS)
            arr = _darken_image(np.array(img))
            images.append(arr)
            prev_img = arr
            print(f"[editor] [{i+1}/{len(lines)}] 캐시 사용")
            continue

        prompt = line.get("image_prompt", "")
        # speaker 기반으로 성별 강제 보정 (Gemini가 틀리게 생성하는 것 방지)
        speaker = line.get("speaker", "a")
        gender_prefix = (
            "close-up of angry Korean MAN as main subject, " if speaker == "a"
            else "close-up of emotional Korean WOMAN as main subject, "
        )
        # 기존 프롬프트에서 잘못된 성별 표현을 교체하고 앞에 강제 지정
        for wrong in ["close-up of angry Korean MAN", "close-up of angry Korean WOMAN",
                      "close-up of emotional Korean MAN", "close-up of emotional Korean WOMAN"]:
            prompt = prompt.replace(wrong, "")
        prompt = gender_prefix + prompt.strip().lstrip(",").strip()

        if not prompt:
            images.append(prev_img)
            continue

        result = _try_imagen(prompt, cache_path, w, h, i + 1, len(lines))
        if result is not None:
            arr = _darken_image(result)
            images.append(arr)
            prev_img = arr
        else:
            images.append(prev_img)

        # Imagen 연속 호출 간격 (할당량 보호)
        if i < len(lines) - 1:
            time.sleep(2)

    return images


def _try_imagen(prompt: str, cache_path: Path, w: int, h: int, idx: int, total: int):
    try:
        from google import genai
        from google.genai import types

        client = genai.Client()
        full_prompt = (
            prompt + " Dark enough to overlay white subtitle text. No watermark. No UI elements."
        )
        print(f"[editor] [{idx}/{total}] Imagen 생성 중...")
        response = client.models.generate_images(
            model="imagen-4.0-fast-generate-001",
            prompt=full_prompt,
            config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio="9:16"),
        )
        image_bytes = response.generated_images[0].image.image_bytes
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((w, h), Image.LANCZOS)
        img.save(str(cache_path), "JPEG", quality=90)
        print(f"[editor] [{idx}/{total}] 생성 완료: {cache_path.name}")
        return np.array(img)
    except Exception as e:
        print(f"[editor] [{idx}/{total}] Imagen 실패: {e.__class__.__name__}: {str(e)[:100]}")
        return None


def _darken_image(arr: np.ndarray, factor: float = 0.42) -> np.ndarray:
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
    x, y = pos
    for dx in range(-stroke_width, stroke_width + 1):
        for dy in range(-stroke_width, stroke_width + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=stroke_color)
    draw.text((x, y), text, font=font, fill=fill)


def _make_situation_overlay(situation: str, font_path: str, w: int, h: int) -> np.ndarray:
    """
    상단 상황 설명 오버레이 (작은 텍스트 + 반투명 배경).
    """
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font = _load_font(font_path, 52)
    bb = draw.textbbox((0, 0), situation, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]

    pad_x, pad_y = 30, 16
    box_w = tw + pad_x * 2
    box_h = th + pad_y * 2
    box_x = (w - box_w) // 2
    box_y = int(h * 0.03)

    draw.rounded_rectangle(
        [(box_x, box_y), (box_x + box_w, box_y + box_h)],
        radius=14, fill=(0, 0, 0, 170)
    )
    tx = box_x + pad_x
    ty = box_y + pad_y
    _draw_text_with_stroke(draw, (tx, ty), situation, font, "#FFE033", "black", 3)
    return np.array(img)


def _make_subtitle_image(
    speaker_name: str,
    text: str,
    name_color: str,
    font_path: str,
    w: int,
) -> np.ndarray:
    """하단 자막: 반투명 박스 + 캐릭터명 + 대사."""
    font_name = _load_font(font_path, 38)
    font_text = _load_font(font_path, 60)

    wrapped = textwrap.fill(text, width=13)
    text_lines = wrapped.split("\n")

    dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    name_bb = dummy.textbbox((0, 0), speaker_name, font=font_name)
    name_h = name_bb[3] - name_bb[1]

    text_bbs = [dummy.textbbox((0, 0), l, font=font_text) for l in text_lines]
    text_heights = [bb[3] - bb[1] for bb in text_bbs]
    text_widths = [bb[2] - bb[0] for bb in text_bbs]

    pad_x, pad_y = 44, 22
    spacing = 10
    box_w = min(w - 40, max(max(text_widths, default=200), name_bb[2] - name_bb[0]) + pad_x * 2)
    box_h = name_h + 14 + sum(text_heights) + spacing * max(len(text_lines) - 1, 0) + pad_y * 2

    img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle([(0, 0), (box_w - 1, box_h - 1)], radius=20, fill=(0, 0, 0, 190))

    cx = (box_w - (name_bb[2] - name_bb[0])) // 2
    draw.text((cx, pad_y), speaker_name, font=font_name, fill=name_color)
    y = pad_y + name_h + 14

    for i, line in enumerate(text_lines):
        lw = text_bbs[i][2] - text_bbs[i][0]
        tx = (box_w - lw) // 2
        _draw_text_with_stroke(draw, (tx, y), line, font_text, "white", "black", 3)
        y += text_heights[i] + spacing

    return np.array(img)


def _make_question_card(question: str, font_path: str, w: int, h: int) -> np.ndarray:
    """
    마지막 판결 질문 카드 오버레이.
    화면 하단 절반을 채우는 반투명 어두운 박스.
    """
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_q = _load_font(font_path, 52)
    font_hint = _load_font(font_path, 40)

    lines = question.replace("\\n", "\n").split("\n")
    hint = "댓글로 판결해주세요!"

    # 전체 박스 (화면 하단 45%)
    box_h = int(h * 0.45)
    box_y = h - box_h
    draw.rectangle([(0, box_y), (w, h)], fill=(0, 0, 0, 210))

    # 구분선
    draw.line([(40, box_y + 10), (w - 40, box_y + 10)], fill="#FFE033", width=4)

    y = box_y + 40
    for line in lines:
        if not line.strip():
            y += 20
            continue
        wrapped = textwrap.fill(line.strip(), width=16)
        for wl in wrapped.split("\n"):
            bb = draw.textbbox((0, 0), wl, font=font_q)
            lw = bb[2] - bb[0]
            lh = bb[3] - bb[1]
            tx = (w - lw) // 2
            _draw_text_with_stroke(draw, (tx, y), wl, font_q, "white", "black", 3)
            y += lh + 12

    y += 16
    bb = draw.textbbox((0, 0), hint, font=font_hint)
    lw = bb[2] - bb[0]
    tx = (w - lw) // 2
    _draw_text_with_stroke(draw, (tx, y), hint, font_hint, "#FFE033", "black", 2)

    return np.array(img)


# ─────────────────────────────────────────
# 메인 영상 생성
# ─────────────────────────────────────────

def create_video(script: dict, audio_entries: list, config: dict) -> str:
    ed_cfg = config["editor"]
    W, H = ed_cfg["width"], ed_cfg["height"]
    fps = ed_cfg["fps"]
    sub_cfg = ed_cfg["subtitle"]
    name_cfg = ed_cfg["name_tag"]
    font_path = sub_cfg["font"]

    # 1) 대사별 배경 이미지 생성
    print(f"[editor] 대사 {len(script['lines'])}개에 대한 배경 이미지 생성 시작...")
    images = generate_images_for_lines(script, config, W, H)

    # 2) 오디오 타임라인 구성
    audio_clips = []
    timeline = []
    gap = 0.20
    current_time = 0.4

    for i, entry in enumerate(audio_entries):
        a_clip = AudioFileClip(entry["audio_path"])
        start = current_time
        end = start + entry["duration"]
        timeline.append({**entry, "start": start, "end": end, "index": i})
        audio_clips.append(a_clip.with_start(start))
        current_time = end + gap

    # 판결 카드 표시 시간 (마지막 대사 후 4초)
    question_start = current_time + 0.2
    question_duration = 4.0
    total_duration = question_start + question_duration

    # 쇼츠 59초 제한
    if total_duration > 59.0:
        print(f"[editor] {total_duration:.1f}초 → 59초로 자릅니다")
        total_duration = 59.0
        question_duration = max(1.0, total_duration - question_start)

    print(f"[editor] 총 영상 길이: {total_duration:.1f}초")

    # 3) 배경 클립: 대사마다 이미지 교체
    # 각 이미지는 해당 대사 시작부터 다음 대사 시작 전까지 표시
    bg_clips = []

    # 첫 대사 전 구간: 첫 번째 이미지
    if timeline:
        first_img = images[0] if images else _gradient_array(W, H)
        pre_clip = (
            ImageClip(first_img)
            .with_start(0)
            .with_duration(timeline[0]["start"])
            .with_fps(fps)
        )
        bg_clips.append(pre_clip)

    for i, entry in enumerate(timeline):
        img = images[i] if i < len(images) else (images[-1] if images else _gradient_array(W, H))

        seg_start = entry["start"]
        if i < len(timeline) - 1:
            seg_end = timeline[i + 1]["start"]
        else:
            seg_end = question_start  # 마지막 대사 → 판결 카드까지

        duration = seg_end - seg_start
        if duration <= 0:
            continue

        clip = (
            ImageClip(img)
            .with_start(seg_start)
            .with_duration(duration)
            .with_fps(fps)
        )
        bg_clips.append(clip)

    # 판결 카드 구간: 마지막 이미지 유지 (어둡게)
    if images:
        last_img = (images[-1] * 0.6).clip(0, 255).astype(np.uint8)
        q_bg = (
            ImageClip(last_img)
            .with_start(question_start)
            .with_duration(question_duration)
            .with_fps(fps)
        )
        bg_clips.append(q_bg)

    # 4) 상단 상황 설명 오버레이 (전체 구간)
    situation = script.get("situation", script.get("topic", ""))
    sit_arr = _make_situation_overlay(situation, font_path, W, H)
    sit_clip = ImageClip(sit_arr).with_duration(total_duration)

    # 5) 하단 자막 클립 생성
    subtitle_clips = []
    sub_y_ratio = sub_cfg["position_y_ratio"]

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

    # 6) 판결 질문 카드
    question_clips = []
    question_text = script.get("question", "여러분의 판결은?")
    q_arr = _make_question_card(question_text, font_path, W, H)
    q_clip = (
        ImageClip(q_arr)
        .with_start(question_start)
        .with_duration(question_duration)
    )
    question_clips.append(q_clip)

    # 7) 오디오 믹싱
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

    # 8) 최종 합성
    all_clips = bg_clips + [sit_clip] + subtitle_clips + question_clips
    final = (
        CompositeVideoClip(all_clips, size=(W, H))
        .with_audio(final_audio)
        .with_duration(total_duration)
    )

    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = str(out_dir / f"shorts_{timestamp}.mp4")

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
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY", "")
    with open("config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    from tts import synthesize_voices
    scripts_dir = Path("scripts")
    latest = sorted(scripts_dir.glob("debate_*.json"))[-1]
    with open(latest, encoding="utf-8") as f:
        script = json.load(f)
    audio_entries = synthesize_voices(script, config)
    create_video(script, audio_entries, config)
