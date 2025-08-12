import customtkinter as ctk
from tkinter import filedialog, messagebox
from langdetect import detect, LangDetectException
from deep_translator import GoogleTranslator
import asyncio
import threading
import os
from PyPDF2 import PdfReader
from docx import Document
import socket
import pyttsx3
import edge_tts
import pygame
import re

# Initialize pygame for audio playback
pygame.mixer.init()

# Get supported languages from GoogleTranslator
supported_langs_dict = GoogleTranslator().get_supported_languages(as_dict=True)
LANGUAGE_CODES = supported_langs_dict

# Mapping of language names to Microsoft neural voice codes for Edge TTS
VOICE_MAP = {
    "english": "en-US-AriaNeural",
    "yoruba": "en-NG-AbeoNeural",
    "hausa": "en-NG-EmekaNeural",
    "igbo": "en-NG-AbeoNeural",
    "french": "fr-FR-DeniseNeural",
    "spanish": "es-ES-ElviraNeural",
    "german": "de-DE-KatjaNeural",
    "italian": "it-IT-IsabellaNeural",
    "portuguese": "pt-PT-DuarteNeural",
    "chinese": "zh-CN-XiaoxiaoNeural",
    "japanese": "ja-JP-NanamiNeural",
    "korean": "ko-KR-SunHiNeural",
    "arabic": "ar-SA-ZariyahNeural",
    "russian": "ru-RU-DariyaNeural",
}

# Function to get voice based on language name
def get_voice_for_language(lang_name):
    lang_key = lang_name.strip().lower()
    if lang_key in VOICE_MAP:
        return VOICE_MAP[lang_key]
    if lang_key in LANGUAGE_CODES:
        base_code = LANGUAGE_CODES[lang_key]
        if base_code.startswith("en"):
            return VOICE_MAP["english"]
    return VOICE_MAP["english"]

