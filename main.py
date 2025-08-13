import os
import json
from flask import Flask, request, jsonify
import threading
import time
import requests

# Flask 앱을 초기화합니다.
app = Flask(__name__)

# --- 서버가 시작될 때 한 번만 실행되는 부분 ---

# API 키를 환경 변수에서 불러옵니다.
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY')
BIBLE_DATA = {}  # 성경 데이터를 저장할 변수

# 사용자별 선택 모델 저장 (메모리 기반)
user_sessions = {}

# Groq 클라이언트 초기화
groq_client = None
if GROQ_API_KEY:
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_API_KEY)
        print("✅ Groq API 키가 성공적으로 설정되었습니다.")
    except Exception as e:
        print(f"⚠️ Groq 클라이언트 초기화 실패: {e}")
        groq_client = None
else:
    print("⚠️ GROQ_API_KEY 환경 변수가 설정되지 않았습니다.")

# Claude 클라이언트 초기화
claude_client = None
if CLAUDE_API_KEY:
    try:
        from anthropic import Anthropic
        claude_client = Anthropic(api_key=CLAUDE_API_KEY)
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


# --- 실제 요청을 처리하는 함수 부분 ---

def search_bible(keywords):
    """성경 데이터에서 관련 구절을 검색하는 함수"""
    search_results = []
    if not BIBLE_DATA:
        return search_results
    
    # 검색어를 확장
    if isinstance(keywords, str):
        keywords = [keywords]
    
    # 사용자 입력에서 키워드 추출 및 확장
    expanded_keywords = []
    for keyword in keywords:
        expanded_keywords.append(keyword)
        # 특정 키워드에 대한 추가 관련어
        if "외로" in keyword or "혼자" in keyword:
            expanded_keywords.extend(["외로", "고독", "혼자", "홀로", "위로"])
        elif "힘들" in keyword or "어려" in keyword:
            expanded_keywords.extend(["힘들", "어려움", "고난", "시련", "인내"])
        elif "감사" in keyword:
            expanded_keywords.extend(["감사", "감사하", "은혜", "축복"])
        elif "사랑" in keyword:
            expanded_keywords.extend(["사랑", "사랑하", "아끼", "귀하"])
        elif "기도" in keyword:
            expanded_keywords.extend(["기도", "간구", "부르짖"])
        elif "배우자" in keyword or "부부" in keyword or "결혼" in keyword:
            expanded_keywords.extend(["사랑", "인내", "용서", "화목", "아내", "남편"])
        elif "갈등" in keyword or "다툼" in keyword:
            expanded_keywords.extend(["화평", "용서", "사랑", "인내", "화목"])
        elif "두려" in keyword or "무서" in keyword:
            expanded_keywords.extend(["두려", "무서", "담대", "용기"])
        elif "죽" in keyword or "죽음" in keyword:
            expanded_keywords.extend(["죽음", "생명", "영생", "부활"])
    
    # 중복 제거
    expanded_keywords = list(set(expanded_keywords))
    
    # 키워드가 너무 적으면 일반적인 축복 구절 추가
    if len(expanded_keywords) < 3:
        expanded_keywords.extend(["사랑", "평안", "소망", "믿음"])
    
    # 성경 구절 검색 (최대 3개로 제한)
    for verse, content in BIBLE_DATA.items():
        if any(keyword in content for keyword in expanded_keywords):
            search_results.append(f"{verse}: {content}")
            if len(search_results) >= 3:  # 5개에서 3개로 줄임
                break
    
    # 검색 결과가 없으면 기본 구절 제공
    if not search_results:
        default_verses = [
            verse for verse, content in BIBLE_DATA.items() 
            if any(word in content for word in ["사랑", "위로", "평안"])
        ][:2]
        search_results = [f"{verse}: {BIBLE_DATA[verse]}" for verse in default_verses]
    
    return search_results


def generate_groq_response(user_message, bible_verses):
    """Groq AI를 사용하여 응답 생성"""
    if not groq_client:
        return "Groq API가 설정되지 않았습니다."
    
    verses_text = "\n".join(bible_verses[:2]) if bible_verses else ""  # 2개만 사용
    
    # 짧고 간결한 프롬프트
    prompt = f"""한국어 기독교 상담사입니다.

[성경]
{verses_text}

[상담요청]
{user_message}

짧고 따뜻하게 위로하고 실질적 조언을 300자 이내로 전하세요. 마지막에 한 줄 기도 추가."""

    try:
        # 사용 가능한 모델들을 순서대로 시도
        models = [
            "llama3-8b-8192",  # 더 가벼운 모델 먼저
            "llama3-70b-8192",
            "mixtral-8x7b-32768"
        ]
        
        for model in models:
            try:
                response = groq_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "한국어로만 응답. 300자 이내로 간결하게."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=250,  # 더 줄임
                    temperature=0.7
                )
                result = response.choices[0].message.content
                # 응답 길이 체크 및 자르기
                if len(result) > 900:
                    result = result[:897] + "..."
                print(f"✅ Groq 응답 길이: {len(result)}자")
                return result
            except Exception as model_error:
                print(f"⚠️ {model} 모델 실패: {model_error}")
                continue
        
        return "죄송합니다. 잠시 후 다시 시도해주세요."
        
    except Exception as e:
        print(f"Groq API 오류: {e}")
        return "죄송합니다. 잠시 후 다시 시도해주세요."


