from flask import Flask, render_template, request, jsonify, send_from_directory
from app.idea_to_video.story_generator import generate_story
from app.idea_to_video.voice_over import generate_voice_over
from app.idea_to_video.video_matching import find_videos, re_search_video
from app.idea_to_video.video_merging import merge_videos
from app.video_transcript.video_transcription import transcribe_video_from_url, get_video_metadata
from app.video_transcript.ai_assistant.ai_processor import generate_summary, translate_text
from moviepy.config import change_settings
from dotenv import load_dotenv
import logging
import json
import os
import shutil
import urllib.parse
import requests
import whisper
import yt_dlp
import hashlib
import tempfile
import ffmpeg

# Configure ImageMagick and FFmpeg paths for MoviePy
change_settings({
    "IMAGEMAGICK_BINARY": "/usr/local/bin/magick",
    "FFMPEG_BINARY": "/usr/local/bin/ffmpeg"
})

# Load environment variables
load_dotenv()
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pexels API key (replace with your actual key)
PEXELS_API_KEY = "RkevFNjcykQRRf8b2Ba8PZcEnZqh0lKroLPCCZjsblfCXuSSr1pqu1cY"

# Suggested titles for different themes
SUGGESTED_TITLES = {
    'none': ['Untitled'],
    'inspiration': ['A Journey of Self-Discovery', 'Overcoming Life’s Challenges', 'The Power of Perseverance', 'Finding Hope in Dark Times'],
    'education': ['The Science of Everyday Life', 'History’s Hidden Stories', 'Mastering New Skills', 'The Art of Problem Solving'],
    'romance': ['Love at First Sight', 'A Summer Romance', 'Rekindling Old Flames', 'Love Against All Odds'],
    'comedy': ['A Day Full of Mishaps', 'The Misadventure Chronicles', 'Laughing Through Chaos', 'When Plans Go Wrong'],
    'adventure': ['Quest for the Lost Treasure', 'Surviving the Wilderness', 'The Great Expedition', 'Chasing the Unknown']
}

# Direktori
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
VIDEO_DIR = os.path.join(TEMP_DIR, "videos")
AUDIO_DIR = os.path.join(TEMP_DIR, "audio")
PROJECT_DIR = os.path.join(BASE_DIR, "AI Transcript")

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(PROJECT_DIR, exist_ok=True)

def create_project_dirs(title):
    """Create project directories for videos and audio."""
    project_path = os.path.join(BASE_DIR, 'projects', title)
    os.makedirs(os.path.join(project_path, 'videos'), exist_ok=True)
    os.makedirs(os.path.join(project_path, 'audio'), exist_ok=True)
    logger.info(f"Created project directories for: {title}")
    return project_path

@app.route('/')
def index():
    return render_template('index.html', active_page='dashboard')

@app.route('/get_suggested_titles')
def get_suggested_titles():
    theme = request.args.get('theme')
    titles = SUGGESTED_TITLES.get(theme, ['Untitled'])
    logger.info(f"Fetched suggested titles for theme: {theme}")
    return jsonify({'titles': titles})

@app.route('/projects/<path:filepath>')
def serve_project_file(filepath):
    """Serve files from the projects directory."""
    file_path = os.path.join(BASE_DIR, 'projects', filepath)
    if os.path.exists(file_path):
        return send_from_directory(os.path.dirname(file_path), os.path.basename(file_path))
    else:
        return jsonify({'error': 'File not found'}), 404  # Corrected syntax

@app.route('/exports/<path:filepath>')
def serve_exported_file(filepath):
    """Serve files from the exports directory."""
    file_path = os.path.join(EXPORTS_DIR, filepath)
    if os.path.exists(file_path):
        return send_from_directory(EXPORTS_DIR, os.path.basename(file_path), as_attachment=True)
    else:
        return jsonify({'error': 'File not found'}), 404  # Corrected syntax

@app.route('/get_projects')
def get_projects():
    """Return a list of existing project directories."""
    projects = [d for d in os.listdir(os.path.join(BASE_DIR, 'projects')) if os.path.isdir(os.path.join(BASE_DIR, 'projects', d))]
    logger.info(f"Retrieved projects: {projects}")
    return jsonify({'projects': projects})

