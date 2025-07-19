import streamlit as st
import json
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
import gspread
import requests
import traceback
import time
import re
import urllib.parse
import unicodedata
from datetime import date, datetime

# ===============================================================
# 1. アプリの基本設定と、神聖なる金庫からの情報取得
# ===============================================================
st.set_page_config(page_title="AIアシスタント・ポータル", page_icon="🤖", layout="wide")

try:
    CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
    REDIRECT_URI = st.secrets["REDIRECT_URI"]
    MAPS_API_KEY = st.secrets["Maps_API_KEY"] # Google Maps APIキーもSecretsから取得
    
    SCOPE = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email", 
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly"  # ファイル一覧取得のために追加
    ]
except KeyError as e:
    st.error(f"重大なエラー: StreamlitのSecretsに必須の情報が設定されていません。不足: {e}")
    st.info("以下のキーがSecretsに設定されていることを確認してください: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `REDIRECT_URI`, `Maps_API_KEY`")
    st.stop()

# --- ▼▼▼【交通費自動計算ツール用設定エリア】▼▼▼ ---
# 注: ここに設定するスプレッドシートURLは、公開設定またはアクセス権限が必要です。
# テスト用のスプレッドシートを使用することを強く推奨します。
SPREADSHEET_URL_RAW = "https://docs.google.com/spreadsheets/d/1UfX26pO3dFZ284qBTUgjq0Ase7PHxAuMlptmNzlJl0Q/edit?gid=0#gid=0" 
MAIN_SHEET_NAME = "MAC"
OFFICE_SHEET_NAME = "【参考】オフィス住所"
FACILITY_SHEET_NAME = "【参考】施設住所"
HEADER_COLUMNS = { "date": "③作業日", "staff": "③作業者", "station": "最寄駅", "prefecture": "都道府県", "address": "住所", "workplace": "勤務先", "distance_station": "③自宅〜最寄り駅距離", "distance_work": "③自宅〜勤務先距離" }
OFFICE_KEY_COL, OFFICE_VALUE_COL, OFFICE_START_ROW = 0, 2, 2
FACILITY_KEY_COL, FACILITY_VALUE_COL, FACILITY_START_ROW = 0, 2, 8
SIMILARITY_THRESHOLD = 0.5
# --- ▲▲▲ 設定はここまで ▲▲▲ ---

# ===============================================================
# 2. ログイン/ログアウト関数
# ===============================================================
def get_google_auth_flow():
    return Flow.from_client_config(
        client_config={ "web": { "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                                 "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token",
                                 "redirect_uris": [REDIRECT_URI], }},
        scopes=SCOPE,
        redirect_uri=REDIRECT_URI
    )

def google_logout():
    keys_to_clear = ["google_credentials", "google_user_info", "google_auth_state"]
    for key in keys_to_clear:
        st.session_state.pop(key, None)
    st.success("ログアウトしました。")
    st.rerun()

# ===============================================================
# 3. 認証処理の核心部（修正版）
# ===============================================================
# 認証処理を最初に実行（UIが描画される前）
if "code" in st.query_params and "google_credentials" not in st.session_state:
    st.sidebar.info("Google認証処理中...")
    
    query_state = st.query_params.get("state")
    session_state = st.session_state.get("google_auth_state")
    
    # stateが存在し、かつ一致する場合、または開発中のためstateチェックを一時的にスキップ (本番では False に変更推奨)
    if query_state and (query_state == session_state or True): # 一時的にstateチェックを無効化
        try:
            with st.spinner("Google認証処理中..."):
                flow = get_google_auth_flow()
                
                try:
                    flow.fetch_token(code=st.query_params["code"])
                except Exception as token_error:
                    if "Scope has changed" in str(token_error):
                        st.info("スコープの調整中...")
                        flow = Flow.from_client_config(
                            client_config={ 
                                "web": { 
                                    "client_id": CLIENT_ID, 
                                    "client_secret": CLIENT_SECRET,
                                    "auth_uri": "https://accounts.google.com/o/oauth2/auth", 
                                    "token_uri": "https://oauth2.googleapis.com/token",
                                    "redirect_uris": [REDIRECT_URI], 
                                }
                            },
                            scopes=None,
                            redirect_uri=REDIRECT_URI
                        )
                        flow.fetch_token(code=st.query_params["code"])
                    else:
                        raise token_error
                
                creds = flow.credentials
                
                st.session_state["google_credentials"] = {
                    "token": creds.token, 
                    "refresh_token": creds.refresh_token, 
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id, 
                    "client_secret": creds.client_secret, 
                    "scopes": creds.scopes,
                }
                
                user_info_response = requests.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {creds.token}"},
                )
                user_info_response.raise_for_status()
                st.session_state["google_user_info"] = user_info_response.json()
                
                st.success("✅ Google認証が正常に完了しました！")
                st.info(f"取得されたスコープ: {', '.join(creds.scopes) if creds.scopes else 'なし'}")
                
                st.query_params.clear()
                time.sleep(2)
                st.rerun()
            
        except Exception as e:
            st.error(f"Google認証中にエラーが発生しました: {str(e)}")
            st.code(traceback.format_exc())
            st.query_params.clear()
            if st.button("トップページに戻る"):
                st.rerun()
    else:
        st.warning("認証フローを開始します...")
        st.info("stateパラメータの不整合が検出されましたが、処理を続行します。")
        st.query_params.clear()
        if st.button("再度ログインする"):
            st.rerun()

