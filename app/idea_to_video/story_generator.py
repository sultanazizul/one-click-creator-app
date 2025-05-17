import openai
import logging

logger = logging.getLogger(__name__)

openai.api_key = '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'

def generate_story(idea, theme, duration):
    logger.info(f"Generating story with idea: {idea}, theme: {theme}, duration: {duration}")
    
    # Map duration to number of scenes
    duration_map = {
        'short': (2, 3),
        'medium': (4, 5),
        'long': (6, 8)
    }
    min_scenes, max_scenes = duration_map.get(duration, (2, 3))
    
    # Create a clear and strict prompt
    prompt = f"""
    You are a creative writer tasked with writing a {theme} story based on the idea: "{idea}".
    Write a narrative story in the following exact format:
    Title: [Your story title here]
    Scene: [Scene title here]
    Script: [Scene script here]
    Scene: [Another scene title here]
    Script: [Another scene script here]
    ...
    - Include between {min_scenes} and {max_scenes} scenes.
    - Use only 'Title:', 'Scene:', and 'Script:' as labels.
    - Each script should be a short paragraph (1-2 sentences) suitable for text-to-speech.
    - Do not include any instructions, comments, code, or extra text outside the specified format.
    - Ensure the story is a narrative, not a piece of code or technical content.
    Example:
    Title: A Day with a Hero
    Scene: The Meeting
    Script: I nervously waited at the stadium, and then Neymar walked in, his smile lighting up the field.
    Scene: The First Kick
    Script: We started playing, and I was amazed by Neymar's skill as he effortlessly dribbled past me.
    """
    
    try:
        response = openai.Completion.create(
            engine="gpt-4.1-nano",  # Use the configured engine
            prompt=prompt,
            max_tokens=1000,
            temperature=0.7
        )
        
        story_text = response.choices[0].text.strip()
        logger.info(f"Raw API response: {story_text}")
        
        # Split into lines and filter to keep only valid story lines
        lines = [line.strip() for line in story_text.split('\n') if line.strip()]
        cleaned_lines = []
        capturing = False
        
        for line in lines:
            if line.startswith("Title:"):
                capturing = True
            if capturing and (line.startswith("Title:") or line.startswith("Scene:") or line.startswith("Script:")):
                cleaned_lines.append(line)
        
        cleaned_story = '\n'.join(cleaned_lines)
        
        if not cleaned_story:
            logger.warning("Valid story content not found, using fallback")
            return f"Title: [Story Title]\nScene: [Scene Title]\nScript: [Scene Script]\nScene: [Scene Title]\nScript: [Scene Script]"
        
        logger.info(f"Cleaned story: {cleaned_story}")
        return cleaned_story
    except Exception as e:
        logger.error(f"Error generating story: {str(e)}")
        raise