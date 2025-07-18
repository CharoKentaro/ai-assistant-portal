import streamlit as st
import google.generativeai as genai
from google.cloud import speech
from google.api_core.client_options import ClientOptions
import json
from datetime import datetime
import urllib.parse
import pytz
import pandas as pd

# --- アプリの基本設定 ---
st.set_page_config(page_title="AIアシスタント・ポータル", page_icon="🤖", layout="wide")

# --- サイドバー ---
with st.sidebar:
    st.title("🤖 AIアシスタント・ポータル")
    
    # ★★★ 新しいツール「AI乗り換え案内」を追加 ★★★
    tool_choice = st.radio(
        "使いたいツールを選んでください:",
        ("📅 あなただけのAI秘書", "💹 価格リサーチ", "📝 議事録作成", "🚇 AI乗り換え案内")
    )
    st.divider()
    
    st.header("⚙️ APIキー設定")
    gemini_api_key = st.text_input("1. Gemini APIキー", type="password", help="Google AI Studioで取得したキー")
    speech_api_key = st.text_input("2. Speech-to-Text APIキー", type="password", help="Google Cloud Platformで取得したキー")
    st.divider()
    st.markdown("""
    <div style="font-size: 0.9em;">
    <a href="https://aistudio.google.com/app/apikey" target="_blank">1. Gemini APIキーの取得</a><br>
    <a href="https://console.cloud.google.com/apis/credentials" target="_blank">2. Speech-to-Text APIキーの取得</a>
    </div>
    """, unsafe_allow_html=True)

# --- バックエンド関数 (変更なし) ---
def transcribe_audio(audio_bytes, api_key):
    if not audio_bytes or not api_key: return None
    client_options = ClientOptions(api_key=api_key); client = speech.SpeechClient(client_options=client_options)
    audio = speech.RecognitionAudio(content=audio_bytes); config = speech.RecognitionConfig(language_code="ja-JP", audio_channel_count=1)
    try:
        response = client.recognize(config=config, audio=audio)
        if response.results: return response.results[0].alternatives[0].transcript
    except Exception as e:
        st.error(f"音声認識エラー: {e}")
    return None

def create_google_calendar_url(details):
    try:
        jst = pytz.timezone('Asia/Tokyo'); start_time_naive = datetime.fromisoformat(details['start_time']); end_time_naive = datetime.fromisoformat(details['end_time']); start_time_jst = jst.localize(start_time_naive); end_time_jst = jst.localize(end_time_naive); start_time_utc = start_time_jst.astimezone(pytz.utc); end_time_utc = end_time_jst.astimezone(pytz.utc); start_time_str = start_time_utc.strftime('%Y%m%dT%H%M%SZ'); end_time_str = end_time_utc.strftime('%Y%m%dT%H%M%SZ'); dates = f"{start_time_str}/{end_time_str}"
    except (ValueError, KeyError): dates = ""
    base_url = "https://www.google.com/calendar/render?action=TEMPLATE"; params = { "text": details.get('title', ''), "dates": dates, "location": details.get('location', ''), "details": details.get('details', '') }; encoded_params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote); return f"{base_url}&{encoded_params}"

# --- メイン画面の描画 ---
if tool_choice == "📅 あなただけのAI秘書":
    # (既存の機能は変更なし)
    pass
elif tool_choice == "💹 価格リサーチ":
    # (既存の機能は変更なし)
    pass
elif tool_choice == "📝 議事録作成":
    # (既存の機能は変更なし)
    pass