def generate_claude_response(user_message, bible_verses):
    """Claude AI를 사용하여 응답 생성"""
    if not claude_client:
        return "Claude API가 설정되지 않았습니다."
    
    verses_text = "\n".join(bible_verses[:2]) if bible_verses else ""  # 2개만 사용
    
    # 매우 짧고 간결한 프롬프트
    prompt = f"""한국어 기독교 상담.

성경: {verses_text}

요청: {user_message}

300자 이내로 따뜻한 위로와 실용적 조언. 마지막에 한 줄 기도."""

    try:
        response = claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=200,  # 대폭 감소
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        result = response.content[0].text
        
        # 응답 길이 체크 및 자르기 (카카오톡 제한)
        if len(result) > 900:
            result = result[:897] + "..."
        
        print(f"✅ Claude 응답 길이: {len(result)}자")
        return result
        
    except Exception as e:
        print(f"Claude API 오류: {e}")
        # Claude 실패 시 Groq로 폴백
        if groq_client:
            print("Claude 실패, Groq로 전환")
            return generate_groq_response(user_message, bible_verses)
        return "죄송합니다. 잠시 후 다시 시도해주세요."


# 카카오톡 요청을 처리할 URL 경로를 설정합니다.
@app.route('/kakao', methods=['POST'])
def kakao_chatbot():
    """카카오톡 서버로부터 요청을 받아 AI 답변을 생성하고 반환하는 함수"""
    
    # 요청 로깅
    kakao_request = request.get_json()
    user_id = kakao_request.get('userRequest', {}).get('user', {}).get('id', 'unknown')
    user_message = kakao_request.get('userRequest', {}).get('utterance', '')
    
    print(f"[사용자 {user_id[:8]}...] {user_message}")
    
    # API 키가 하나도 설정되지 않았다면 에러 메시지
    if not groq_client and not claude_client:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{
                    "simpleText": {
                        "text": "⚠️ AI API가 설정되지 않았습니다."
                    }
                }]
            }
        })
    
    # 시작 메시지 처리
    if user_message in ['안녕하세요', '시작', '상담시작', '처음', 'start']:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{
                    "simpleText": {
                        "text": "🙏 안녕하세요! 성경 말씀 상담 챗봇입니다.\n\n어떤 방식의 상담을 원하시나요?"
                    }
                }],
                "quickReplies": [
                    {
                        "label": "🚀 빠른 상담",
                        "action": "message",
                        "messageText": "빠른상담선택"
                    },
                    {
                        "label": "💎 깊이있는 상담",
                        "action": "message",
                        "messageText": "정밀상담선택"
                    }
                ] if groq_client and claude_client else [
                    {
                        "label": "상담 시작하기",
                        "action": "message",
                        "messageText": "상담시작하기"
                    }
                ]
            }
        })
    
    # 모델 선택 처리
    elif user_message == "빠른상담선택" and groq_client:
        user_sessions[user_id] = {'model': 'groq'}
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{
                    "simpleText": {
                        "text": "⚡ 빠른 상담 모드로 설정되었습니다.\n\n무엇이든 편하게 말씀해주세요."
                    }
                }]
            }
        })
    
    elif user_message == "정밀상담선택" and claude_client:
        user_sessions[user_id] = {'model': 'claude'}
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{
                    "simpleText": {
                        "text": "💎 깊이있는 상담 모드로 설정되었습니다.\n\n고민을 자세히 들려주세요."
                    }
                }]
            }
        })
    
    elif user_message == "상담시작하기":
        # 단일 모델만 있는 경우
        if groq_client and not claude_client:
            user_sessions[user_id] = {'model': 'groq'}
        elif claude_client and not groq_client:
            user_sessions[user_id] = {'model': 'claude'}
        
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{
                    "simpleText": {
                        "text": "🙏 무엇이든 편하게 말씀해주세요."
                    }
                }]
            }
        })
    
    # 상담사 변경 요청
    elif user_message in ['상담사변경', '모델변경', '변경']:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{
                    "simpleText": {
                        "text": "상담 방식을 변경하시겠습니까?"
                    }
                }],
                "quickReplies": [
                    {
                        "label": "🚀 빠른 상담",
                        "action": "message",
                        "messageText": "빠른상담선택"
                    },
                    {
                        "label": "💎 깊이있는 상담",
                        "action": "message",
                        "messageText": "정밀상담선택"
                    }
                ] if groq_client and claude_client else []
            }
        })
    
    # 실제 상담 처리
    else:
        try:
            # 사용자의 선택된 모델 확인
            selected_model = user_sessions.get(user_id, {}).get('model')
            
            # 모델이 선택되지 않았거나 사용 불가능한 경우 자동 선택
            if not selected_model:
                if groq_client:
                    selected_model = 'groq'
                elif claude_client:
                    selected_model = 'claude'
                else:
                    return jsonify({
                        "version": "2.0",
                        "template": {
                            "outputs": [{
                                "simpleText": {
                                    "text": "⚠️ 사용 가능한 AI 모델이 없습니다."
                                }
                            }]
                        }
                    })
            
            # 성경 구절 검색
            keywords = user_message.split()
            bible_verses = search_bible(keywords)
            
            # AI 응답 생성
            print(f"[모델: {selected_model}]")
            
            if selected_model == 'claude' and claude_client:
                ai_response = generate_claude_response(user_message, bible_verses)
            else:
                ai_response = generate_groq_response(user_message, bible_verses)
            
            # 응답 길이 최종 체크
            if len(ai_response) > 950:
                ai_response = ai_response[:947] + "..."
            
            # 카카오톡 응답 생성
            response_json = {
                "version": "2.0",
                "template": {
                    "outputs": [{
                        "simpleText": {
                            "text": ai_response
                        }
                    }],
                    "quickReplies": []
                }
            }
            
            # 두 모델이 모두 사용 가능한 경우에만 변경 버튼 추가
            if groq_client and claude_client:
                response_json["template"]["quickReplies"].append({
                    "label": "🔄 상담 방식 변경",
                    "action": "message",
                    "messageText": "상담사변경"
                })
            
            print(f"[응답 완료] {len(ai_response)}자")
            return jsonify(response_json)
            
        except Exception as e:
            print(f"[오류] {e}")
            return jsonify({
                "version": "2.0",
                "template": {
                    "outputs": [{
                        "simpleText": {
                            "text": "잠시 문제가 발생했습니다. 다시 말씀해주세요. 🙏"
                        }
                    }]
                }
            })


