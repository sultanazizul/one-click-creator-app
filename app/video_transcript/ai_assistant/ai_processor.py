import os
from openai import OpenAI
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_summary(transcript):
    try:
        prompt = f"""
        Generate a summary and key points from the following video (transcript). Include timestamps where possible.
        Transcript: {transcript}

        Return in this format:
        "Summary:
        [Summary text here]

        Key Points:
        - (timestamp): [Key point text here]
        - (timestamp): [Key point text here]"
        """
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        summary = response.choices[0].message.content.strip()
        logger.info(f"Summary generated: {summary}")
        return summary
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        raise

def translate_text(text, target_lang):
    try:
        language_names = {
            'en': 'English',
            'id': 'Indonesian',
            'es': 'Spanish',
            'fr': 'French'
        }
        prompt = f"Translate the following text to {language_names[target_lang]}:\n\n{text}"
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000
        )
        translated = response.choices[0].message.content.strip()
        logger.info(f"Text translated to {target_lang}: {translated}")
        return translated
    except Exception as e:
        logger.error(f"Error translating text: {str(e)}")
        raise