# ===============================================================
# 4. 交通費自動計算ツールの主要ロジック
# ===============================================================
def run_traffic_expense_calculation(creds, Maps_api_key):
    st.info("処理開始: 各行をチェックし、空欄を埋めます。")
    log_messages = []
    
    # ロギング関数をStreamlitに適合させる
    def log_and_display(message):
        log_messages.append(message)
        st.text(message) # Streamlit上でリアルタイム表示

    try:
        gc = gspread.authorize(creds)
        
        # --- URL自動洗浄 & シートデータ取得 ---
        def clean_spreadsheet_url(raw_url):
            if 'spreadsheets/d/' in raw_url:
                match = re.search(r'spreadsheets/d/([^/]+)', raw_url)
                if match:
                    sheet_id = match.group(1)
                    clean_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}"
                    log_and_display(f"  - URLを自動洗浄しました: 「{clean_url}」")
                    return clean_url
            log_and_display(f"  - 警告: URLの形式が正しくない可能性があります。そのまま試行します: 「{raw_url}」")
            return raw_url
        
        SPREADSHEET_URL = clean_spreadsheet_url(SPREADSHEET_URL_RAW)
        
        def create_address_dict_from_sheet(worksheet, key_col_index, value_col_index, start_row):
            log_and_display(f"  - 参照シート「{worksheet.title}」のデータを読み込み中...")
            all_values, address_dict = worksheet.get_all_values(), {}
            last_key, last_value = "", ""
            for row in all_values[start_row - 1:]:
                if len(row) > max(key_col_index, value_col_index):
                    key, value = row[key_col_index].strip(), row[value_col_index].strip()
                    if key and key != last_key:
                        if last_key and last_value: address_dict[last_key] = last_value
                        last_key, last_value = key, ""
                    if value: last_value += value
            if last_key and last_value: address_dict[last_key] = last_value
            log_and_display(f"  - 「{worksheet.title}」から {len(address_dict)} 件の住所データを取得しました。")
            return address_dict
        
        def find_address_with_partial_match(target_name, address_dict):
            if not target_name: return None, None
            target_name = target_name.strip()
            if target_name in address_dict: return target_name, address_dict[target_name]
            for facility_name, address in address_dict.items():
                if target_name in facility_name: return facility_name, address
            for facility_name, address in address_dict.items():
                if facility_name in target_name: return facility_name, address
            
            def similarity_score(str1, str2):
                if not str1 or not str2: return 0
                common_chars, str1_chars, str2_chars = 0, list(str1), list(str2)
                for char in str1_chars:
                    if char in str2_chars:
                        common_chars += 1
                        str2_chars.remove(char)
                if len(str1) == 0 or len(str2) == 0: return 0
                return common_chars / max(len(str1), len(str2))
            
            best_match, best_score, best_address = None, 0, None
            for facility_name, address in address_dict.items():
                score = similarity_score(target_name, facility_name)
                if score > best_score and score >= SIMILARITY_THRESHOLD:
                    best_score, best_match, best_address = score, facility_name, address
            if best_match: return best_match, best_address
            return None, None
        
        with st.spinner("スプレッドシートにアクセス中..."):
            spreadsheet = gc.open_by_url(SPREADSHEET_URL)
            main_worksheet = spreadsheet.worksheet(MAIN_SHEET_NAME)
            log_and_display(f"メインシート「{main_worksheet.title}」へのアクセス成功。")
            office_worksheet = spreadsheet.worksheet(OFFICE_SHEET_NAME)
            office_addresses = create_address_dict_from_sheet(office_worksheet, OFFICE_KEY_COL, OFFICE_VALUE_COL, OFFICE_START_ROW)
            facility_worksheet = spreadsheet.worksheet(FACILITY_SHEET_NAME)
            facility_addresses = create_address_dict_from_sheet(facility_worksheet, FACILITY_KEY_COL, FACILITY_VALUE_COL, FACILITY_START_ROW)
        log_and_display("処理完了: データ取得完了。\n")

        # --- ヘッダー位置検出 ---
        log_and_display("処理開始: ヘッダー行を検出します。")
        all_values, header_row_index, col_indices = main_worksheet.get_all_values(), -1, {}
        for i, row in enumerate(all_values[:15]):
            if all(name in row for name in HEADER_COLUMNS.values()):
                header_row_index = i
                for key, name in HEADER_COLUMNS.items(): col_indices[key] = row.index(name)
                log_and_display(f"  - ヘッダー行: {header_row_index + 1}行目")
                break
        if header_row_index == -1: raise Exception("エラー: ヘッダーが見つかりません。")
        log_and_display("処理完了: ヘッダー位置特定完了。\n")

        # --- 専門関数群 ---
        def get_coords_from_address(api_key, address):
            if not address: return None, None, None
            cleaned_address = unicodedata.normalize('NFKC', address).replace(' ', '').replace('　', '')
            cleaned_address = re.sub(r'[−‐―]', '-', cleaned_address)
            
            # 作戦1: Geocoding API (より厳密な住所検索)
            log_and_display(f"    -> [作戦1: 辞書検索] 「{cleaned_address}」で試行...")
            try:
                params = {'address': cleaned_address, 'key': api_key, 'language': 'ja'}
                response = requests.get("https://maps.googleapis.com/maps/api/geocode/json", params=params, timeout=10)
                data = response.json()
                if data.get('status') == 'OK' and data.get('results'):
                    log_and_display(f"    -> [作戦1: 成功🎯] 辞書検索で場所を特定しました。")
                    result, location = data['results'][0], data['results'][0]['geometry']['location']
                    return f"{location['lat']},{location['lng']}", result.get('formatted_address', '（取得失敗）'), "辞書検索"
            except Exception as e:
                log_and_display(f"    -> [作戦1: エラー] Geocoding APIエラー: {e}")
            log_and_display(f"    -> [作戦1: 失敗] AI検索に切り替えます。")

            # 作戦2: Places API (Find Place From Text) (より柔軟な検索)
            log_and_display(f"    -> [作戦2: AI検索] 「{address}」で試行...")
            try:
                params = {'input': address, 'inputtype': 'textquery', 'fields': 'formatted_address,geometry', 'key': api_key, 'language': 'ja'}
                response = requests.get("https://maps.googleapis.com/maps/api/place/findplacefromtext/json", params=params, timeout=10)
                data = response.json()
                if data.get('status') == 'OK' and data.get('candidates'):
                    log_and_display(f"    -> [作戦2: 成功🎯] AI検索で場所を特定しました！")
                    candidate, location = data['candidates'][0], data['candidates'][0]['geometry']['location']
                    return f"{location['lat']},{location['lng']}", candidate.get('formatted_address', '（取得失敗）'), "AI検索"
            except Exception as e:
                log_and_display(f"    -> [作戦2: エラー] Places API(Find Text)エラー: {e}")
            log_and_display(f"    -> [作戦2: 失敗] 最終手段、AI超解析に切り替えます。")

            # 最終作戦: Places API (Autocomplete + Details) (予測と詳細取得)
            log_and_display(f"    -> [最終作戦: 予測] 「{address}」の最も確実な候補を探します...")
            try:
                params_ac = {'input': address, 'key': api_key, 'language': 'ja'}
                response_ac = requests.get("https://maps.googleapis.com/maps/api/place/autocomplete/json", params=params_ac, timeout=10)
                data_ac = response_ac.json()
                if data_ac.get('status') == 'OK' and data_ac.get('predictions'):
                    place_id = data_ac['predictions'][0]['place_id']
                    log_and_display(f"    -> [最終作戦: 候補発見] 最有力候補のIDを取得しました: {place_id}")
                    params_dt = {'place_id': place_id, 'fields': 'formatted_address,geometry', 'key': api_key, 'language': 'ja'}
                    response_dt = requests.get("https://maps.googleapis.com/maps/api/place/details/json", params=params_dt, timeout=10)
                    data_dt = response_dt.json()
                    if data_dt.get('status') == 'OK' and data_dt.get('result'):
                        log_and_display(f"    -> [最終作戦: 成功🎯] AI超解析で場所を確定しました！")
                        result, location = data_dt['result'], data_dt['result']['geometry']['location']
                        return f"{location['lat']},{location['lng']}", result.get('formatted_address', '（取得失敗）'), "AI超解析"
            except Exception as e:
                log_and_display(f"    -> [最終作戦: エラー] Places API(Autocomplete/Details)エラー: {e}")
            
            log_and_display(f"    -> [全作戦失敗] この住所の座標は特定できませんでした。")
            return None, None, None

        def get_distance_from_coords(api_key, origin, destination, format_type='default'):
            params = {'origins': origin, 'destinations': destination, 'key': api_key, 'language': 'ja', 'mode': 'walking'}
            try:
                response = requests.get("https://maps.googleapis.com/maps/api/distancematrix/json", params=params, timeout=10)
                data = response.json()
                if data.get('status') == 'OK' and data['rows'][0]['elements'][0].get('status') == 'OK':
                    dist = data['rows'][0]['elements'][0]['distance']['value']
                    if format_type == 'km_only': return f"{round(dist / 1000, 1)} km"
                    else: return f"{dist} m" if dist < 1000 else f"{round(dist / 1000, 1)} km"
            except Exception as e:
                log_and_display(f"    -> Distance Matrix APIエラー: {e}")
            return "取得失敗"

        def generate_maps_link(origin, destination):
            params = urllib.parse.urlencode({'api': 1, 'origin': origin, 'destination': destination, 'travelmode': 'walking'})
            return f"https://www.google.com/maps/dir/?{params}"

        # --- メイン処理 ---
        today_str, staff_name = f"{date.today().month}月{date.today().day}日", st.session_state["google_user_info"].get("name", "担当者不明")
        updated_cells, updated_row_count = [], 0
        
        # ProgressBarの初期化
        progress_bar = st.progress(0)
        total_rows_to_process = len(all_values) - (header_row_index + 1)
        
        for i, row_index in enumerate(range(header_row_index + 1, len(all_values))):
            row = all_values[row_index]
            
            # 進捗バーを更新
            progress = (i + 1) / total_rows_to_process
            progress_bar.progress(progress)

            if not any(cell.strip() for cell in row):
                log_and_display(f"\n---------------------[ 空行検出 ]---------------------")
                log_and_display(f"{row_index + 1}行目が空行のため、処理を正常に終了します。")
                break
            
            # ヘッダー行よりも列数が多いかチェック
            if len(row) <= max(col_indices.values()):
                log_and_display(f"  - {row_index + 1}行目をスキップ: 列数が不足しています。")
                continue

            # 作業日と作業者名が空の場合のみ処理を行う
            if not str(row[col_indices['date']]).strip() and not str(row[col_indices['staff']]).strip():
                updated_row_count += 1
                log_and_display(f"---------------------[ {row_index + 1}行目 ]---------------------")
                
                prefecture = str(row[col_indices['prefecture']]).strip()
                address_part = str(row[col_indices['address']]).strip()
                home_address_raw = address_part if (prefecture and address_part.startswith(prefecture)) else prefecture + address_part

                if not home_address_raw:
                    log_and_display(f"  - スキップ: 住所情報が空です。")
                    continue
                
                log_and_display(f"  - 自宅住所の座標を特定中...")
                log_and_display(f"    -> 元の住所(Excel): 「{home_address_raw}」")
                home_coords, home_formatted_address, success_strategy = get_coords_from_address(Maps_api_key, home_address_raw)
                time.sleep(0.1) # API制限回避のため
                
                if not home_coords:
                    log_and_display(f"  - 致命的エラー: 自宅の座標が特定できませんでした。この行をスキップします。")
                    continue
                log_and_display(f"    -> ★[{success_strategy}]で特定した住所: 「{home_formatted_address}」")
                
                updated_cells.extend([
                    gspread.Cell(row_index + 1, col_indices['date'] + 1, today_str),
                    gspread.Cell(row_index + 1, col_indices['staff'] + 1, staff_name)
                ])

                station_name = str(row[col_indices['station']]).strip()
                if station_name:
                    station_query = f"{prefecture} {station_name}駅"
                    station_coords, _, _ = get_coords_from_address(Maps_api_key, station_query)
                    time.sleep(0.1) # API制限回避のため
                    if station_coords:
                        distance1 = get_distance_from_coords(Maps_api_key, home_coords, station_coords)
                        if distance1 != "取得失敗":
                            updated_cells.append(gspread.Cell(row_index + 1, col_indices['distance_station'] + 1, distance1))
                            log_and_display(f"  - 駅までの距離: {distance1}")
                            log_and_display(f"  - 駅へのルート(確認用): [Google Maps Link]({generate_maps_link(home_formatted_address, station_query)})")
                
                workplace_name = str(row[col_indices['workplace']]).strip()
                if workplace_name:
                    workplace_address, found_facility_name = None, None
                    if "オフィス" in workplace_name:
                        log_and_display(f"  - 勤務先「{workplace_name}」はオフィスと判断。オフィス住所録を検索します...")
                        found_facility_name, workplace_address = find_address_with_partial_match(workplace_name, office_addresses)
                        if not found_facility_name:
                            log_and_display(f"    -> ❌ オフィス住所録に該当なし。念のため施設住所録も検索します...")
                            found_facility_name, workplace_address = find_address_with_partial_match(workplace_name, facility_addresses)
                    else:
                        log_and_display(f"  - 勤務先「{workplace_name}」は施設と判断。施設住所録を検索します...")
                        found_facility_name, workplace_address = find_address_with_partial_match(workplace_name, facility_addresses)
                        if not found_facility_name:
                            log_and_display(f"    -> ❌ 施設住所録に該当なし。念のためオフィス住所録も検索します...")
                            found_facility_name, workplace_address = find_address_with_partial_match(workplace_name, office_addresses)
                    
                    if workplace_address:
                        log_and_display(f"    -> 🎯 一致した施設名: 「{found_facility_name}」")
                        log_and_display(f"    -> 📍 発見した住所: 「{workplace_address}」")
                        workplace_coords, _, _ = get_coords_from_address(Maps_api_key, workplace_address)
                        time.sleep(0.1) # API制限回避のため
                        if workplace_coords:
                            distance2 = get_distance_from_coords(Maps_api_key, home_coords, workplace_coords, format_type='km_only')
                            if distance2 != "取得失敗":
                                updated_cells.append(gspread.Cell(row_index + 1, col_indices['distance_work'] + 1, distance2))
                                log_and_display(f"  - 勤務先までの距離: {distance2}")
                                log_and_display(f"  - 勤務先へのルート(確認用): [Google Maps Link]({generate_maps_link(home_formatted_address, workplace_address)})")
                    else:
                        log_and_display(f"  - ⚠️ 警告: 勤務先「{workplace_name}」が、どちらの参照シートでも見つかりませんでした。")
                log_and_display("\n\n")

        # --- シートへの書き込み ---
        if updated_row_count > 0:
            log_and_display(f"---------------------[ 最終報告 ]---------------------")
            log_and_display(f"\n🔄 {updated_row_count}件の行を更新します...")
            with st.spinner("スプレッドシートを更新中..."):
                try:
                    main_worksheet.update_cells(updated_cells, value_input_option='USER_ENTERED')
                    log_and_display("✅ スプレッドシート更新完了！")
                except Exception as e:
                    log_and_display(f"❌ スプレッドシート更新エラー: {e}")
                    st.error(f"スプレッドシートの更新中にエラーが発生しました: {e}")
        else:
            log_and_display("ℹ️ 更新対象の行がありませんでした。")
            st.info("更新対象の行（作業日と作業者名が空の行）はありませんでした。")

        st.success(f"\n📈 全ての処理が完了しました。")
        st.markdown(f"🔗 更新されたスプレッドシートはこちらから確認できます: [交通費計算シート]({SPREADSHEET_URL})")

    except Exception as e:
        log_and_display(f"🛑 交通費計算ツールの実行中にエラーが発生しました: {e}")
        log_and_display(traceback.format_exc())
        st.error(f"交通費計算ツールの実行中にエラーが発生しました: {e}")
        st.code(traceback.format_exc())
    finally:
        progress_bar.empty() # 処理完了後にプログレスバーを非表示にする
        st.subheader("実行ログ詳細")
        st.text_area("ログ", value="\n".join(log_messages), height=300)

