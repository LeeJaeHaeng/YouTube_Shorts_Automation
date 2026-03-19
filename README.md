# 유튜브 쇼츠 자동화 🎬

Google Gemini AI가 두 개의 AI 페르소나(로직봇 vs 감성시인) 토론 대본을 생성하고, Edge TTS로 음성을 합성하여 쇼츠 영상을 제작한 뒤 유튜브에 자동 업로드하는 파이프라인입니다.

## 파이프라인 흐름

```
[1] 대본 생성 (Gemini AI)
    → [2] 음성 합성 (Edge TTS)
        → [3] 영상 편집 (MoviePy)
            → [4] 유튜브 업로드 (YouTube Data API)
```

## 폴더 구조

```
├── main.py             # 메인 오케스트레이터
├── generator.py        # Gemini AI 대본 생성
├── tts.py              # Edge TTS 음성 합성
├── editor.py           # MoviePy 영상 편집
├── uploader.py         # YouTube Data API 업로드
├── config.yaml         # 전체 설정 파일
├── requirements.txt    # 의존성 목록
├── .env.example        # 환경 변수 예시
├── assets/
│   ├── backgrounds/    # 배경 영상/이미지 (background.mp4 또는 .jpg)
│   ├── bgm/            # 배경음악 (bgm.mp3)
│   └── fonts/          # 자막 폰트 (NanumGothicBold.ttf 포함)
├── scripts/            # 생성된 대본 JSON (자동 생성)
├── audio/              # 생성된 TTS 음성 파일 (자동 생성)
└── output/             # 완성된 영상 파일 (자동 생성)
```

## 설치

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env.example`을 복사하여 `.env`를 생성하고 API 키를 입력합니다.

```bash
cp .env.example .env
```

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

- Gemini API 키 발급: https://aistudio.google.com/apikey

### 3. 유튜브 업로드 설정 (선택)

유튜브 업로드를 사용하려면 Google Cloud Console에서 OAuth 2.0 클라이언트 ID를 발급받아 `client_secrets.json`으로 저장합니다.

1. [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → YouTube Data API v3 활성화
2. OAuth 2.0 클라이언트 ID 생성 (데스크톱 앱)
3. JSON 다운로드 → 프로젝트 루트에 `client_secrets.json`으로 저장

### 4. 에셋 준비

| 경로 | 설명 |
|------|------|
| `assets/backgrounds/background.mp4` | 배경 영상 (9:16, 세로형 권장) |
| `assets/bgm/bgm.mp3` | 배경음악 |

> 배경 영상 없이 배경 이미지(`.jpg`)만 있어도 동작합니다.

## 실행 방법

### 기본 실행 (1회 생성 + 업로드)

```bash
python main.py
```

### 업로드 없이 테스트 (영상만 생성)

```bash
python main.py --no-upload
```

### 스케줄 모드 (매일 자동 실행)

```bash
python main.py --schedule
```

`config.yaml`의 `schedule.daily_time`에 설정된 시간(기본: 09:00)에 매일 자동 실행됩니다.

## 설정 (config.yaml)

### 페르소나 커스터마이징

```yaml
generator:
  personas:
    a:
      name: "로직봇"
      description: "극강의 논리와 데이터로 무장한 냉철한 AI 로봇."
      tone: "냉정하고 단호하며, 통계와 논문을 인용한다"
    b:
      name: "감성시인"
      description: "세상 모든 것에서 아름다움을 찾는 낭만적 시인."
      tone: "따뜻하고 감성적이며, 비유와 은유를 즐겨 사용한다"
```

### 토론 주제 추가

`config.yaml`의 `generator.topics` 목록에 원하는 주제를 추가합니다. 매 실행마다 랜덤으로 선택됩니다.

```yaml
  topics:
    - "짜장면 vs 짬뽕, 인류의 운명을 건 최후의 선택"
    - "만약 고양이가 세계를 지배한다면"
    - "나만의 주제 추가"
```

### TTS 음성 변경

```yaml
tts:
  edge_tts:
    voice_a: "ko-KR-InJoonNeural"   # 남성 목소리
    voice_b: "ko-KR-SunHiNeural"    # 여성 목소리
```

사용 가능한 한국어 음성 목록은 [Edge TTS 공식 문서](https://learn.microsoft.com/ko-kr/azure/ai-services/speech-service/language-support)를 참고하세요.

### 스케줄 설정

```yaml
schedule:
  enabled: true
  daily_time: "09:00"   # 24시간 형식
```

## 주요 의존성

| 패키지 | 용도 |
|--------|------|
| `google-genai` | Gemini AI 대본 생성 |
| `edge-tts` | 무료 TTS 음성 합성 |
| `moviepy` | 영상 편집 및 자막 합성 |
| `google-api-python-client` | YouTube Data API 업로드 |
| `python-dotenv` | 환경 변수 관리 |
| `schedule` | 자동 스케줄링 |