@app.route('/get_project_data')
def get_project_data():
    """Return the story and scene data for a given project."""
    project_title = request.args.get('project_title')
    project_path = os.path.join(BASE_DIR, 'projects', project_title)
    if not os.path.exists(project_path):
        return jsonify({'error': 'Project not found'}), 404

    # Load story and scene data from JSON file
    data_file = os.path.join(project_path, f"{project_title}.json")
    story = "Sample story content"  # Default if file not found
    scene_data = {}
    if os.path.exists(data_file):
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            story = data.get('story', story)
            scene_data = data.get('sceneData', {})
    logger.info(f"Retrieved data for project {project_title}: {story}")
    return jsonify({'story': story, 'sceneData': scene_data})

def generate_unique_id(video_url):
    """Generate a unique ID based on the video URL."""
    return hashlib.md5(video_url.encode()).hexdigest()

def get_next_project_folder(title):
    """Get the next project folder name based on existing folders."""
    existing_folders = [d for d in os.listdir(PROJECT_DIR) if d.startswith("Project")]
    max_num = 0
    for folder in existing_folders:
        try:
            num = int(folder.split("Project ")[1].split(" -")[0])
            max_num = max(max_num, num)
        except (IndexError, ValueError):
            continue
    new_num = max_num + 1
    sanitized_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()
    return os.path.join(PROJECT_DIR, f"Project {new_num} - {sanitized_title}")

