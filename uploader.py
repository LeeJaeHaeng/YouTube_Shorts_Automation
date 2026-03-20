"""
유튜브 업로드 모듈
Google YouTube Data API v3를 사용하여 Shorts 영상을 업로드한다.
"""

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def upload_to_youtube(video_path: str, script: dict, config: dict) -> str:
    """영상을 YouTube Shorts로 업로드하고 영상 URL을 반환한다."""
    up_cfg = config["uploader"]

    # 인증
    youtube = _get_youtube_service(up_cfg)

    # 메타데이터 구성
    title = script.get("title", script.get("topic", "AI 커플 갈등"))
    if len(title) > 100:
        title = title[:97] + "..."

    description = script.get("description", "")
    if not description:
        situation = script.get("situation", "")
        question = script.get("question", "").replace("\\n", " ")
        description = f"{situation}\n\n{question}"

    # config의 태그를 해시태그로 추가
    config_tags = up_cfg.get("tags", [])
    hashtags = " ".join(f"#{t.replace(' ', '')}" for t in config_tags)
    description = description.strip() + f"\n\n{hashtags}"

    tags = list(config_tags)
    topic = script.get("topic", "")
    if topic:
        tags.append(topic[:30])

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": up_cfg["category_id"],
        },
        "status": {
            "privacyStatus": up_cfg["privacy_status"],
            "selfDeclaredMadeForKids": False,
        },
    }

    # 업로드
    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024,  # 10MB 청크
    )

    print(f"[uploader] 업로드 시작: {title}")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"[uploader] 업로드 진행: {pct}%")

    video_id = response["id"]
    video_url = f"https://youtube.com/shorts/{video_id}"
    print(f"[uploader] 업로드 완료: {video_url}")
    return video_url


def _get_youtube_service(up_cfg: dict):
    """YouTube API 서비스 객체를 인증하여 반환한다."""
    creds = None
    token_file = up_cfg["token_file"]
    client_secrets = up_cfg["client_secrets"]

    # 기존 토큰 로드
    if Path(token_file).exists():
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    # 토큰 갱신 또는 새로 발급
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[uploader] 토큰 갱신 중...")
            creds.refresh(Request())
        else:
            if not Path(client_secrets).exists():
                raise FileNotFoundError(
                    f"[uploader] '{client_secrets}' 파일이 없습니다.\n"
                    "Google Cloud Console에서 OAuth 2.0 클라이언트 ID를 생성하고\n"
                    "client_secrets.json을 프로젝트 루트에 놓아주세요.\n"
                    "참고: https://console.cloud.google.com/apis/credentials"
                )
            print("[uploader] 브라우저에서 Google 계정 인증을 진행하세요...")
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES)
            creds = flow.run_local_server(port=0)

        # 토큰 저장
        Path(token_file).write_text(creds.to_json())
        print("[uploader] 인증 토큰 저장 완료")

    return build("youtube", "v3", credentials=creds)


if __name__ == "__main__":
    import json
    import yaml
    from dotenv import load_dotenv

    load_dotenv()
    with open("config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 테스트: 가장 최근 영상 업로드
    output_dir = Path("output")
    latest_video = sorted(output_dir.glob("shorts_*.mp4"))[-1]

    # debate_YYYYMMDD_HHMMSS.json 형식만 선택 (debate_test.json 등 제외)
    scripts_dir = Path("scripts")
    dated_scripts = [
        p for p in scripts_dir.glob("debate_*.json")
        if p.stem.replace("debate_", "").replace("_", "").isdigit()
    ]
    latest_script = sorted(dated_scripts)[-1]
    with open(latest_script, encoding="utf-8") as f:
        script = json.load(f)

    upload_to_youtube(str(latest_video), script, config)
