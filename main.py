"""
메인 오케스트레이터
전체 파이프라인을 순차 실행하고, 스케줄링을 관리한다.
"""

import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import schedule
import yaml
from dotenv import load_dotenv

from generator import generate_script
from tts import synthesize_voices
from editor import create_video
from uploader import upload_to_youtube


def load_config() -> dict:
    """설정 파일을 로드한다."""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_pipeline(config: dict = None, skip_upload: bool = False):
    """전체 파이프라인을 1회 실행한다."""
    if config is None:
        config = load_config()

    start_time = datetime.now()
    print("=" * 50)
    print(f"[main] 파이프라인 시작: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    try:
        # Step 1: 대본 생성
        print("\n📝 [Step 1/4] 대본 생성 중...")
        script = generate_script(config)

        # Step 2: TTS 음성 합성
        print("\n🎤 [Step 2/4] 음성 합성 중...")
        audio_entries = synthesize_voices(script, config)

        # Step 3: 영상 편집
        print("\n🎬 [Step 3/4] 영상 편집 중...")
        video_path = create_video(script, audio_entries, config)

        # Step 4: 유튜브 업로드
        if skip_upload:
            print("\n⏭ [Step 4/4] 업로드 건너뜀 (--no-upload)")
            video_url = "(업로드 건너뜀)"
        else:
            print("\n📤 [Step 4/4] 유튜브 업로드 중...")
            video_url = upload_to_youtube(video_path, script, config)

        elapsed = (datetime.now() - start_time).total_seconds()
        print("\n" + "=" * 50)
        print(f"[main] 파이프라인 완료! ({elapsed:.0f}초 소요)")
        print(f"[main] 주제: {script.get('topic', 'N/A')}")
        print(f"[main] 영상: {video_path}")
        print(f"[main] URL: {video_url}")
        print("=" * 50)

        return {"success": True, "video_path": video_path, "url": video_url}

    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n❌ [main] 파이프라인 실패 ({elapsed:.0f}초): {e}")
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def run_scheduler():
    """매일 정해진 시간에 파이프라인을 실행하는 스케줄러."""
    config = load_config()
    sched_cfg = config["schedule"]

    if not sched_cfg.get("enabled", False):
        print("[main] 스케줄링이 비활성화 상태입니다. config.yaml에서 schedule.enabled: true로 변경하세요.")
        return

    daily_time = sched_cfg["daily_time"]
    print(f"[main] 스케줄러 시작 — 매일 {daily_time}에 실행됩니다.")
    print("[main] 종료하려면 Ctrl+C를 누르세요.\n")

    schedule.every().day.at(daily_time).do(run_pipeline, config=config)

    while True:
        schedule.run_pending()
        time.sleep(30)


def main():
    import os
    load_dotenv()

    # google-genai는 GOOGLE_API_KEY 환경변수를 사용
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and not os.getenv("GOOGLE_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = gemini_key

    # imageio-ffmpeg의 ffmpeg 바이너리를 pydub에서도 사용할 수 있게 PATH에 추가
    try:
        import imageio_ffmpeg
        ffmpeg_dir = str(Path(imageio_ffmpeg.get_ffmpeg_exe()).parent)
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    except ImportError:
        pass

    args = sys.argv[1:]

    if "--schedule" in args:
        # 스케줄 모드: 매일 자동 실행
        run_scheduler()
    elif "--no-upload" in args:
        # 업로드 없이 1회 실행 (테스트용)
        run_pipeline(skip_upload=True)
    else:
        # 기본: 1회 실행
        run_pipeline()


if __name__ == "__main__":
    main()
