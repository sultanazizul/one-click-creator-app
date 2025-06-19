import os
import logging
import yt_dlp
import whisper
import ssl
from datetime import timedelta

logger = logging.getLogger(__name__)

def get_video_metadata(video_url, video_path=None):
    """Mengambil metadata video dari URL tanpa perlu file lokal."""
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(video_url, download=False)
            duration = info.get('duration', 0)
            duration_str = str(timedelta(seconds=duration)) if duration else "Unknown"
            filesize = info.get('filesize', 0) / (1024 * 1024) if info.get('filesize') else "Unknown"
            return {
                'title': info.get('title', 'Unknown Title'),
                'uploader': info.get('uploader', 'Unknown Uploader'),
                'size': f"{filesize:.2f} MB" if isinstance(filesize, (int, float)) else filesize,
                'duration': duration_str
            }
    except Exception as e:
        logger.error(f"Error getting video metadata: {str(e)}")
        raise


def transcribe_video_from_url(video_url, audio_path=None):
    try:
        # Temporarily disable SSL verification
        ssl._create_default_https_context = ssl._create_unverified_context
        model = whisper.load_model("base")
        if not audio_path:
            raise ValueError("Audio path must be provided.")
        
        result = model.transcribe(audio_path, verbose=False)
        segments = result['segments']
        timestamps = [
            {
                'start': segment['start'],
                'end': segment['end'],
                'text': segment['text'].strip()
            }
            for segment in segments
        ]
        full_text = result['text'].strip()
        language = result.get('language', 'en')
        
        logger.info(f"Transcription completed for {video_url}")
        return {'text': full_text, 'timestamps': timestamps, 'language': language, 'title': get_video_metadata(video_url)['title']}
    except Exception as e:
        logger.error(f"Error transcribing video: {str(e)}")
        raise