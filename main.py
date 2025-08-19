import os
import json
from flask import Flask, request, jsonify
import threading
import time
import requests
from datetime import datetime, timedelta

# Flask 앱을 초기화합니다.
app = Flask(__name__)

# --- 서버가 시작될 때 한 번만 실행되는 부분 ---

# API 키를 환경 변수에서 불러옵니다.
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY')
BIBLE_DATA = {}  # 성경 데이터를 저장할 변수

# 사용자별 세션 저장 (모델 선택 + 대화 기록)
user_sessions = {}

# Groq 클라이언트 초기화 (현재 API 키 문제로 임시 비활성화)
groq_client = None
GROQ_DISABLED = True  # 임시 비활성화

if GROQ_API_KEY and not GROQ_DISABLED:
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_API_KEY)
        print("✅ Groq API 키가 성공적으로 설정되었습니다.")
    except Exception as e:
        print(f"⚠️ Groq 클라이언트 초기화 실패: {e}")
        groq_client = None
else:
    if GROQ_DISABLED:
        print("⚠️ Groq가 임시로 비활성화되었습니다. (API 키 문제)")
    else:
        print("⚠️ GROQ_API_KEY 환경 변수가 설정되지 않았습니다.")

# Claude 클라이언트 초기화
claude_client = None
if CLAUDE_API_KEY:
    try:
        from anthropic import Anthropic
        claude_client = Anthropic(api_key=CLAUDE_API_KEY, timeout=60.0)
        print("✅ Claude API 키가 성공적으로 설정되었습니다.")
    except Exception as e:
        print(f"⚠️ Claude 클라이언트 초기화 실패: {e}")
        claude_client = None
else:
    print("⚠️ CLAUDE_API_KEY 환경 변수가 설정되지 않았습니다.")

# 성경 JSON 파일을 읽어 메모리에 저장합니다.
try:
    with open('bible.json', 'r', encoding='utf-8') as f:
        BIBLE_DATA = json.load(f)
    print("✅ bible.json 파일 로딩 완료!")
    print(f"📖 총 {len(BIBLE_DATA)} 개의 성경 구절 로드됨")
except FileNotFoundError:
    print("🚨 [경고] bible.json 파일을 찾을 수 없습니다.")
except json.JSONDecodeError:
    print("🚨 [에러] bible.json 파일 형식이 올바르지 않습니다.")


# --- 대화 기록 관리 함수 ---

