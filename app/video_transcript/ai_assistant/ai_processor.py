import os
import google.generativeai as genai
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

# Configure Gemini API dengan kunci API langsung
# PERINGATAN: Menyematkan kunci API langsung dalam kode TIDAK disarankan untuk produksi.
# Gunakan variabel lingkungan atau layanan manajemen kunci yang aman untuk produksi.
genai.configure(api_key="AIzaSyCJta-o3NHq2FOKJm2F92TcRrlrUqea0Lc")

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
        # Mengganti model ke gemini-2.5-flash-lite-preview-06-17
        model = genai.GenerativeModel('gemini-2.5-flash-lite-preview-06-17')
        response = model.generate_content(prompt)
        summary = response.text.strip()
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
        # Mengganti model ke gemini-2.5-flash-lite-preview-06-17
        model = genai.GenerativeModel('gemini-2.5-flash-lite-preview-06-17')
        response = model.generate_content(prompt)
        translated = response.text.strip()
        logger.info(f"Text translated to {target_lang}: {translated}")
        return translated
    except Exception as e:
        logger.error(f"Error translating text: {str(e)}")
        raise