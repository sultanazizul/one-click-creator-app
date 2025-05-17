import logging
from gtts import gTTS

logger = logging.getLogger(__name__)

def generate_voice_over(script, output_path):
    """
    Generate voice-over audio from script and save to output_path.
    """
    try:
        tts = gTTS(text=script, lang='en')
        tts.save(output_path)
        logger.info(f"Generated voice-over at: {output_path}")
    except Exception as e:
        logger.error(f"Error generating voice-over: {str(e)}")
        raise