def download_video_and_audio(video_url):
    logger.info(f"Starting download for URL: {video_url}")
    unique_id = generate_unique_id(video_url)
    video_path = os.path.join(VIDEO_DIR, f"{unique_id}.mp4")
    audio_path = os.path.join(AUDIO_DIR, f"{unique_id}.mp3")

    ydl_opts = {
        'format': 'best',
        'outtmpl': video_path,
        'quiet': False,
        'verbose': True,  # Enable verbose logging for debugging
        'nocheckcertificate': True  # Temporary workaround for SSL issue
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            title = info.get('title', 'Unknown Title')
        logger.info(f"Video downloaded: {video_path}")
    except Exception as e:
        logger.error(f"Error downloading video from {video_url}: {str(e)}", exc_info=True)
        raise

    try:
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(stream, audio_path, format='mp3', acodec='mp3')
        ffmpeg.run(stream, overwrite_output=True, quiet=True)
        logger.info(f"Audio extracted: {audio_path}")
    except Exception as e:
        logger.error(f"Error extracting audio: {str(e)}")
        raise

    return video_path, audio_path, title

@app.route('/transcript', methods=['GET', 'POST'])
def transcript():
    if request.method == 'POST':
        video_url = request.form.get('video_url')
        action = request.form.get('action')
        if not video_url:
            return jsonify({'error': 'URL video tidak ditemukan'}), 400

        unique_id = generate_unique_id(video_url)
        video_path = os.path.join(VIDEO_DIR, f"{unique_id}.mp4")
        audio_path = os.path.join(AUDIO_DIR, f"{unique_id}.mp3")
        project_folder = None

        if action == 'download':
            try:
                # Download video and audio
                video_path, audio_path, title = download_video_and_audio(video_url)
                metadata = get_video_metadata(video_url, video_path)
                return jsonify({'metadata': metadata, 'video_url': video_url})  # Return original URL instead of file path
            except Exception as e:
                logger.error(f"Error processing video: {str(e)}")
                return jsonify({'error': str(e)}), 500

        elif action == 'transcribe':
            if not os.path.exists(audio_path):
                return jsonify({'error': 'Audio file not found. Please download the video first.'}), 400
            try:
                transcript_data = transcribe_video_from_url(video_url, audio_path=audio_path)
                # Create project folder and save transcript
                project_folder = get_next_project_folder(transcript_data.get('title', 'Unknown Title'))
                os.makedirs(project_folder, exist_ok=True)
                transcript_path = os.path.join(project_folder, f"transcript_{unique_id}.json")
                transcript_json = {
                    'video_url': video_url,
                    'transcript': transcript_data['text'],
                    'timestamps': transcript_data['timestamps']
                }
                with open(transcript_path, 'w', encoding='utf-8') as f:
                    json.dump(transcript_json, f, ensure_ascii=False, indent=4)
                logger.info(f"Transcript saved: {transcript_path}")

                # Clean up temporary files
                if os.path.exists(video_path):
                    os.remove(video_path)
                    logger.info(f"Deleted temporary video: {video_path}")
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                    logger.info(f"Deleted temporary audio: {audio_path}")

                return jsonify({'transcript': transcript_data['text'], 'timestamps': transcript_data['timestamps']})
            except Exception as e:
                logger.error(f"Error transcribing video: {str(e)}")
                return jsonify({'error': str(e)}), 500

        elif action == 'load_transcript':
            # Search for transcript in all project folders
            for folder in os.listdir(PROJECT_DIR):
                folder_path = os.path.join(PROJECT_DIR, folder)
                if os.path.isdir(folder_path):
                    transcript_path = os.path.join(folder_path, f"transcript_{unique_id}.json")
                    if os.path.exists(transcript_path):
                        with open(transcript_path, 'r', encoding='utf-8') as f:
                            transcript_data = json.load(f)
                        return jsonify({
                            'transcript': transcript_data['transcript'],
                            'timestamps': transcript_data['timestamps']
                        })
            return jsonify({'error': 'Transcript not found'}), 404

        elif action == 'load_summary':
            # Search for summary in all project folders
            for folder in os.listdir(PROJECT_DIR):
                folder_path = os.path.join(PROJECT_DIR, folder)
                if os.path.isdir(folder_path):
                    summary_path = os.path.join(folder_path, f"summary_{unique_id}.json")
                    if os.path.exists(summary_path):
                        with open(summary_path, 'r', encoding='utf-8') as f:
                            summary_data = json.load(f)
                        return jsonify({
                            'summary': summary_data['summary'],
                            'key_points': summary_data['key_points']
                        })
            return jsonify({'error': 'Summary not found'}), 404

    return render_template('transcript.html', active_page='transcript')

@app.route('/get_summary', methods=['POST'])
def get_summary():
    video_url = request.form.get('video_url')
    transcript = request.form.get('transcript')
    if not transcript or not video_url:
        return jsonify({'error': 'No transcript or video URL provided'}), 400

    unique_id = generate_unique_id(video_url)
    # Search for existing project folder or create new one
    project_folder = None
    for folder in os.listdir(PROJECT_DIR):
        folder_path = os.path.join(PROJECT_DIR, folder)
        if os.path.isdir(folder_path):
            transcript_path = os.path.join(folder_path, f"transcript_{unique_id}.json")
            if os.path.exists(transcript_path):
                project_folder = folder_path
                break
    if not project_folder:
        project_folder = get_next_project_folder("Unknown Title")
        os.makedirs(project_folder, exist_ok=True)

    summary_path = os.path.join(project_folder, f"summary_{unique_id}.json")

    try:
        summary = generate_summary(transcript)
        summary_lines = summary.split('\n')
        summary_text = ''
        key_points = []
        in_key_points = False
        for line in summary_lines:
            if line.startswith('Summary:'):
                continue
            elif line.startswith('Key Points:'):
                in_key_points = True
            elif in_key_points and line.strip():
                key_points.append(line.strip())
            elif line.strip():
                summary_text += (summary_text and '\n') + line.strip()

        summary_data = {
            'video_url': video_url,
            'summary': summary_text,
            'key_points': key_points
        }
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=4)
        logger.info(f"Summary saved: {summary_path}")
        return jsonify({'summary': summary_text, 'key_points': key_points})
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/translate', methods=['POST'])
def translate():
    text = request.form.get('text')
    target_lang = request.form.get('target_lang')
    if not text or not target_lang:
        return jsonify({'error': 'Text or target language missing'}), 400
    try:
        translated = translate_text(text, target_lang)
        return jsonify({'translated': translated})
    except Exception as e:
        logger.error(f"Error translating text: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/idea_to_video', methods=['GET', 'POST'])
def idea_to_video():
    if request.method == 'POST':
        prompt = request.form.get('prompt')
        theme = request.form.get('theme', 'none')  # Default to 'none'
        duration = request.form.get('duration')
        video_ratio = request.form.get('video_ratio')  # New video ratio parameter
        action = request.form.get('action')
        story = request.form.get('story')
        scene = request.form.get('scene')
        script = request.form.get('script')
        scene_data = request.form.get('scene_data')
        project_title = request.form.get('project_title')

        logger.info(f"Received: Prompt={prompt}, Theme={theme}, Duration={duration}, Video Ratio={video_ratio}, Action={action}, Scene={scene}, Script={script}, Project Title={project_title}")

        if video_ratio:
            logger.info(f"User selected video ratio: {video_ratio}")

        if action == 'generate_story':
            suggested_title = request.form.get('suggested_title', '')
            if suggested_title:
                prompt = suggested_title
                logger.info(f"Using suggested title as prompt: {suggested_title}")
            story = generate_story(prompt, theme, duration)
            lines = story.split('\n')
            project_title = next((line.replace('Title:', '').strip() for line in lines if line.startswith('Title:')), prompt or SUGGESTED_TITLES.get(theme, ['Untitled'])[0])
            project_title = project_title.replace(' ', '_').replace('/', '_')
            scene_data = {}
            current_scene = None
            for line in story.split('\n'):
                if line.startswith('Scene:'):
                    current_scene = line.replace('Scene:', '').strip()
                elif line.startswith('Script:') and current_scene:
                    script = line.replace('Script:', '').strip()
                    scene_data[current_scene] = {'script': script, 'video': None, 'audio': None}
            temp_data_file = os.path.join(TEMP_DIR, f"{project_title}_temp.json")
            try:
                with open(temp_data_file, 'w', encoding='utf-8') as f:
                    json.dump({'story': story, 'sceneData': scene_data}, f, ensure_ascii=False, indent=4)
                logger.info(f"Successfully saved temp file: {temp_data_file}")
            except Exception as e:
                logger.error(f"Failed to save temp file {temp_data_file}: {str(e)}")
                return jsonify({'error': f"Failed to save temporary data: {str(e)}"}), 500
            if not os.path.exists(temp_data_file):
                logger.error(f"Temp file {temp_data_file} was not created")
                return jsonify({'error': 'Temporary data file was not created'}), 500
            logger.info(f"Generated story: {story}, Project Title: {project_title}, Temp file: {temp_data_file}")
            return jsonify({'story': story, 'project_title': project_title})
        elif action == 'regenerate':
            suggested_title = request.form.get('suggested_title', '')
            if suggested_title:
                prompt = suggested_title
                logger.info(f"Using suggested title as prompt for regeneration: {suggested_title}")
            story = generate_story(prompt, theme, duration)
            lines = story.split('\n')
            project_title = next((line.replace('Title:', '').strip() for line in lines if line.startswith('Title:')), prompt or SUGGESTED_TITLES.get(theme, ['Untitled'])[0])
            project_title = project_title.replace(' ', '_').replace('/', '_')
            scene_data = {}
            current_scene = None
            for line in story.split('\n'):
                if line.startswith('Scene:'):
                    current_scene = line.replace('Scene:', '').strip()
                elif line.startswith('Script:') and current_scene:
                    script = line.replace('Script:', '').strip()
                    scene_data[current_scene] = {'script': script, 'video': None, 'audio': None}
            temp_data_file = os.path.join(TEMP_DIR, f"{project_title}_temp.json")
            try:
                with open(temp_data_file, 'w', encoding='utf-8') as f:
                    json.dump({'story': story, 'sceneData': scene_data}, f, ensure_ascii=False, indent=4)
                logger.info(f"Successfully saved temp file: {temp_data_file}")
            except Exception as e:
                logger.error(f"Failed to save temp file {temp_data_file}: {str(e)}")
                return jsonify({'error': f"Failed to save temporary data: {str(e)}"}), 500
            if not os.path.exists(temp_data_file):
                logger.error(f"Temp file {temp_data_file} was not created")
                return jsonify({'error': 'Temporary data file was not created'}), 500
            logger.info(f"Regenerated story: {story}, Updated Temp file: {temp_data_file}")
            return jsonify({'story': story, 'project_title': project_title})
        elif action == 'create_project':
            project_path = create_project_dirs(project_title)
            temp_data_file = os.path.join(TEMP_DIR, f"{project_title}_temp.json")
            logger.info(f"Attempting to move temp file: {temp_data_file} to {project_path}")
            if os.path.exists(temp_data_file):
                project_data_file = os.path.join(project_path, f"{project_title}.json")
                shutil.move(temp_data_file, project_data_file)
                logger.info(f"Moved temp data to project directory: {project_data_file}")
                return jsonify({'status': 'success'})
            else:
                logger.error(f"Temporary data file not found for {project_title}")
                return jsonify({'error': 'Temporary data not found'}), 400
        elif action == 'generate_audio':
            try:
                scene_data = json.loads(scene_data)
                audios = {}
                project_path = os.path.join('projects', project_title)
                for scene, data in scene_data.items():
                    script = data['script']
                    audio_path = os.path.join(project_path, 'audio', f"{scene.replace(' ', '_')}.mp3")
                    generate_voice_over(script, audio_path)
                    audios[scene] = audio_path
                    data['audio'] = audio_path
                data_file = os.path.join(project_path, f"{project_title}.json")
                if os.path.exists(data_file):
                    with open(data_file, 'r', encoding='utf-8') as f:
                        project_data = json.load(f)
                    project_data['sceneData'] = scene_data
                    with open(data_file, 'w', encoding='utf-8') as f:
                        json.dump(project_data, f, ensure_ascii=False, indent=4)
                logger.info(f"Generated audios: {audios}")
                return jsonify({'audios': audios})
            except Exception as e:
                logger.error(f"Error generating audio: {str(e)}")
                return jsonify({'error': f"Failed to generate audio: {str(e)}"}), 500
        elif action == 'find_videos':
            try:
                scene_data = json.loads(scene_data)
                videos = {}
                project_path = os.path.join('projects', project_title)
                for scene, data in scene_data.items():
                    summary = f"{data['script'][:50]}..."
                    keywords = data['script'].split()[:3]
                    video_url = find_videos(summary, keywords)
                    video_path = download_video(video_url, scene, project_path)
                    videos[scene] = {'url': video_url, 'path': video_path}
                    data['video'] = videos[scene]
                data_file = os.path.join(project_path, f"{project_title}.json")
                if os.path.exists(data_file):
                    with open(data_file, 'r', encoding='utf-8') as f:
                        project_data = json.load(f)
                    project_data['sceneData'] = scene_data
                    with open(data_file, 'w', encoding='utf-8') as f:
                        json.dump(project_data, f, ensure_ascii=False, indent=4)
                logger.info(f"Found videos: {videos}")
                return jsonify({'videos': videos})
            except Exception as e:
                logger.error(f"Error finding videos: {str(e)}")
                return jsonify({'error': f"Failed to find videos: {str(e)}"}), 500
        elif action == 'research_video':
            try:
                summary = f"{script[:50]}..."
                keywords = script.split()[:3]
                project_path = os.path.join('projects', project_title)
                old_video_path = os.path.join(project_path, 'videos', f"{scene.replace(' ', '_')}.mp4")
                if os.path.exists(old_video_path):
                    os.remove(old_video_path)
                    logger.info(f"Deleted old video for scene {scene}: {old_video_path}")
                video_url = re_search_video(summary, keywords)
                video_path = download_video(video_url, scene, project_path)
                logger.info(f"Re-searched video for scene {scene}: {video_url}")
                scene_data = json.loads(request.form.get('scene_data', '{}'))
                if scene in scene_data:
                    scene_data[scene]['video'] = {'url': video_url, 'path': video_path}
                    data_file = os.path.join(project_path, f"{project_title}.json")
                    if os.path.exists(data_file):
                        with open(data_file, 'r', encoding='utf-8') as f:
                            project_data = json.load(f)
                        project_data['sceneData'] = scene_data
                        with open(data_file, 'w', encoding='utf-8') as f:
                            json.dump(project_data, f, ensure_ascii=False, indent=4)
                return jsonify({'video': {'url': video_url, 'path': video_path}})
            except Exception as e:
                logger.error(f"Error re-searching video: {str(e)}")
                return jsonify({'error': f"Failed to re-search video: {str(e)}"}), 500
        elif action == 'generate_video':
            try:
                scene_data = json.loads(scene_data)
                for scene, data in scene_data.items():
                    if not data.get('video'):
                        return jsonify({'error': f"No video found for scene: {scene}"}), 400
                    if not data.get('audio'):
                        return jsonify({'error': f"No audio found for scene: {scene}"}), 400

                updated_scene_data = {}
                for scene, data in scene_data.items():
                    updated_scene_data[scene] = {
                        'video': data['video']['path'],
                        'audio': data['audio'],
                        'script': data['script']
                    }

                # Define resolution based on video ratio
                resolutions = {
                    '9:16': (1080, 1920),  # Vertical
                    '16:9': (1920, 1080),  # Landscape
                    '1:1': (1080, 1080)    # Square
                }
                resolution = resolutions.get(video_ratio, (1920, 1080))  # Default to 16:9 if not specified
                logger.info(f"Setting video resolution to: {resolution}")

                # Subtitle styling
                subtitle_style = {
                    'color': 'white',
                    'background': 'rgba(0, 0, 0, 0.2)',  # Black with 20% opacity
                    'font_size': 36,
                    'position': 'center-bottom'
                }
                logger.info(f"Applying subtitle styling: {subtitle_style}")

                # Merge videos with specified resolution and subtitle styling
                video_path = os.path.join(EXPORTS_DIR, f"{project_title}.mp4")
                logger.info(f"Starting video merge process for {project_title}")
                merge_videos(story, updated_scene_data, resolution=resolution, subtitle_style=subtitle_style, output_path=video_path)
                logger.info(f"Completed video merge, saved to {video_path}")
                return jsonify({'video_path': f"exports/{project_title}.mp4"})
            except Exception as e:
                logger.error(f"Error generating video: {str(e)}")
                return jsonify({'error': f"Failed to generate video: {str(e)}"}), 500
        elif action == 'export_video':
            try:
                video_path = os.path.join(EXPORTS_DIR, f"{project_title}.mp4")
                if not os.path.exists(video_path):
                    return jsonify({'error': 'Video not found'}), 404
                logger.info(f"Exporting video: {video_path}")
                return send_from_directory(EXPORTS_DIR, f"{project_title}.mp4", as_attachment=True)
            except Exception as e:
                logger.error(f"Error exporting video: {str(e)}")
                return jsonify({'error': f"Failed to export video: {str(e)}"}), 500
        elif action == 'clean_temp_data':
            temp_data_file = os.path.join(TEMP_DIR, f"{project_title}_temp.json")
            if os.path.exists(temp_data_file):
                os.remove(temp_data_file)
                logger.info(f"Cleaned up temporary data file: {temp_data_file}")
            return jsonify({'status': 'success'})

    return render_template('idea_to_video.html', active_page='idea_to_video')

@app.route('/news_content')
def news_content():
    return render_template('placeholder.html', active_page='news_content')

@app.route('/text_to_speech')
def text_to_speech():
    return render_template('placeholder.html', active_page='text_to_speech')

@app.route('/speech_to_text')
def speech_to_text():
    return render_template('placeholder.html', active_page='speech_to_text')

@app.route('/audio_dubbing')
def audio_dubbing():
    return render_template('placeholder.html', active_page='audio_dubbing')

@app.route('/subtitle_generator')
def subtitle_generator():
    return render_template('placeholder.html', active_page='subtitle_generator')

@app.route('/metadata_generator')
def metadata_generator():
    return render_template('placeholder.html', active_page='metadata_generator')

@app.route('/trending_videos')
def trending_videos():
    return render_template('placeholder.html', active_page='trending_videos')

@app.route('/video_download')
def video_download():
    return render_template('placeholder.html', active_page='video_download')

@app.route('/audio_download')
def audio_download():
    return render_template('placeholder.html', active_page='audio_download')

@app.route('/clips_generator')
def clips_generator():
    return render_template('placeholder.html', active_page='clips_generator')

@app.route('/competitor_creator')
def competitor_creator():
    return render_template('placeholder.html', active_page='competitor_creator')

@app.route('/image_gen')
def image_gen():
    return render_template('placeholder.html', active_page='image_gen')

@app.route('/thumbnail_gen')
def thumbnail_gen():
    return render_template('placeholder.html', active_page='thumbnail_gen')

@app.route('/carousel_gen')
def carousel_gen():
    return render_template('placeholder.html', active_page='carousel_gen')

if __name__ == '__main__':
    app.run(debug=True)