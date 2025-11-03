# ===========================================
# Caption to Narration - 最終修正版
# ===========================================

import streamlit as st
import re
import math
# ▼▼▼ Gemini API 関連 ▼▼▼
from google import genai
from google.genai.errors import APIError


# ===============================================================
# ▼▼▼ AIチェックの本体（Gemini API呼び出し部分）▼▼▼
# ===============================================================
def check_narration_with_gemini(narration_blocks, api_key):
    """Gemini APIを使用してナレーションの誤字脱字をチェックする"""
    if not api_key:
        return "エラー：Gemini APIキーが設定されていません。Streamlit Secretsを確認してください。"

    try:
        client = genai.Client(api_key=api_key)
        formatted_text = "\n".join([f"[{b['time']}] {b['text']}" for b in narration_blocks])

        prompt = f"""
        あなたはプロフェッショナルな校正者です。
        以下のナレーション原稿のリストを、誤字脱字、不適切な表現、文法ミスがないか厳密にチェックしてください。
        
        【指示】
        1. 誤りが見つかった場合のみ、以下の Markdown テーブル形式で修正提案とその理由を出力してください。
        2. 誤りがない場合は、「問題ありませんでした。」とだけ出力してください。
        
        【出力形式】
        | 原文の位置 | 本文 | 修正提案 | 理由 |
        |---|---|---|---|
        | (行番号または特定箇所) | (誤っている単語・フレーズ) | (正しい単語・フレーズ) | (修正理由) |
        
        【ナレーション原稿】
        ---
        {formatted_text}
        ---
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return getattr(response, "text", "") or ""

    except APIError as e:
        return f"Gemini APIエラーが発生しました。詳細: {e}"
    except Exception as e:
        return f"予期せぬエラー: {e}"


# ===============================================================
# ▼▼▼ ナレーション変換エンジン（Nロジック更新版）▼▼▼
# ===============================================================
def convert_narration_script(text, n_force_insert_flag=True, mm_ss_colon_flag=False):
    FRAME_RATE = 30.0
    CONNECTION_THRESHOLD = 1.0 + (10.0 / FRAME_RATE)

    to_zenkaku_num = str.maketrans('0123456789', '０１２３４５６７８９')
    hankaku_symbols = '!@#$%&-+='
    zenkaku_symbols = '！＠＃＄％＆－＋＝'
    hankaku_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ' + hankaku_symbols
    zenkaku_chars = 'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ０１２３４５６７８９　' + zenkaku_symbols
    to_zenkaku_all = str.maketrans(hankaku_chars, zenkaku_chars)
    to_hankaku_time = str.maketrans('０１２３４５６７８９：〜', '0123456789:~')

    lines = text.strip().split('\n')
    start_index = -1
    time_pattern = r'(\d{2})[:;](\d{2})[:;](\d{2})[;.](\d{2})\s*-\s*(\d{2})[:;](\d{2})[:;](\d{2})[;.](\d{2})'

    for i, line in enumerate(lines):
        line_with_frames = re.sub(r'(\d{2}:\d{2}:\d{2})(?![:.]\d{2})', r'\1.00', line)
        normalized_line = line_with_frames.strip().translate(to_hankaku_time).replace('~', '-')
        if re.match(time_pattern, normalized_line):
            start_index = i
            break
            
    if start_index == -1: 
        return {"narration_script": "エラー：変換可能なタイムコード（フレーム情報を含む形式）が見つかりませんでした。", "ai_data": []}
        
    relevant_lines = lines[start_index:]
    blocks = []
    i = 0
    while i < len(relevant_lines):
        current_line = relevant_lines[i].strip()
        line_with_frames = re.sub(r'(\d{2}:\d{2}:\d{2})(?![:.]\d{2})', r'\1.00', current_line)
        normalized_line = line_with_frames.translate(to_hankaku_time).replace('~', '-')
        if re.match(time_pattern, normalized_line):
            time_val = current_line
            text_val = ""
            if i + 1 < len(relevant_lines):
                next_line = relevant_lines[i+1].strip()
                next_normalized_line = re.sub(r'(\d{2}:\d{2}:\d{2})(?![:.]\d{2})', r'\1.00', next_line).translate(to_hankaku_time).replace('~', '-')
                if not re.match(time_pattern, next_normalized_line):
                    text_val = next_line
                    i += 1
            blocks.append({'time': time_val, 'text': text_val})
        i += 1
        
    output_lines = []
    narration_blocks_for_ai = []
    parsed_blocks = []
    for block in blocks:
        line_with_frames = re.sub(r'(\d{2}:\d{2}:\d{2})(?![:.]\d{2})', r'\1.00', block['time'])
        normalized_time_str = line_with_frames.translate(to_hankaku_time).replace('~', '-')
        time_match = re.match(time_pattern, normalized_time_str)
        if not time_match: continue
        
        groups = time_match.groups()
        start_hh, start_mm, start_ss, start_fr, end_hh, end_mm, end_ss, end_fr = [int(g or 0) for g in groups]
        narration_blocks_for_ai.append({'time': block['time'].strip(), 'text': block['text'].strip()})
        parsed_blocks.append({
            'start_hh': start_hh, 'start_mm': start_mm, 'start_ss': start_ss, 'start_fr': start_fr,
            'end_hh': end_hh, 'end_mm': end_mm, 'end_ss': end_ss, 'end_fr': end_fr,
            'text': block['text']
        })

    previous_end_hh = None
    for i, block in enumerate(parsed_blocks):
        start_hh, start_mm, start_ss, start_fr = block['start_hh'], block['start_mm'], block['start_ss'], block['start_fr']
        end_hh, end_mm, end_ss, end_fr = block['end_hh'], block['end_mm'], block['end_ss'], block['end_fr']

        should_insert_h_marker = False
        marker_hh_to_display = -1
        if i == 0:
            if start_hh > 0:
                should_insert_h_marker = True
                marker_hh_to_display = start_hh
            previous_end_hh = end_hh
        else:
            if start_hh < end_hh:
                should_insert_h_marker = True
                marker_hh_to_display = end_hh
            elif previous_end_hh is not None and start_hh > previous_end_hh:
                should_insert_h_marker = True
                marker_hh_to_display = start_hh

        if should_insert_h_marker:
             output_lines.append("")
             output_lines.append(f"【{str(marker_hh_to_display).translate(to_zenkaku_num)}Ｈ】")
             output_lines.append("")
        previous_end_hh = end_hh

        total_seconds_in_minute_loop = (start_mm % 60) * 60 + start_ss
        spacer = ""
        is_half_time = False
        base_time_str = ""
        if 0 <= start_fr <= 9:
            display_mm = (total_seconds_in_minute_loop // 60) % 60
            display_ss = total_seconds_in_minute_loop % 60
            base_time_str = f"{display_mm:02d}{display_ss:02d}"
            spacer = "　　　"
        elif 10 <= start_fr <= 22:
            display_mm = (total_seconds_in_minute_loop // 60) % 60
            display_ss = total_seconds_in_minute_loop % 60
            base_time_str = f"{display_mm:02d}{display_ss:02d}"
            spacer = "　　"
            is_half_time = True
        else:
            total_seconds_in_minute_loop += 1
            display_mm = (total_seconds_in_minute_loop // 60) % 60
            display_ss = total_seconds_in_minute_loop % 60
            base_time_str = f"{display_mm:02d}{display_ss:02d}"
            spacer = "　　　"

        colon_time_str = f"{base_time_str[:2]}：{base_time_str[2:]}" if mm_ss_colon_flag else base_time_str
        formatted_start_time = f"{colon_time_str.translate(to_zenkaku_num)}半" if is_half_time else colon_time_str.translate(to_zenkaku_num)

        speaker_symbol = 'Ｎ'
        text_content = block['text']
        body = ""
        if n_force_insert_flag:
            tc = text_content.strip()
            m_leading_n = re.match(r'^[\s　]*([NnＮｎ])(?:[\s　]*[：:])?(?![A-Za-z0-9])[\s　]*(.*)$', tc)
            if m_leading_n:
                speaker_symbol = 'Ｎ'
                body = m_leading_n.group(2).lstrip().lstrip('　')
            else:
                match = re.match(r'^(\S+)[\s　]+(.*)', text_content)
                if match:
                    raw_speaker = match.group(1)
                    body = match.group(2).strip()
                    if raw_speaker.upper() in ('N', 'Ｎ'):
                        speaker_symbol = 'Ｎ'
                    else:
                        speaker_symbol = raw_speaker.translate(to_zenkaku_all)
                else:
                    if tc.upper() in ('N', 'Ｎ'):
                        body = ""
                    else:
                        body = tc
            if not body: body = "※注意！本文なし！"
        else:
            speaker_symbol = ''
            body = text_content
            if not body.strip():
                body = "※注意！本文なし！"
        body = body.translate(to_zenkaku_all)

        end_string = ""
        add_blank_line = True
        if i + 1 < len(parsed_blocks):
            next_block = parsed_blocks[i+1]
            end_total_seconds = (end_hh * 3600) + (end_mm * 60) + end_ss + (end_fr / FRAME_RATE)
            next_start_total_seconds = (next_block['start_hh'] * 3600) + (next_block['start_mm'] * 60) + next_block['start_ss'] + (next_block['start_fr'] / FRAME_RATE)
            if next_start_total_seconds - end_total_seconds < CONNECTION_THRESHOLD:
                add_blank_line = False

        if add_blank_line:
            adj_ss = end_ss
            adj_mm = end_mm
            if 0 <= end_fr <= 9: adj_ss = end_ss - 1
            if adj_ss < 0: adj_ss = 59; adj_mm -= 1
            adj_mm_display = adj_mm % 60
            if start_hh != end_hh or (start_mm % 60) != adj_mm_display:
                formatted_end_time = f"{adj_mm_display:02d}{adj_ss:02d}".translate(to_zenkaku_num)
            else:
                formatted_end_time = f"{adj_ss:02d}".translate(to_zenkaku_num)
            end_string = f" (～{formatted_end_time})"

        if n_force_insert_flag:
            output_lines.append(f"{formatted_start_time}{spacer}{speaker_symbol}　{body}{end_string}")
        else:
            output_lines.append(f"{formatted_start_time}{spacer}{body}{end_string}")

        if add_blank_line and i < len(parsed_blocks) - 1:
            output_lines.append("")
            
    return {"narration_script": "\n".join(output_lines), "ai_data": narration_blocks_for_ai}


# ===============================================================
# ▼▼▼ Streamlit UI ▼▼▼
# ===============================================================
st.set_page_config(page_title="Caption to Narration", page_icon="📝", layout="wide")
st.title('Caption to Narration')

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")

# --- セッション状態の初期化 ---
if "ai_result_cache" not in st.session_state:
    st.session_state["ai_result_cache"] = ""
if "last_input_hash" not in st.session_state:
    st.session_state["last_input_hash"] = None

st.markdown("""<style> 
textarea::placeholder { font-size: 13px; } 
textarea { font-size: 14px !important; }
</style>""", unsafe_allow_html=True)

help_text = """
【機能詳細】
・ENDタイム(秒のみ)が自動で入ります
・Hをまたぐときは自動で仕切りが入ります
・✅N強制挿入ONで自動で全角Ｎが挿入されます
・半角英数字は全て全角に変換します
・✅ｍｍ：ｓｓで出力ONでタイムに：が入ります
・✅誤字脱字をAIでチェックONでAIが校正します
"""

# --- 1段目：タイトル ---
col1_top, col2_top = st.columns(2)
with col1_top:
    st.header('ナレーション原稿形式に変換します')
with col2_top:
    st.header('コピーしてお使いください')

# --- 2段目：メインのテキストエリア ---
col1_main, col2_main = st.columns(2)
with col1_main:
    input_text = st.text_area(
        "　", 
        height=500, 
        placeholder="ここに元原稿をペーストして Ctrl+Enter を押してください。",
        help=help_text
    )

# --- ★【重要】キャッシュ管理ロジック ---
# 入力テキストのハッシュを計算し、前回と違う場合のみAIキャッシュをクリアする
cur_hash = hash(input_text.strip())
if st.session_state["last_input_hash"] != cur_hash:
    st.session_state["ai_result_cache"] = ""  # AIキャッシュをリセット
    st.session_state["last_input_hash"] = cur_hash # ハッシュを更新

# --- 3段目：コントロールエリア ---
col1_bottom_opt, col2_bottom_opt, col3_bottom_opt, _ = st.columns([1.5, 2, 3, 7.5]) 
with col1_bottom_opt:
    n_force_insert = st.checkbox("N強制挿入", value=True)
with col2_bottom_opt:
    mm_ss_colon = st.checkbox("ｍｍ：ｓｓで出力", value=False)
with col3_bottom_opt:
    ai_check_flag = st.checkbox("誤字脱字をAIでチェック", value=False)

# --- 4段目：変換実行と結果表示 ---
if input_text:
    try:
        # 1. 本文の変換処理（これは毎回実行される）
        conversion_result = convert_narration_script(input_text, n_force_insert, mm_ss_colon)
        converted_text = conversion_result["narration_script"]
        ai_data = conversion_result["ai_data"]
        
        # 2. 変換結果を右のエリアに表示
        with col2_main:
             st.text_area("　", value=converted_text, height=500)
             
        # 3. AIチェックがONの場合、結果を下部に表示
        if ai_check_flag:
            st.markdown("---")
            st.subheader("📝 AI校正チェック結果")
            
            with st.spinner("Geminiが誤字脱字をチェック中..."):
                # キャッシュが空の場合のみ、APIを呼び出す
                if not st.session_state.get("ai_result_cache"):
                    ai_result = check_narration_with_gemini(ai_data, GEMINI_API_KEY)
                    st.session_state["ai_result_cache"] = ai_result
            
            # キャッシュされた（または新しく取得した）結果を表示
            st.markdown(st.session_state.get("ai_result_cache", "チェック結果がありません。"))
            
    except Exception as e:
        with col2_main:
            st.error(f"エラーが発生しました。テキストの形式を確認してください。\n\n詳細: {e}")
            st.text_area("　", value="", height=500, disabled=True)
else:
    # 入力がない時に右側の高さを維持してレイアウト崩れを防ぐ
    with col2_main:
        st.markdown('<div style="height: 538px;"></div>', unsafe_allow_html=True)
            
# --- フッター ---
st.markdown("---")
st.markdown(
    """
    <div style="text-align: right; font-size: 12px; color: #C5D6B9;">
        © 2025 kimika Inc. All rights reserved.
    </div>
    """,
    unsafe_allow_html=True
)```
