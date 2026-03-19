"""
음성 합성 모듈
Edge TTS (무료)를 사용하여 캐릭터별 음성을 생성한다.
"""

import asyncio
from pathlib import Path

import edge_tts
from moviepy import AudioFileClip


def synthesize_voices(script: dict, config: dict) -> list[dict]:
    """대본의 각 대사를 TTS로 변환하고 오디오 정보를 반환한다."""
    tts_cfg = config["tts"]
    edge_cfg = tts_cfg["edge_tts"]

    voice_map = {
        "a": edge_cfg["voice_a"],
        "b": edge_cfg["voice_b"],
    }
    rate_map = {
        "a": edge_cfg.get("rate_a", "+0%"),
        "b": edge_cfg.get("rate_b", "+0%"),
    }

    audio_dir = Path("audio")
    audio_dir.mkdir(exist_ok=True)

    # 이전 오디오 파일 정리
    for f in audio_dir.glob("line_*.mp3"):
        f.unlink()

    # 비동기 TTS 생성 실행
    audio_entries = asyncio.run(
        _generate_all(script, voice_map, rate_map, audio_dir)
    )

    total = sum(e["duration"] for e in audio_entries)
    print(f"[tts] 전체 오디오 길이: {total:.1f}초")

    if total > 58:
        print(f"[tts] ⚠ 경고: 총 {total:.1f}초로 쇼츠 60초 제한에 근접합니다!")

    return audio_entries


async def _generate_all(
    script: dict,
    voice_map: dict,
    rate_map: dict,
    audio_dir: Path,
) -> list[dict]:
    """모든 대사를 순차적으로 TTS 변환한다."""
    audio_entries = []

    for i, line in enumerate(script["lines"]):
        speaker = line["speaker"]
        text = line["text"]
        voice = voice_map[speaker]
        rate = rate_map[speaker]

        out_path = audio_dir / f"line_{i:03d}_{speaker}.mp3"

        # Edge TTS 생성
        communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
        await communicate.save(str(out_path))

        # moviepy로 오디오 길이 측정 (ffprobe 불필요)
        clip = AudioFileClip(str(out_path))
        duration_sec = clip.duration
        clip.close()

        audio_entries.append({
            "index": i,
            "speaker": speaker,
            "name": line["name"],
            "text": text,
            "audio_path": str(out_path),
            "duration": duration_sec,
        })

        print(f"[tts] ({i+1}/{len(script['lines'])}) {line['name']}: \"{text[:30]}\" → {duration_sec:.1f}s")

    return audio_entries


if __name__ == "__main__":
    import json
    import yaml
    from dotenv import load_dotenv

    load_dotenv()
    with open("config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    scripts_dir = Path("scripts")
    latest = sorted(scripts_dir.glob("debate_*.json"))[-1]
    with open(latest, encoding="utf-8") as f:
        script = json.load(f)

    synthesize_voices(script, config)
