from moviepy.editor import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips
import logging
import re

logger = logging.getLogger(__name__)

def merge_videos(story, scene_data, resolution=(1920, 1080), subtitle_style=None, output_path="output.mp4"):
    """
    Merge video clips with audio and subtitles, and save the final video.
    
    Args:
        story (str): The full story text with scenes and scripts.
        scene_data (dict): Dictionary mapping scenes to their video paths, audio paths, and scripts.
        resolution (tuple): Desired resolution of the output video (width, height).
        subtitle_style (dict): Styling for subtitles (color, background, font_size, position).
        output_path (str): Path where the final video will be saved.
    
    Returns:
        str: Path to the generated video.
    """
    try:
        # Default subtitle style if none provided
        if subtitle_style is None:
            subtitle_style = {
                'color': 'white',
                'background': 'rgba(0, 0, 0, 0.2)',
                'font_size': 36,
                'position': 'center-bottom'
            }

        # Parse scenes from the story
        scenes = []
        current_scene = None
        current_script = None
        for line in story.split('\n'):
            if line.startswith('Scene:'):
                if current_scene and current_script:
                    scenes.append((current_scene, current_script))
                current_scene = line.replace('Scene:', '').strip()
            elif line.startswith('Script:'):
                current_script = line.replace('Script:', '').strip()

        # Add the last scene if it exists
        if current_scene and current_script:
            scenes.append((current_scene, current_script))

        if not scenes:
            raise ValueError("No scenes found in the story")

        # Process each scene
        final_clips = []
        for scene_name, script in scenes:
            if scene_name not in scene_data:
                logger.warning(f"Scene {scene_name} not found in scene_data, skipping")
                continue

            data = scene_data[scene_name]
            video_path = data.get('video')
            audio_path = data.get('audio')
            script_text = data.get('script')

            if not video_path or not audio_path:
                logger.warning(f"Missing video or audio for scene {scene_name}, skipping")
                continue

            # Load and resize video clip to the specified resolution
            video_clip = VideoFileClip(video_path)
            video_clip = video_clip.resize(resolution)

            # Load audio clip
            audio_clip = AudioFileClip(audio_path)

            # Trim video to match audio duration (or vice versa)
            duration = min(video_clip.duration, audio_clip.duration)
            video_clip = video_clip.subclip(0, duration)
            audio_clip = audio_clip.subclip(0, duration)

            # Set audio to the video
            video_clip = video_clip.set_audio(audio_clip)

            # Add subtitles
            if script_text and subtitle_style:
                subtitle_clip = TextClip(
                    script_text,
                    fontsize=subtitle_style.get('font_size', 36),
                    color=subtitle_style.get('color', 'white'),
                    bg_color=subtitle_style.get('background', 'rgba(0, 0, 0, 0.2)'),
                    font='Arial',
                    method='caption',
                    size=(resolution[0] * 0.8, None)
                )
                subtitle_clip = subtitle_clip.set_duration(duration)

                position = subtitle_style.get('position', 'center-bottom')
                if position == 'center-bottom':
                    subtitle_clip = subtitle_clip.set_position(('center', resolution[1] - 100))
                else:
                    subtitle_clip = subtitle_clip.set_position('center')

                video_clip = CompositeVideoClip([video_clip, subtitle_clip])

            final_clips.append(video_clip)
            logger.info(f"Processed scene {scene_name} with resolution {resolution} and duration {duration}s")

        if not final_clips:
            raise ValueError("No valid clips to merge")

        # Concatenate all clips with the specified resolution
        final_video = concatenate_videoclips(final_clips, method="compose")

        # Write the final video to the output path
        final_video.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            fps=24,
            preset='medium',
            threads=4
        )

        # Close all clips to free memory
        for clip in final_clips:
            clip.close()
        final_video.close()

        logger.info(f"Final video saved to {output_path} with resolution {resolution}")
        return output_path

    except Exception as e:
        logger.error(f"Error in merge_videos: {str(e)}")
        raise