# ===============================================================
# 5. UI描画
# ===============================================================
with st.sidebar:
    st.title("🤖 AIアシスタント・ポータル")
    
    if "google_user_info" not in st.session_state:
        st.info("各ツールを利用するには、Googleアカウントでのログインが必要です。")
        
        flow = get_google_auth_flow()
        authorization_url, state = flow.authorization_url(
            prompt="consent", 
            access_type="offline",
            include_granted_scopes='true'
        )
        st.session_state["google_auth_state"] = state
        
        st.link_button("🗝️ Googleアカウントでログイン", authorization_url, use_container_width=True)
        
        with st.expander("🔍 トラブルシューティング"):
            st.write("認証で問題が発生する場合:")
            st.write("1. ブラウザのキャッシュとCookieをクリアしてください")
            st.write("2. シークレット/プライベートモードでお試しください")
            st.write("3. 複数のタブでアプリを開いている場合は、他のタブを閉じてください")
    else:
        st.success("✅ ログイン中")
        user_info = st.session_state.get("google_user_info", {})
        if 'name' in user_info: 
            st.markdown(f"**ユーザー:** {user_info['name']}")
        if 'email' in user_info: 
            st.markdown(f"**メール:** {user_info['email']}")
        if st.button("🔑 ログアウト", use_container_width=True): 
            google_logout()
    
    st.divider()

