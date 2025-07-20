import streamlit as st
from google.cloud import speech
from google.api_core.client_options import ClientOptions

# ===============================================================
# 補助関数（calendar_tool.pyから「魂のコピー」をした、完全に同一の関数）
# 原則④に従い、既存の動作するコードを尊重し、安全のために複製する
# ===============================================================

def transcribe_audio(audio_bytes, api_key):
    """Speech-to-Text APIを使用して音声データを文字に変換する関数"""
    if not audio_bytes or not api_key:
        return None
    try:
        client_options = ClientOptions(api_key=api_key)
        client = speech.SpeechClient(client_options=client_options)
        audio = speech.RecognitionAudio(content=audio_bytes)
        config = speech.RecognitionConfig(language_code="ja-JP")
        response = client.recognize(config=config, audio=audio)
        if response.results:
            return response.results[0].alternatives[0].transcript
    except Exception as e:
        st.error(f"音声認識中にエラーが発生しました。APIキーが正しいか、有効期限が切れていないかをご確認ください。詳細: {e}")
    return None

# ===============================================================
# 専門家のメインの仕事 (司令塔 app.py から呼び出される)
# ===============================================================

def show_tool(speech_api_key):
    """議事録作成ツールのUIと機能をすべてここに集約"""
    st.header("📝 音声ファイルから議事録を作成")
    st.info("会議などを録音した音声ファイルをアップロードすると、AIが文字起こしを行い、テキストファイルとしてダウンロードできます。")

    if "transcript_text" not in st.session_state:
        st.session_state.transcript_text = None

    議事録_file = st.file_uploader("議事録を作成したい音声ファイルをアップロードしてください:", type=['wav', 'mp3', 'm4a', 'flac'], key="transcript_uploader")
    
    if st.button("この音声ファイルから議事録を作成する"):
        if not speech_api_key:
            st.error("サイドバーでSpeech-to-Text APIキーを設定してください。")
        elif 議事録_file is None:
            st.warning("音声ファイルをアップロードしてください。")
        else:
            with st.spinner("音声ファイルを文字に変換しています。長い音声の場合、数分かかることがあります..."):
                audio_bytes = 議事録_file.getvalue()
                transcript = transcribe_audio(audio_bytes, speech_api_key)
                if transcript:
                    st.session_state.transcript_text = transcript
                else:
                    # transcribe_audio内でエラー表示されるため、ここでは警告を省略しても良い
                    pass

    if st.session_state.transcript_text:
        st.success("文字起こしが完了しました！")
        st.text_area("文字起こし結果", st.session_state.transcript_text, height=300)
        st.download_button(
            label="議事録をテキストファイルでダウンロード (.txt)",
            data=st.session_state.transcript_text.encode('utf_8'),
            file_name="transcript.txt",
            mime="text/plain"
        )
