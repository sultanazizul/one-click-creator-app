from flask import Flask, render_template, request, jsonify, send_file
from app.idea_to_video.story_generator import generate_story
from app.idea_to_video.voice_over import generate_voice_over
from app.idea_to_video.video_matching import find_videos, re_search_video
from app.idea_to_video.video_merging import merge_videos
from moviepy.config import change_settings
import logging
import json
import os
import shutil
import urllib.parse
import requests
import whisper
import yt_dlp
import tempfile

# Configure ImageMagick binary path for MoviePy
change_settings({"IMAGEMAGICK_BINARY": "/usr/local/bin/magick"})

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

# Directory for temporary files and exports
TEMP_DIR = "temp"
EXPORTS_DIR = "exports"
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(EXPORTS_DIR, exist_ok=True)

def create_project_dirs(title):
    """Create project directories for videos and audio."""
    project_path = os.path.join('projects', title)
    os.makedirs(os.path.join(project_path, 'videos'), exist_ok=True)
    os.makedirs(os.path.join(project_path, 'audio'), exist_ok=True)
    logger.info(f"Created project directories for: {title}")
    return project_path

def download_video(url, scene, project_path):
    """Download a video from a URL and save it in the project's videos folder."""
    try:
        parsed_url = urllib.parse.urlparse(url)
        if not all([parsed_url.scheme, parsed_url.netloc]):
            raise ValueError(f"Invalid video URL: {url}")

        video_filename = os.path.join(project_path, 'videos', f"{scene.replace(' ', '_')}.mp4")
        headers = {"Authorization": f"Bearer {PEXELS_API_KEY}"}
        response = requests.get(url, stream=True, timeout=10, headers=headers)
        response.raise_for_status()

        with open(video_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info(f"Downloaded video for scene {scene}: {video_filename}")
        return video_filename
    except Exception as e:
        logger.error(f"Error downloading video for scene {scene} from {url}: {str(e)}")
        raise

def download_media_from_url(url):
    """Download video/audio from a URL using yt-dlp."""
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(TEMP_DIR, 'media.%(ext)s'),
            'merge_output_format': 'mp4',
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        # Find the downloaded file
        for file in os.listdir(TEMP_DIR):
            if file.startswith("media."):
                return os.path.join(TEMP_DIR, file)
        raise Exception("No media file found after download")
    except Exception as e:
        logger.error(f"Error downloading media from {url}: {str(e)}")
        raise

def transcribe_media(file_path):
    """Transcribe audio or video file using Whisper."""
    try:
        model = whisper.load_model("base")  # Use 'base' model for faster processing
        result = model.transcribe(file_path)
        return result["text"]
    except Exception as e:
        logger.error(f"Error transcribing media: {str(e)}")
        raise

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
    file_path = os.path.join('projects', filepath)
    if os.path.exists(file_path):
        return send_file(file_path)
    else:
        return jsonify({'error': 'File not found'}), 404

@app.route('/exports/<path:filepath>')
def serve_exported_file(filepath):
    """Serve files from the exports directory."""
    file_path = os.path.join(EXPORTS_DIR, filepath)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name=os.path.basename(file_path))
    else:
        return jsonify({'error': 'File not found'}), 404

@app.route('/get_projects')
def get_projects():
    """Return a list of existing project directories."""
    projects = [d for d in os.listdir('projects') if os.path.isdir(os.path.join('projects', d))]
    logger.info(f"Retrieved projects: {projects}")
    return jsonify({'projects': projects})

@app.route('/get_project_data')
def get_project_data():
    """Return the story and scene data for a given project."""
    project_title = request.args.get('project_title')
    project_path = os.path.join('projects', project_title)
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

@app.route('/transcript', methods=['GET', 'POST'])
def transcript():
    if request.method == 'POST':
        action = request.form.get('action')
        logger.info(f"Transcript action: {action}")

        if action == 'generate_transcript':
            try:
                input_type = request.form.get('input_type')
                transcript = None
                temp_file = None

                if input_type == 'url':
                    url = request.form.get('url')
                    if not url:
                        return jsonify({'error': 'URL is required'}), 400
                    logger.info(f"Downloading media from URL: {url}")
                    temp_file = download_media_from_url(url)
                elif input_type == 'file':
                    if 'file' not in request.files:
                        return jsonify({'error': 'No file uploaded'}), 400
                    file = request.files['file']
                    if file.filename == '':
                        return jsonify({'error': 'No file selected'}), 400
                    temp_file = os.path.join(TEMP_DIR, file.filename)
                    file.save(temp_file)
                    logger.info(f"Saved uploaded file: {temp_file}")
                else:
                    return jsonify({'error': 'Invalid input type'}), 400

                # Transcribe the media
                logger.info(f"Transcribing file: {temp_file}")
                transcript = transcribe_media(temp_file)

                # Clean up temporary file
                if temp_file and os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.info(f"Deleted temporary file: {temp_file}")

                return jsonify({'transcript': transcript})
            except Exception as e:
                logger.error(f"Error generating transcript: {str(e)}")
                return jsonify({'error': f"Failed to generate transcript: {str(e)}"}), 500

        elif action == 'download_transcript':
            try:
                transcript = request.form.get('transcript')
                if not transcript:
                    return jsonify({'error': 'No transcript provided'}), 400
                # Save transcript to a temporary file
                temp_file = os.path.join(TEMP_DIR, 'transcript.txt')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(transcript)
                return send_file(temp_file, as_attachment=True, download_name='transcript.txt')
            except Exception as e:
                logger.error(f"Error downloading transcript: {str(e)}")
                return jsonify({'error': f"Failed to download transcript: {str(e)}"}), 500

    return render_template('transcript.html', active_page='transcript_download')

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

from flask import send_from_directory  # Add this import at the top

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