# Function to check internet connectivity
def check_internet_connection(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except Exception:
        return False

# File reading utilities

def read_txt_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def read_pdf_file(path):
    reader = PdfReader(path)
    text = ''
    for page in reader.pages:
        content = page.extract_text()
        if content:
            text += content + '\n'
    return text.strip()

def read_docx_file(path):
    doc = Document(path)
    return '\n'.join([para.text for para in doc.paragraphs if para.text.strip()])

# Function to extract text based on file extension
def extract_text_from_file(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".txt":
        return read_txt_file(path)
    elif ext == ".pdf":
        return read_pdf_file(path)
    elif ext == ".docx":
        return read_docx_file(path)
    else:
        raise ValueError("Unsupported file format")

# Asynchronous function to convert text to speech using Edge TTS and save as MP3
async def online_tts(text, voice_name, output_file="output.mp3"):
    cleaned_text = re.sub(r'[\[\](){}<>\"\'“”‘’]', '', text)
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    communicate = edge_tts.Communicate(cleaned_text, voice_name)
    await communicate.save(output_file)

# Main application class using customtkinter
class Doc2SpeechApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Doc2Speech Translator")
        self.geometry("950x700")
        self.resizable(False, False)

        # Initialize state variables
        self.selected_file = None
        self.original_text = ""
        self.engine = pyttsx3.init()
        self.is_playing = False

        self.create_widgets()

    # Setup the GUI widgets
    def create_widgets(self):
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        title = ctk.CTkLabel(main_frame, text="Doc2Speech Translator", font=("Arial", 24, "bold"))
        title.pack(pady=(10, 20))

        self.file_button = ctk.CTkButton(main_frame, text="Select File", command=self.select_file)
        self.file_button.pack(pady=5)

        self.text_box = ctk.CTkTextbox(main_frame, width=880, height=100)
        self.text_box.pack(pady=5)

        self.lang_label = ctk.CTkLabel(main_frame, text="Detected Language: ")
        self.lang_label.pack(pady=5)

        self.target_lang_var = ctk.StringVar(value="English")
        self.lang_dropdown = ctk.CTkOptionMenu(main_frame, values=sorted(list(LANGUAGE_CODES.keys()), key=str.lower), variable=self.target_lang_var)
        self.lang_dropdown.pack(pady=5)

        self.translate_button = ctk.CTkButton(main_frame, text="Translate", command=self.translate_text)
        self.translate_button.pack(pady=10)

        self.translated_text_box = ctk.CTkTextbox(main_frame, width=880, height=100)
        self.translated_text_box.pack(pady=5)

        self.tts_mode_label = ctk.CTkLabel(main_frame, text="Choose TTS Mode:", font=("Arial", 16))
        self.tts_mode_label.pack(pady=(20, 5))

        self.tts_mode_var = ctk.StringVar(value="online")
        tts_modes_frame = ctk.CTkFrame(main_frame)
        tts_modes_frame.pack(pady=5)

        self.radio_online = ctk.CTkRadioButton(tts_modes_frame, text="Online TTS (Better voice, requires Internet)", variable=self.tts_mode_var, value="online")
        self.radio_online.pack(side="left", padx=10)

        self.radio_offline = ctk.CTkRadioButton(tts_modes_frame, text="Offline TTS (Works offline, less natural)", variable=self.tts_mode_var, value="offline")
        self.radio_offline.pack(side="left", padx=10)

        speak_frame = ctk.CTkFrame(main_frame)
        speak_frame.pack(pady=20)
        self.speak_button = ctk.CTkButton(speak_frame, text="Speak Translated Text", command=self.speak_text)
        self.speak_button.pack(side="left", padx=10)
        self.stop_button = ctk.CTkButton(speak_frame, text="Stop Speech", command=self.stop_speech)
        self.stop_button.pack(side="left", padx=10)

        self.status_label = ctk.CTkLabel(self, text="Status: Ready", anchor="w")
        self.status_label.pack(side="bottom", fill="x", pady=5, padx=10)

    # Update the status bar
    def update_status(self, message):
        self.status_label.configure(text=f"Status: {message}")

    # Handle file selection and language detection
    def select_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Documents", "*.txt *.pdf *.docx")])
        if file_path:
            try:
                text = extract_text_from_file(file_path)
                if not text.strip():
                    raise ValueError("File appears to be empty or unreadable.")
                self.selected_file = file_path
                self.original_text = text
                self.text_box.delete("0.0", "end")
                self.text_box.insert("0.0", text)

                try:
                    detected_lang = detect(text)
                except LangDetectException:
                    detected_lang = "Unknown"

                self.lang_label.configure(text=f"Detected Language: {detected_lang}")
                self.update_status("File loaded and language detected")

            except Exception as e:
                messagebox.showerror("Error", f"Failed to read file: {str(e)}")
                self.update_status("Error reading file")

    # Perform translation using GoogleTranslator
    def translate_text(self):
        target_lang = self.target_lang_var.get()
        target_code = LANGUAGE_CODES.get(target_lang.lower(), "en")
        original = self.text_box.get("0.0", "end").strip()

        if not original:
            messagebox.showwarning("Warning", "No text to translate")
            return

        cleaned_text = re.sub(r'\s+', ' ', original)
        if len(cleaned_text) > 5000:
            messagebox.showwarning("Warning", "Text too long to translate. Try shortening it.")
            return

        try:
            if not check_internet_connection():
                raise ConnectionError("No internet connection for translation")

            translated = GoogleTranslator(source='auto', target=target_code).translate(cleaned_text)
            self.translated_text_box.delete("0.0", "end")
            self.translated_text_box.insert("0.0", translated)
            self.update_status("Translation successful")

        except Exception as e:
            self.update_status("Translation failed")
            messagebox.showerror("Translation Error", str(e))

    # Text-to-speech handler
    def speak_text(self):
        text_to_speak = self.translated_text_box.get("0.0", "end").strip()
        if not text_to_speak:
            messagebox.showwarning("Warning", "No translated text to speak")
            return

        tts_mode = self.tts_mode_var.get()
        target_lang = self.target_lang_var.get()
        voice_name = get_voice_for_language(target_lang)

        if tts_mode == "online":
            def run_online():
                try:
                    if not check_internet_connection():
                        self.run_fallback_tts(text_to_speak)
                        return
                    output_path = "output.mp3"
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(online_tts(text_to_speak, voice_name, output_path))
                    loop.close()
                    pygame.mixer.music.load(output_path)
                    pygame.mixer.music.play()
                    self.is_playing = True
                    self.update_status("Speaking with online voice")
                except Exception as e:
                    print(f"Online TTS failed: {e}")
                    self.run_fallback_tts(text_to_speak)
                    self.update_status("Online TTS failed, fallback triggered")

            threading.Thread(target=run_online).start()
        else:
            threading.Thread(target=lambda: self.run_fallback_tts(text_to_speak)).start()
            self.update_status("Speaking with offline voice")

    # Offline fallback using pyttsx3
    def run_fallback_tts(self, text):
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            messagebox.showerror("Fallback TTS Error", f"Offline TTS failed: {str(e)}")

    # Stop audio playback
    def stop_speech(self):
        if self.is_playing:
            pygame.mixer.music.stop()
            self.is_playing = False
        if hasattr(self, 'engine'):
            self.engine.stop()
        self.update_status("Speech stopped")

# Run the application
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = Doc2SpeechApp()
    app.mainloop()