# ★★★ ここからが、新しく「追加」された「AI乗り換え案内」ツールの機能 ★★★
elif tool_choice == "🚇 AI乗り換え案内":
    st.header("🚇 AI乗り換え案内シミュレーター")
    st.info("出発地と目的地を入力すると、AIが標準的な所要時間や料金に基づいた最適なルートを3つ提案します。")
    st.warning("※これはリアルタイムの運行情報を反映したものではありません。あくまで目安としてご利用ください。")

    # ★あなたのアイデア！構造化された入力欄
    col1, col2 = st.columns(2)
    with col1:
        start_station = st.text_input("出発地を入力してください", "大阪")
    with col2:
        end_station = st.text_input("目的地を入力してください", "小阪")

    if st.button(f"「{start_station}」から「{end_station}」へのルートを検索"):
        if not gemini_api_key:
            st.error("サイドバーにGemini APIキーを入力してください。")
        else:
            with st.spinner(f"AIが最適なルートをシミュレーションしています..."):
                try:
                    genai.configure(api_key=gemini_api_key)
                    
                    # ★あなたのアイデアを反映した、超高精度なシステムプロンプト
                    system_prompt = f"""
                    あなたは、日本の公共交通機関の膨大なデータベースを内蔵した、世界最高の「乗り換え案内エンジン」です。
                    ユーザーから指定された「出発地」と「目的地」に基づき、標準的な所要時間、料金、乗り換え情報を基に、最適な移動ルートをシミュレートするのがあなたの役割です。
                    
                    特に、以下の条件を厳格に守って、シミュレーション結果をJSON形式で出力してください。
                    
                    1.  **3つのルート提案:** 必ず、「早さ・安さ・楽さ」のバランスが良い、優れたルートを「3つ」提案してください。
                    2.  **厳格なJSONフォーマット:** 出力は、必ず、以下のJSON形式の配列のみで回答してください。他の言葉、説明、言い訳は、一切含めないでください。
                    3.  **経路の詳細 (steps):**
                        *   `transport_type`: "電車", "徒歩", "バス" などを明確に記述してください。
                        *   `line_name`: 電車の場合、「JR大阪環状線」や「近鉄奈良線」のように、路線名を正確に記述してください。
                        *   `station_from`: 乗車駅を記述してください。
                        *   `station_to`: 降車駅を記述してください。
                        *   `details`: 「〇〇方面行き」や「〇番線ホーム」など、補足情報があれば記述してください。徒歩の場合は、「〇〇駅まで歩く」のように記述してください。
                    4.  **サマリー情報:**
                        *   `total_time`: ルート全体の合計所要時間（分）を、数値のみで記述してください。
                        *   `total_fare`: ルート全体の合計料金（円）を、数値のみで記述してください。
                        *   `transfers`: 乗り換え回数を、数値のみで記述してください。
                    
                    ```json
                    [
                      {{
                        "route_name": "ルート1：最速",
                        "summary": {{ "total_time": 30, "total_fare": 450, "transfers": 1 }},
                        "steps": [
                          {{ "transport_type": "電車", "line_name": "JR大阪環状線", "station_from": "大阪", "station_to": "鶴橋", "details": "内回り" }},
                          {{ "transport_type": "徒歩", "details": "近鉄線へ乗り換え" }},
                          {{ "transport_type": "電車", "line_name": "近鉄奈良線", "station_from": "鶴橋", "station_to": "河内小阪", "details": "普通・奈良行き" }}
                        ]
                      }},
                      {{
                        "route_name": "ルート2：乗り換え आसान",
                        "summary": {{ "total_time": 35, "total_fare": 480, "transfers": 0 }},
                        "steps": [
                          {{ "transport_type": "バス", "line_name": "市営バス12系統", "station_from": "大阪駅前", "station_to": "小阪駅前", "details": "" }}
                        ]
                      }},
                      {{
                        "route_name": "ルート3：最安",
                        "summary": {{ "total_time": 40, "total_fare": 400, "transfers": 2 }},
                        "steps": [
                          // ...
                        ]
                      }}
                    ]
                    ```
                    """
                    model = genai.GenerativeModel('gemini-1.5-flash-latest', system_instruction=system_prompt)
                    response = model.generate_content(f"出発地：{start_station}, 目的地：{end_station}")
                    
                    json_text = response.text.strip().lstrip("```json").rstrip("```")
                    routes = json.loads(json_text)
                    
                    st.success(f"AIによるルートシミュレーションが完了しました！")
                    
                    # ★あなたのアイデアを反映した、美しい表示
                    for i, route in enumerate(routes):
                        with st.expander(f"**{route['route_name']}** - 約{route['summary']['total_time']}分 / {route['summary']['total_fare']}円 / 乗り換え{route['summary']['transfers']}回", expanded=(i==0)):
                            for step in route['steps']:
                                if step['transport_type'] == "電車":
                                    st.markdown(f"**<font color='blue'>{step['station_from']}</font>**", unsafe_allow_html=True)
                                    st.markdown(f"｜ 🚃 {step['line_name']} ({step['details']})")
                            st.markdown(f"**<font color='red'>{end_station}</font>**", unsafe_allow_html=True)


                except Exception as e:
                    st.error(f"シミュレーション中にエラーが発生しました: {e}")

# (ここに、既存のツールのコードを、そのまま貼り付けてください)
# if tool_choice == "📅 あなただけのAI秘書": ...
# elif tool_choice == "💹 価格リサーチ": ...
# elif tool_choice == "📝 議事録作成": ...