def get_user_session(user_id):
    """사용자 세션 가져오기 (없으면 생성)"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'model': 'claude' if claude_client else None,  # Claude를 기본으로
            'conversation': [],  # 대화 기록
            'last_activity': datetime.now(),
            'counseling_stage': 'initial',  # initial, exploring, deepening, concluding
            'key_topics': []  # 주요 상담 주제
        }
    else:
        # 30분 이상 비활성 시 대화 초기화
        if datetime.now() - user_sessions[user_id]['last_activity'] > timedelta(minutes=30):
            user_sessions[user_id]['conversation'] = []
            user_sessions[user_id]['counseling_stage'] = 'initial'
            user_sessions[user_id]['key_topics'] = []
    
    user_sessions[user_id]['last_activity'] = datetime.now()
    return user_sessions[user_id]


def add_to_conversation(user_id, role, content):
    """대화 기록에 추가 (최대 10개 유지)"""
    session = get_user_session(user_id)
    session['conversation'].append({'role': role, 'content': content})
    # 메모리 관리를 위해 최대 10개의 대화만 유지
    if len(session['conversation']) > 10:
        session['conversation'] = session['conversation'][-10:]


def get_conversation_context(user_id):
    """대화 컨텍스트 문자열로 반환"""
    session = get_user_session(user_id)
    if not session['conversation']:
        return ""
    
    context = "=== 이전 대화 내용 ===\n"
    for msg in session['conversation'][-4:]:  # 최근 4개만
        role = "상담자" if msg['role'] == 'assistant' else "내담자"
        # 긴 내용은 요약
        content = msg['content'][:150] + "..." if len(msg['content']) > 150 else msg['content']
        context += f"{role}: {content}\n"
    context += "================\n\n"
    return context


def safe_truncate(text, max_length=750):
    """텍스트를 안전하게 자르기 (더 짧게)"""
    if len(text) <= max_length:
        return text
    
    # 마지막 완전한 문장 찾기
    truncated = text[:max_length]
    
    # 마지막 마침표, 느낌표, 물음표 위치 찾기
    last_period = truncated.rfind('.')
    last_exclaim = truncated.rfind('!')
    last_question = truncated.rfind('?')
    
    # 가장 마지막 문장 부호 위치
    last_sentence = max(last_period, last_exclaim, last_question)
    
    if last_sentence > max_length * 0.7:  # 70% 이상이면 그 위치에서 자르기
        return truncated[:last_sentence + 1]
    else:
        # 너무 짧으면 강제로 자르고 ... 추가
        return truncated[:max_length-3] + "..."


# --- 실제 요청을 처리하는 함수 부분 ---

def search_bible(keywords):
    """성경 데이터에서 관련 구절을 검색하는 함수"""
    search_results = []
    if not BIBLE_DATA:
        return search_results
    
    if isinstance(keywords, str):
        keywords = [keywords]
    
    expanded_keywords = []
    for keyword in keywords:
        expanded_keywords.append(keyword)
        if "외로" in keyword or "혼자" in keyword: 
            expanded_keywords.extend(["외로", "고독", "혼자", "홀로", "위로"])
        elif "힘들" in keyword or "어려" in keyword: 
            expanded_keywords.extend(["힘들", "어려움", "고난", "시련", "인내"])
        elif "감사" in keyword: 
            expanded_keywords.extend(["감사", "감사하", "은혜", "축복"])
        elif "사랑" in keyword: 
            expanded_keywords.extend(["사랑", "사랑하", "아끼"])
        elif "기도" in keyword: 
            expanded_keywords.extend(["기도", "간구", "부르짖"])
        elif "배우자" in keyword or "부부" in keyword or "결혼" in keyword or "갈등" in keyword: 
            expanded_keywords.extend(["사랑", "인내", "용서", "화목", "아내", "남편"])
        elif "갈등" in keyword or "다툼" in keyword: 
            expanded_keywords.extend(["화평", "용서", "사랑", "인내", "화목"])
    
    expanded_keywords = list(set(expanded_keywords))
    
    for verse, content in BIBLE_DATA.items():
        if any(keyword in content for keyword in expanded_keywords):
            search_results.append(f"{verse}: {content}")
            if len(search_results) >= 2:  # 2개로 줄임
                break
    
    return search_results


def generate_claude_response(user_message, bible_verses, user_id, quick_mode=False):
    """Claude AI를 사용하여 응답 생성 (빠른/깊이있는 모드 통합)"""
    if not claude_client: 
        return "Claude API가 설정되지 않았습니다."
    
    session = get_user_session(user_id)
    context = get_conversation_context(user_id)
    verses_text = "\n".join(bible_verses[:1]) if bible_verses else ""  # 1개만
    
    # 대화 횟수에 따라 상담 단계 조정
    conv_count = len(session['conversation'])
    if conv_count <= 2:
        session['counseling_stage'] = 'initial'
    elif conv_count <= 4:
        session['counseling_stage'] = 'exploring'
    elif conv_count <= 8:
        session['counseling_stage'] = 'deepening'
    else:
        session['counseling_stage'] = 'concluding'
    
    # 모드에 따른 프롬프트 조정
    if quick_mode:
        prompt = f"""한국어 기독교 상담사입니다.

{context}

[성경 구절]
{verses_text}

[내담자]
{user_message}

[빠른 상담 모드]
- 300자 이내 간결한 응답
- 핵심 위로와 격려
- 실용적 조언 1개
- 따뜻한 마무리

한국어로만."""
    else:
        prompt = f"""한국어 기독교 상담 전문가입니다.

{context}

[상담 단계: {session['counseling_stage']}]

[성경 구절]
{verses_text}

[내담자]
{user_message}

[깊이있는 상담 모드]
1. 350자 이내 엄격 제한
2. 공감 표현으로 시작
3. 핵심 조언 1-2개
4. 구체적 질문 1개
5. 희망의 메시지로 마무리

