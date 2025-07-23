# tools/translator_tool.py

import streamlit as st
import google.generativeai as genai
from google.cloud import speech
from google.api_core.client_options import ClientOptions
from streamlit_mic_recorder import mic_recorder

# (補助関数 transcribe_audio, translate_text_with_gemini は変更なし)
def transcribe_audio(audio_bytes, api_key):
    if not audio_bytes or not api_key: return None
    try:
        client_options = ClientOptions(api_key=api_key)
        client = speech.SpeechClient(client_options=client_options)
        audio = speech.RecognitionAudio(content=audio_bytes)
        config = speech.RecognitionConfig(language_code="ja-JP")
        response = client.recognize(config=config, audio=audio)
        if response.results: return response.results[0].alternatives[0].transcript
    except Exception as e:
        st.error(f"音声認識エラー: APIキーが正しいかご確認ください。詳細: {e}")
    return None

def translate_text_with_gemini(text_to_translate, api_key):
    if not text_to_translate or not api_key: return None
    try:
        genai.configure(api_key=api_key)
        system_prompt = """
        あなたは、言語の壁を乗り越える手助けをする、非常に優秀な翻訳アシスタントです。
        ユーザーから渡された日本語のテキストを、海外の親しい友人との会話で使われるような、自然で、カジュアルでありながら礼儀正しく、そしてフレンドリーな英語に翻訳してください。
        - 非常に硬い表現や、ビジネス文書のような翻訳は避けてください。
        - 翻訳後の英語テキストのみを回答してください。他の言葉は一切含めないでください。
        """
        model = genai.GenerativeModel('gemini-1.5-flash-latest', system_instruction=system_prompt)
        response = model.generate_content(text_to_translate)
        return response.text.strip()
    except Exception as e:
        st.error(f"翻訳エラー: AIとの通信に失敗しました。詳細: {e}")
    return None


# ===============================================================
# 専門家のメインの仕事 (司令塔 app.py から呼び出される)
# ===============================================================
def show_tool(gemini_api_key, speech_api_key):
    st.header("🤝 フレンドリー翻訳ツール", divider='rainbow')

    if "translator_results" not in st.session_state:
        st.session_state.translator_results = []
    if "translator_last_mic_id" not in st.session_state:
        st.session_state.translator_last_mic_id = None
    if "translator_last_text" not in st.session_state:
        st.session_state.translator_last_text = ""

    st.info("マイクで日本語を話すか、テキストボックスに入力してください。自然な英語に翻訳します。")
    col1, col2 = st.columns([1, 2])
    with col1:
        audio_info = mic_recorder(start_prompt="🎤 話し始める", stop_prompt="⏹️ 翻訳する", key='translator_mic')
    with col2:
        text_prompt = st.text_input("または、ここに日本語を入力してEnterキーを押してください...", key="translator_text")

    if st.session_state.translator_results:
        st.write("---")
        for i, result in enumerate(st.session_state.translator_results):
            with st.container(border=True):
                st.caption(f"翻訳履歴 No.{len(st.session_state.translator_results) - i}")
                st.markdown(f"**🇯🇵 あなたの入力:**\n> {result['original']}")
                st.markdown(f"**🇺🇸 AIの翻訳:**\n> {result['translated']}")
        if st.button("翻訳履歴をクリア", key="clear_translator_history"):
            st.session_state.translator_results = []
            st.session_state.translator_last_text = ""
            st.rerun()

    japanese_text = None
    is_new_input = False

    if audio_info and audio_info['id'] != st.session_state.translator_last_mic_id:
        st.session_state.translator_last_mic_id = audio_info['id']
        if not speech_api_key: st.error("サイドバーでSpeech-to-Text APIキーを設定してください。")
        else:
            with st.spinner("音声を日本語に変換中..."):
                japanese_text = transcribe_audio(audio_info['bytes'], speech_api_key)
                if japanese_text: is_new_input = True

    elif text_prompt and text_prompt != st.session_state.translator_last_text:
        japanese_text = text_prompt
        is_new_input = True

    if is_new_input and japanese_text:
        if not gemini_api_key: st.error("サイドバーでGemini APIキーを設定してください。")
        else:
            with st.spinner("AIが最適な英語を考えています..."):
                translated_text = translate_text_with_gemini(japanese_text, gemini_api_key)
            if translated_text:
                st.session_state.translator_results.insert(0, {"original": japanese_text, "translated": translated_text})
                st.session_state.translator_last_text = japanese_text
                
                # ★★★ Streamlitの絶対的なルールを尊重し、問題の行を削除 ★★★
                # st.session_state.translator_text = ""  <-- この行がエラーの原因でした
                
                st.rerun()
            else:
                st.warning("翻訳に失敗しました。もう一度お試しください。")
