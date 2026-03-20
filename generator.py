"""
대본 생성 모듈
Google Gemini API를 사용하여 남녀/커플 갈등 상황 대본을 JSON으로 생성한다.
각 대사마다 Imagen 이미지 프롬프트가 포함된다.
"""

import json
import os
import random
from datetime import datetime
from pathlib import Path

from google import genai


def generate_script(config: dict) -> dict:
    gen_cfg = config["generator"]
    personas = gen_cfg["personas"]
    topic = random.choice(gen_cfg["topics"])
    lines_per_char = gen_cfg["lines_per_character"]

    prompt = _build_prompt(personas, topic, lines_per_char)

    client = genai.Client()
    response = client.models.generate_content(
        model=gen_cfg["model"],
        contents=prompt,
    )

    script = _parse_response(response.text, personas, topic)

    out_dir = Path("scripts")
    out_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"debate_{timestamp}.json"
    out_path.write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[generator] 대본 생성 완료: {out_path}")
    print(f"[generator] 주제: {script['topic']}")
    print(f"[generator] 상황: {script.get('situation', '')}")
    print(f"[generator] 대사 수: {len(script['lines'])}개")
    return script


def _build_prompt(personas: dict, topic: str, lines_per_char: int) -> str:
    total_lines = lines_per_char * 2
    return f"""너는 유튜브 쇼츠 대본 전문 작가야. 실제 커플 싸움처럼 날 것 그대로의 대본을 써야 해.

## 포맷
실제 남녀/커플 갈등 상황에서 두 캐릭터가 감정적으로 충돌하는 대본.
진짜 싸우는 것처럼 감정이 격하게 고조돼야 해. 마지막엔 시청자에게 판결 요청.

## 캐릭터
- **{personas['a']['name']}** (남자): {personas['a']['description']}
- **{personas['b']['name']}** (여자): {personas['b']['description']}

## 상황
"{topic}"

## 대사 작성 규칙 (매우 중요!)
1. 총 {total_lines}개 대사, A->B->A->B 순서
2. 각 대사 10~25자 (진짜 싸울 때처럼 짧고 강렬하게)
3. 실제 사람이 싸울 때 쓰는 말투로: 비속어, 줄임말, 은어, 감탄사 적극 활용
   - 비속어 예: "아 진짜", "씨", "개열받아", "뭔 개소리야", "기가 막혀"
   - 줄임말 예: "남친", "여친", "솔직", "ㄹㅇ", "존나", "완전"
   - 감탄사 예: "야", "아니", "잠깐만", "ㅋㅋ 뭐야"
4. 감정이 점점 고조되는 흐름 (처음엔 따지기 → 나중엔 폭발)
5. 마지막 대사는 강하게 끊어내거나 반전 펀치라인
6. 절대로 "~입니다", "~하겠습니다" 같은 존댓말/문어체 금지

## 이미지 프롬프트 규칙 (매우 중요!)
- speaker가 "a"(남자)이면: 반드시 "close-up of angry Korean MAN" 으로 시작
- speaker가 "b"(여자)이면: 반드시 "close-up of angry Korean WOMAN" 으로 시작
- 배경에 커플 관계 맥락 포함 (카페, 집, 침대 옆 등)
- 얼굴 표정이 감정을 명확히 드러내야 함
- 실사 사진 스타일, 세로 9:16 비율, 텍스트 없음

## 감정 레벨 (emotion 필드)
- "shouting": 소리지르거나 완전 폭발
- "angry": 화가 많이 남
- "upset": 상처받거나 억울함
- "sarcastic": 비꼬는 말투
- "defiant": 단호하게 선 긋기
- "normal": 비교적 차분

## 출력 형식 (반드시 JSON만, 다른 텍스트 없이)
{{
  "topic": "{topic}",
  "title": "유튜브 쇼츠 제목 (35자 이내, 이모지 포함, 클릭 유발)",
  "description": "영상 설명 (2~3줄, 해시태그 포함)",
  "situation": "상황 요약 (20자 이내, 화면 상단 표시용)",
  "lines": [
    {{
      "speaker": "a",
      "name": "{personas['a']['name']}",
      "text": "비속어/줄임말 포함한 자연스러운 대사",
      "emotion": "angry",
      "image_prompt": "close-up of angry Korean MAN, [구체적 감정 장면], realistic photo style, dramatic lighting, vertical 9:16, no text"
    }},
    {{
      "speaker": "b",
      "name": "{personas['b']['name']}",
      "text": "비속어/줄임말 포함한 자연스러운 대사",
      "emotion": "shouting",
      "image_prompt": "close-up of angry Korean WOMAN, [구체적 감정 장면], realistic photo style, dramatic lighting, vertical 9:16, no text"
    }}
  ],
  "question": "여러분의 판결은? \u2696\ufe0f\\n[A 입장 한 줄] vs [B 입장 한 줄]"
}}"""


def _parse_response(raw_text: str, personas: dict, topic: str) -> dict:
    text = raw_text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        script = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        script = json.loads(text[start:end])

    assert "lines" in script and len(script["lines"]) >= 2
    for line in script["lines"]:
        assert "speaker" in line and "text" in line
        if "image_prompt" not in line:
            line["image_prompt"] = (
                f"Realistic Korean couple illustration, emotional scene related to '{topic}', "
                "cinematic lighting, vertical 9:16 format, no text"
            )
    return script


if __name__ == "__main__":
    import yaml
    from dotenv import load_dotenv
    load_dotenv()
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY", "")
    with open("config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    generate_script(config)
