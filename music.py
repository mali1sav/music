import os
import requests
import yt_dlp
import streamlit as st
import base64
import hashlib
import tempfile
from dotenv import load_dotenv
import json
from rich.console import Console

# Load environment variables from .env file
load_dotenv()

# Configuration
API_KEY = os.getenv('MINIMAX_API_KEY')
UPLOAD_API_URL = 'https://api.minimax.chat/v1/music_upload'
MUSIC_GENERATION_API_URL = 'https://api.minimax.chat/v1/music_generation'

# Initialize a Rich console for prettier output
console = Console()

# Helper Functions
@st.cache_data
def download_audio_from_youtube(url, purpose):
    """
    Downloads audio from YouTube and converts it to MP3 format.
    """
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': f'{purpose}_%(title).50s.%(ext)s',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
        
        # Handle long filenames by hashing
        if len(filename) > 200:
            hash_object = hashlib.md5(filename.encode())
            new_filename = f"{purpose}_{hash_object.hexdigest()}.mp3"
            os.rename(filename, new_filename)
            filename = new_filename
        
        return filename
    except Exception as e:
        st.error(f"Error downloading audio from YouTube: {e}")
        return None

class MusicProcessor:
    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {'Authorization': f'Bearer {self.api_key}'}
    
    def upload_audio(self, file_path, purpose):
        """
        Uploads an audio file to the Upload API.
        """
        try:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                data = {'purpose': purpose}
                response = requests.post(UPLOAD_API_URL, headers=self.headers, data=data, files=files, timeout=30)
                response.raise_for_status()
                result = response.json()
                return result
        except requests.exceptions.RequestException as e:
            st.error(f"Error uploading {purpose} audio file: {e}")
        return None
    
    def generate_music(self, refer_voice, refer_instrumental, lyrics, model='music-01', stream=False, audio_setting=None):
        """
        Generates AI music based on provided voice and instrumental references, and lyrics.
        """
        try:
            if not lyrics:
                st.error("Lyrics are required for music generation.")
                return None

            if audio_setting is None:
                audio_setting = {
                    "sample_rate": 44100,
                    "bitrate": 256000,
                    "format": "mp3"
                }
            
            payload = {
                'refer_voice': refer_voice,
                'refer_instrumental': refer_instrumental,
                'lyrics': lyrics,
                'model': model,
                'stream': stream,
                'audio_setting': audio_setting
            }
            
            response = requests.post(MUSIC_GENERATION_API_URL, headers=self.headers, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            
            if 'data' in result and 'audio' in result['data'] and result['data']['audio']:
                audio_data = result['data']['audio']
                try:
                    audio_bytes = bytes.fromhex(audio_data)
                    return audio_bytes
                except Exception as e:
                    st.error(f"Error converting audio data: {e}")
            else:
                st.error(f"Audio data not found in API response")
        except requests.exceptions.RequestException as e:
            st.error(f"Error generating music: {e}")
        return None

def format_lyrics_for_minimax(lyrics):
    """
    Formats the lyrics according to Minimax Music Creation API requirements.
    """
    lines = lyrics.strip().split('\n')
    formatted = "##" + "\n".join(line.strip() for line in lines if line.strip()) + "##"
    return formatted

def get_binary_file_downloader_html(bin_file, file_label='File'):
    """
    Generates a download link for a binary file.
    """
    with open(bin_file, 'rb') as f:
        data = f.read()
    bin_str = base64.b64encode(data).decode()
    href = f'<a href="data:audio/mp3;base64,{bin_str}" download="{os.path.basename(bin_file)}">Download {file_label}</a>'
    return href

# Streamlit App
def main():
    st.title("AI Music Cover Creator")
    
    music_processor = MusicProcessor(API_KEY)
    
    # Initialize session state
    if 'step' not in st.session_state:
        st.session_state.step = 1
    if 'voice_id' not in st.session_state:
        st.session_state.voice_id = None
    if 'instrumental_id' not in st.session_state:
        st.session_state.instrumental_id = None
    if 'lyrics' not in st.session_state:
        st.session_state.lyrics = ""
    
    # Step 1: Vocal Extraction or Manual ID Input
    if st.session_state.step == 1:
        st.header("Step 1: Vocal Extraction or Manual ID Input")
        
        use_manual_ids = st.checkbox("Use manual IDs")
        
        if use_manual_ids:
            voice_id = st.text_input("Enter Voice ID", "vocal-2024101206134524-2988")
            instrumental_id = st.text_input("Enter Instrumental ID", "instrumental-2024101206134524-2973")
            
            if st.button("Confirm IDs"):
                st.session_state.voice_id = voice_id
                st.session_state.instrumental_id = instrumental_id
                st.success("IDs confirmed successfully!")
                st.session_state.step = 3  # Skip to step 3
        else:
            youtube_url = st.text_input("Enter YouTube URL for Original Vocals (URL 1)", "https://www.youtube.com/watch?v=xxxxxx")
            if st.button("Extract Vocals"):
                with st.spinner("Processing Vocal Extraction..."):
                    voice_file = download_audio_from_youtube(youtube_url, "voice")
                    if voice_file:
                        voice_upload = music_processor.upload_audio(voice_file, "voice")
                        if voice_upload:
                            voice_id = voice_upload.get('voice_id')
                            st.session_state.voice_id = voice_id
                            st.success(f"Obtained voice_id: {voice_id}")
                            st.session_state.step = 2
        
        if st.button("Next Step"):
            st.session_state.step += 1
    
    # Step 2: Instrumental Upload
    elif st.session_state.step == 2:
        st.header("Step 2: Instrumental Upload")
        
        youtube_url = st.text_input("Enter YouTube URL for Instrumental (URL 2)", "https://www.youtube.com/watch?v=xxxxxxx")
        if st.button("Upload Instrumental"):
            with st.spinner("Uploading Instrumental..."):
                instrumental_file = download_audio_from_youtube(youtube_url, "instrumental")
                if instrumental_file:
                    song_upload = music_processor.upload_audio(instrumental_file, "song")
                    if song_upload:
                        instrumental_id = song_upload.get('instrumental_id')
                        st.session_state.instrumental_id = instrumental_id
                        st.success(f"Obtained instrumental_id: {instrumental_id}")
                    else:
                        st.error("Failed to upload instrumental as song.")
                else:
                    st.error("Failed to download instrumental audio.")
        
        if st.button("Next Step"):
            st.session_state.step += 1
    
    # Step 3: Music Generation
    elif st.session_state.step == 3:
        st.header("Step 3: Music Generation")
        
        st.subheader("Lyrics")
        default_lyrics = """Walking down the line
I bumped right into you 
Could feel it from a mile 
And I know you feel it too"""
        lyrics = st.text_area("Enter Lyrics", 
                              value=st.session_state.lyrics if st.session_state.lyrics else default_lyrics, 
                              height=200)
        mixer_volume = st.slider("Mixer Volume", min_value=0, max_value=100, value=75)
        mixer_balance = st.selectbox("Mixer Balance", ("left", "center", "right"))
        output_format = st.selectbox("Output Format", ("mp3", "wav"))
        if st.button("Generate AI Cover"):
            with st.spinner("Generating AI Cover..."):
                formatted_lyrics = format_lyrics_for_minimax(lyrics)
                audio_bytes = music_processor.generate_music(
                    refer_voice=st.session_state.voice_id,
                    refer_instrumental=st.session_state.instrumental_id,
                    lyrics=formatted_lyrics,
                    model='music-01',
                    stream=False
                )
                
                if audio_bytes:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{output_format}') as tmp:
                        tmp.write(audio_bytes)
                        tmp_path = tmp.name
                    
                    st.audio(tmp_path, format=f'audio/{output_format}')
                    st.markdown(get_binary_file_downloader_html(tmp_path, 'AI Cover'), unsafe_allow_html=True)
                    st.success("AI Cover generated successfully!")
                else:
                    st.error("Failed to generate AI Cover.")

if __name__ == "__main__":
    main()