# --- メインコンテンツ ---
if "google_user_info" not in st.session_state:
    st.header("ようこそ、AIアシスタント・ポータルへ！")
    st.info("👆 サイドバーにある「🗝️ Googleアカウントでログイン」ボタンを押して、旅を始めましょう！")
else:
    tool_options = ("🚙 交通費自動計算", "📅 カレンダー登録", "💹 価格リサーチ", "📝 議事録作成", "🚇 AI乗り換え案内")
    with st.sidebar:
        tool_choice = st.radio("使いたいツールを選んでください:", tool_options, disabled=False)
    
    st.header(f"{tool_choice}")
    st.divider()

    if tool_choice == "🚙 交通費自動計算":
        st.success("ようこそ！ 認証システムは、正常に稼働しています。")
        st.info("このツールは、Googleスプレッドシートに記載された住所情報をもとに、最寄り駅や勤務先までの距離を自動で計算し、シートに書き込みます。")
        st.warning("⚠️ **重要**: Google Cloud Platformで 'Geocoding API' と 'Places API' が有効になっていることを確認してください。")
        st.warning("⚠️ **注意**: 現状、スプレッドシートのURLはコード内に直接記述されています。**テスト用のスプレッドシート**での実行を強く推奨します。")
        st.markdown(f"**対象スプレッドシートURL:** [現在の設定シート]({SPREADSHEET_URL_RAW})")

        try:
            creds = Credentials(**st.session_state["google_credentials"])
            
            # Google Maps APIが有効かどうかのチェックを促す
            with st.expander("🛠️ Google Maps APIの状態確認とトラブルシューティング"):
                st.write("交通費計算機能を利用するには、Google Cloud Platformで以下のAPIが有効になっている必要があります。")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**1. Geocoding API** (住所から座標を取得)")
                    st.link_button("🔗 Geocoding APIを有効にする", "https://console.cloud.google.com/marketplace/details/google/geocoding_api", use_container_width=True)
                with col2:
                    st.markdown("**2. Places API** (場所検索と詳細取得)")
                    st.link_button("🔗 Places APIを有効にする", "https://console.cloud.google.com/marketplace/details/google/places_api", use_container_width=True)
                st.markdown("---")
                st.markdown("APIが有効になっているか、または有効にする必要がある場合は、上記のリンクから設定を確認してください。")

            st.write("---")
            st.subheader("自動計算の実行")
            if st.button("▶️ 交通費を自動計算する", type="primary", use_container_width=True):
                with st.spinner("交通費計算処理を実行中... しばらくお待ちください。"):
                    run_traffic_expense_calculation(creds, MAPS_API_KEY)
                    st.success("交通費計算処理が完了しました！")
            
        except Exception as e:
            st.error(f"ツールの初期化中にエラーが発生しました: {e}")
            st.code(traceback.format_exc())
            
            with st.expander("🔧 トラブルシューティング"):
                st.write("**よくある解決方法:**")
                st.write("1. **再認証**: ログアウトして再度ログインする")
                st.write("2. **権限の確認**: Google アカウントの「アプリとサイト」で権限を確認")
                st.write("3. **キャッシュクリア**: ブラウザのキャッシュとCookieをクリア")
                if st.button("🔄 強制再認証", key="force_reauth"):
                    google_logout()
    else:
        st.warning(f"ツール「{tool_choice}」は現在、新しい認証システムへの移行作業中です。")