반드시 350자 이내. 한국어만."""

    try:
        response = claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=400,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.content[0].text
        
        # 더 엄격한 길이 제한
        result = safe_truncate(result, 750)  # 750자로 제한
        
        print(f"✅ Claude 응답 길이: {len(result)}자 ({'빠른' if quick_mode else '깊이있는'} 모드)")
        return result
    except Exception as e:
        print(f"Claude 오류: {e}")
        return "죄송합니다. 잠시 후 다시 시도해주세요."


def process_and_callback(user_id, user_message, callback_url):
    """AI 응답 생성 후 callbackUrl로 결과를 POST 요청하는 함수"""
    try:
        session = get_user_session(user_id)
        selected_model = session.get('model', 'claude')  # 기본값 claude
        
        # Groq 비활성화 상태면 강제로 Claude 사용
        if GROQ_DISABLED or not groq_client:
            selected_model = 'claude'
            session['model'] = 'claude'

        # 대화 기록에 사용자 메시지 추가
        add_to_conversation(user_id, 'user', user_message)

        # 주요 키워드 추출 및 저장
        keywords = user_message.split()
        for keyword in keywords:
            if len(keyword) > 2 and keyword not in session['key_topics']:
                session['key_topics'].append(keyword)
                if len(session['key_topics']) > 10:
                    session['key_topics'] = session['key_topics'][-10:]

        # 성경 구절 검색
        bible_verses = search_bible(keywords)
        if not bible_verses: 
            bible_verses = search_bible(["사랑", "위로", "평안"])

        print(f"[백그라운드] 모델: {selected_model}, 단계: {session['counseling_stage']}")
        
        # AI 응답 생성 (Claude만 사용)
        # 원래 groq 선택이었어도 빠른 모드로 Claude 사용
        quick_mode = (selected_model == 'groq')
        ai_response = generate_claude_response(user_message, bible_verses, user_id, quick_mode)
        
        # 최종 길이 체크 (카카오톡 안전 제한)
        if len(ai_response) > 750:
            ai_response = safe_truncate(ai_response, 750)
            print(f"⚠️ 응답 재조정: {len(ai_response)}자")
        
        # 대화 기록에 AI 응답 추가
        add_to_conversation(user_id, 'assistant', ai_response)
        
        # 응답 준비
        response_data = {
            "version": "2.0", 
            "template": {
                "outputs": [{"simpleText": {"text": ai_response}}], 
                "quickReplies": []
            }
        }
        
        # 상담 단계별 빠른 응답 버튼
        if session['counseling_stage'] in ['initial', 'exploring']:
            response_data["template"]["quickReplies"].extend([
                {"label": "더 듣고 싶어요", "action": "message", "messageText": "더 자세히"},
                {"label": "조언 부탁해요", "action": "message", "messageText": "조언 부탁"}
            ])
        
        # Groq 복구 시 표시할 버튼 (현재는 숨김)
        # if groq_client and claude_client and not GROQ_DISABLED: 
        #     response_data["template"]["quickReplies"].append(
        #         {"label": "🔄 상담 방식 변경", "action": "message", "messageText": "상담사변경"}
        #     )
        
        # 대화 초기화 옵션 (5회 이상 대화 시)
        if len(session['conversation']) > 5:
            response_data["template"]["quickReplies"].append(
                {"label": "🔄 새 상담 시작", "action": "message", "messageText": "새상담"}
            )

        requests.post(callback_url, json=response_data, timeout=10)
        print(f"✅ 콜백 성공")
    except Exception as e:
        print(f"🚨 콜백 오류: {e}")
        error_response = {
            "version": "2.0", 
            "template": {
                "outputs": [{"simpleText": {"text": "죄송합니다. 잠시 후 다시 시도해주세요."}}]
            }
        }
        try:
            requests.post(callback_url, json=error_response, timeout=10)
        except:
            pass


@app.route('/kakao', methods=['POST'])
def kakao_chatbot():
    """카카오톡 서버로부터 요청을 받아 처리하는 메인 함수"""
    kakao_request = request.get_json()
    print(f"[카카오 요청] 수신")

    user_request_data = kakao_request.get('userRequest', {})
    user_id = user_request_data.get('user', {}).get('id', 'unknown')
    user_message = user_request_data.get('utterance', '')
    callback_url = user_request_data.get('callbackUrl')

    print(f"[사용자] {user_message[:50]}")

    # 새 상담 시작
    if user_message == '새상담':
        user_sessions[user_id] = {
            'model': 'claude',  # Claude를 기본으로
            'conversation': [],
            'last_activity': datetime.now(),
            'counseling_stage': 'initial',
            'key_topics': []
        }
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "🌟 새로운 상담을 시작합니다.\n\n어떤 마음으로 오셨나요?"}}],
                "quickReplies": []  # Groq 비활성화로 버튼 제거
            }
        })

    # 즉시 응답이 필요한 경우
    if user_message in ['안녕하세요', '시작', '상담시작', '처음', 'start', '상담사변경', '모델변경', '변경'] or user_message.endswith('선택'):
        print("즉시 응답 처리")
        
        if user_message in ['안녕하세요', '시작', '상담시작', '처음', 'start']:
            session = get_user_session(user_id)
            session['counseling_stage'] = 'initial'
            session['model'] = 'claude'  # Claude로 고정
            
            # Groq 비활성화 중이므로 모드 선택 없이 바로 시작
            return jsonify({
                "version": "2.0",
                "template": {
                    "outputs": [{"simpleText": {"text": "🙏 안녕하세요! 성경 말씀 상담 챗봇입니다.\n\n무엇을 도와드릴까요?"}}],
                    "quickReplies": []
                }
            })

        elif user_message in ['상담사변경', '모델변경', '변경']:
            # Groq 비활성화 중 안내
            return jsonify({
                "version": "2.0",
                "template": {
                    "outputs": [{"simpleText": {"text": "현재 시스템 점검 중으로 깊이있는 상담만 가능합니다.\n\n무엇을 도와드릴까요?"}}],
                    "quickReplies": []
                }
            })

        elif user_message == "빠른상담선택":
            session = get_user_session(user_id)
            session['model'] = 'claude'  # Claude 사용 (빠른 모드)
            return jsonify({"version": "2.0", "template": {"outputs": [{"simpleText": {"text": "⚡ 상담을 시작합니다.\n\n무엇을 도와드릴까요?"}}]}})

        elif user_message == "정밀상담선택":
            session = get_user_session(user_id)
            session['model'] = 'claude'
            return jsonify({"version": "2.0", "template": {"outputs": [{"simpleText": {"text": "💎 깊이있는 상담을 시작합니다.\n\n마음을 나눠주세요."}}]}})
        
        elif user_message == "상담시작하기":
            session = get_user_session(user_id)
            session['model'] = 'claude'
            return jsonify({"version": "2.0", "template": {"outputs": [{"simpleText": {"text": "🙏 편하게 말씀해주세요."}}]}})
    
    # AI 상담 처리 (백그라운드)
    else:
        session = get_user_session(user_id)
        if not session.get('model'):
            session['model'] = 'claude'  # 기본값 설정

        if callback_url:
            print(f"콜백 처리 시작")
            thread = threading.Thread(target=process_and_callback, args=(user_id, user_message, callback_url))
            thread.daemon = True
            thread.start()
            return jsonify({"version": "2.0", "useCallback": True})
        else:
            print("⚠️ callbackUrl 없음")
            # 간단한 즉시 응답
            session = get_user_session(user_id)
            add_to_conversation(user_id, 'user', user_message)
            ai_response = generate_claude_response(user_message, search_bible(user_message.split()), user_id, quick_mode=True)
            ai_response = safe_truncate(ai_response, 750)  # 안전 제한
            add_to_conversation(user_id, 'assistant', ai_response)
            return jsonify({"version": "2.0", "template": {"outputs": [{"simpleText": {"text": ai_response}}]}})


@app.route('/health', methods=['GET'])
def health_check():
    active_users = len([s for s in user_sessions.values() if datetime.now() - s['last_activity'] < timedelta(minutes=30)])
    return jsonify({
        "status": "healthy", 
        "groq_api": "disabled (API key issue)" if GROQ_DISABLED else ("connected" if groq_client else "not configured"), 
        "claude_api": "connected" if claude_client else "not configured", 
        "bible_data": f"{len(BIBLE_DATA)} verses loaded" if BIBLE_DATA else "not loaded",
        "active_sessions": active_users
    })


@app.route('/', methods=['GET'])
def home():
    groq_status = "⚠️ Groq 임시 비활성화 (API 키 문제)" if GROQ_DISABLED else ("✅ Groq 정상" if groq_client else "❌ Groq 미설정")
    
    return f"""<html><head><title>성경 상담 챗봇 API</title><style>body{{font-family:Arial,sans-serif;max-width:800px;margin:50px auto;padding:20px}}h1{{color:#333}}.status{{background:#f0f0f0;padding:15px;border-radius:5px;margin:20px 0}}.feature{{background:#e8f8e8;padding:10px;margin:5px 0;border-left:3px solid #4CAF50}}code{{background:#f4f4f4;padding:2px 5px;border-radius:3px}}.warning{{background:#fff3cd;padding:10px;margin:10px 0;border-left:3px solid #ffc107}}.error{{background:#f8d7da;padding:10px;margin:10px 0;border-left:3px solid #dc3545}}</style></head><body><h1>🙏 성경 상담 챗봇 API v2.1</h1><div class=status><h2>서비스 상태</h2><p>✅ 서버 정상 작동 중</p><p>📖 카카오톡 채널과 연동됨</p></div><div class=error><h3>⚠️ 시스템 알림</h3><p>{groq_status}</p><p>✅ Claude API 정상 작동 중</p><p>• 모든 상담은 Claude로 처리됩니다</p></div><div class=feature><h3>✨ 주요 기능</h3><p>• 대화 기억 기능</p><p>• 단계별 상담 진행</p><p>• 응답 길이 최적화 (750자)</p><p>• 30분 세션 유지</p></div></body></html>"""


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
