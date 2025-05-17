import logging
import requests

logger = logging.getLogger(__name__)

# Pexels API key (replace with your actual key)
PEXELS_API_KEY = "RkevFNjcykQRRf8b2Ba8PZcEnZqh0lKroLPCCZjsblfCXuSSr1pqu1cY"

def find_videos(summary, keywords):
    """
    Find stock videos from Pexels based on summary and keywords.
    Returns a downloadable video URL.
    """
    try:
        url = "https://api.pexels.com/videos/search"
        headers = {"Authorization": PEXELS_API_KEY}
        params = {"query": " ".join(keywords), "per_page": 1}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        videos = data.get('videos', [])
        if not videos:
            logger.warning(f"No videos found for query: {' '.join(keywords)}")
            raise ValueError("No videos available from Pexels")

        video = videos[0]
        video_files = video.get('video_files', [])
        if not video_files:
            raise ValueError("No video files available for the selected video")

        downloadable_url = max(video_files, key=lambda x: (x.get('width', 0) * x.get('height', 0))).get('link')
        logger.info(f"Found downloadable video: {downloadable_url} for query: {' '.join(keywords)}")
        return downloadable_url
    except Exception as e:
        logger.error(f"Error fetching video from Pexels: {str(e)}")
        # Fallback URL (replace with a valid one or handle differently)
        fallback_url = "https://videos.pexels.com/video-files/4278963/4278963-hd_1920_1080_24fps.mp4"
        response = requests.head(fallback_url, headers={"Authorization": PEXELS_API_KEY})
        if response.status_code != 200:
            logger.error(f"Fallback URL {fallback_url} is not accessible: {response.status_code}")
            raise ValueError("Neither API nor fallback video is accessible")
        logger.warning(f"Using fallback video URL: {fallback_url}")
        return fallback_url

def re_search_video(summary, keywords):
    """Re-search for a stock video from Pexels."""
    return find_videos(summary, keywords)