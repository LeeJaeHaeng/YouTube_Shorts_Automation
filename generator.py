"""
대본 생성 모듈
Google Gemini API를 사용하여 두 페르소나의 토론 대본을 JSON으로 생성한다.
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
    print(f"[generator] 주제: {topic}")
    print(f"[generator] 대사 수: {len(script['lines'])}개")
    return script


def _build_prompt(personas: dict, topic: str, lines_per_char: int) -> str:
    total_lines = lines_per_char * 2
    return f"""너는 유튜브 쇼츠 대본 작가야. 두 캐릭터가 황당한 주제로 티키타카 토론하는 대본을 만들어줘.

## 캐릭터
- **{personas['a']['name']}**: {personas['a']['description']} (말투: {personas['a']['tone']})
- **{personas['b']['name']}**: {personas['b']['description']} (말투: {personas['b']['tone']})

## 주제
"{topic}"

## 규칙
1. 총 {total_lines}개의 대사를 번갈아가며 작성 (A→B→A→B...)
2. 각 대사는 반드시 30자 이내 (짧고 임팩트 있게, 쇼츠 자막용)
3. 한 대사에 한 문장만 (마침표 하나)
4. 첫 대사는 {personas['a']['name']}이 주제를 던지며 시작
5. 마지막 대사는 웃긴 반전이나 펀치라인으로 마무리
6. 각 캐릭터의 말투와 성격이 확실히 드러나게
7. 한국어로 작성
8. 절대로 30자를 초과하지 말 것

## 출력 형식 (반드시 아래 JSON만 출력, 다른 텍스트 없이)
{{
  "topic": "{topic}",
  "title": "유튜브 쇼츠 제목 (호기심 유발, 30자 이내)",
  "description": "유튜브 설명란 텍스트 (2~3줄)",
  "lines": [
    {{"speaker": "a", "name": "{personas['a']['name']}", "text": "대사 내용"}},
    {{"speaker": "b", "name": "{personas['b']['name']}", "text": "대사 내용"}}
  ]
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
    return script


if __name__ == "__main__":
    import yaml
    from dotenv import load_dotenv
    load_dotenv()
    os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY", "")
    with open("config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    generate_script(config)