# 헬스체크 엔드포인트 (Render.com 상태 확인용)
@app.route('/health', methods=['GET'])
def health_check():
    """서버 상태를 확인하는 엔드포인트"""
    status = {
        "status": "healthy",
        "groq_api": "connected" if groq_client else "not configured",
        "claude_api": "connected" if claude_client else "not configured",
        "bible_data": f"{len(BIBLE_DATA)} verses loaded" if BIBLE_DATA else "not loaded"
    }
    return jsonify(status)


# 루트 경로 처리
@app.route('/', methods=['GET'])
def home():
    """홈페이지"""
    return """
    <html>
        <head>
            <title>성경 상담 챗봇 API</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
                h1 { color: #333; }
                .status { background: #f0f0f0; padding: 15px; border-radius: 5px; margin: 20px 0; }
                .endpoint { background: #e8f4f8; padding: 10px; margin: 10px 0; border-left: 3px solid #007bff; }
                code { background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }
            </style>
        </head>
        <body>
            <h1>🙏 성경 상담 챗봇 API</h1>
            <div class="status">
                <h2>서비스 상태</h2>
                <p>✅ 서버 정상 작동 중</p>
                <p>📖 카카오톡 채널과 연동되어 있습니다.</p>
                <p>🔗 서비스 URL: https://claude-bible-chatbot.onrender.com</p>
            </div>
            <div class="endpoint">
                <h3>API Endpoints</h3>
                <p><code>POST /kakao</code> - 카카오톡 챗봇 요청 처리</p>
                <p><code>GET /health</code> - 서버 상태 확인</p>
            </div>
        </body>
    </html>
    """


# 서버 슬립 방지
def keep_alive():
    """Render 무료 플랜 슬립 방지"""
    while True:
        time.sleep(600)  # 10분마다
        try:
            # 자기 자신에게 헬스체크 요청
            url = "https://claude-bible-chatbot.onrender.com/health"
            requests.get(url, timeout=5)
            print(f"[Keep-Alive] 헬스체크 완료")
        except:
            pass

# 백그라운드 스레드로 keep_alive 실행 - 서버 항상 깨어있음
threading.Thread(target=keep_alive, daemon=True).start()
print("🔄 Keep-Alive 스레드 시작 - 서버가 항상 깨어있습니다")


if __name__ == '__main__':
    # 개발 서버 실행 (프로덕션에서는 gunicorn 사용)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
