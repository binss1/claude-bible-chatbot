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
    
    # 사용자 입력에서 키워드 추출
    expanded_keywords = []
    for keyword in keywords:
        expanded_keywords.append(keyword)
        # 관련 키워드 자동 추가
        if "외로" in keyword or "혼자" in keyword:
            expanded_keywords.extend(["외로", "고독", "혼자", "홀로"])
        elif "힘들" in keyword or "어려" in keyword:
            expanded_keywords.extend(["힘들", "어려움", "고난", "시련"])
        elif "감사" in keyword:
            expanded_keywords.extend(["감사", "감사하", "은혜"])
        elif "사랑" in keyword:
            expanded_keywords.extend(["사랑", "사랑하"])
        elif "기도" in keyword:
            expanded_keywords.extend(["기도", "간구"])
        elif "배우자" in keyword or "부부" in keyword or "결혼" in keyword:
            expanded_keywords.extend(["사랑", "인내", "용서", "화목"])
        elif "갈등" in keyword or "다툼" in keyword:
            expanded_keywords.extend(["화평", "용서", "사랑", "인내"])
    
    # 중복 제거
    expanded_keywords = list(set(expanded_keywords))
    
    for verse, content in BIBLE_DATA.items():
        if any(keyword in content for keyword in expanded_keywords):
            search_results.append(f"{verse}: {content}")
            if len(search_results) >= 5:
                break
    
    return search_results


def generate_groq_response(user_message, bible_verses):
    """Groq AI를 사용하여 응답 생성"""
    if not groq_client:
        return "Groq API가 설정되지 않았습니다."
    
    verses_text = "\n".join(bible_verses) if bible_verses else "관련 성경 구절을 찾지 못했습니다."
    
    # 한국어 응답을 명확히 지시하는 프롬프트
    prompt = f"""당신은 한국어를 사용하는 따뜻하고 공감적인 기독교 상담사입니다.
반드시 한국어로만 응답해주세요. 영어나 다른 언어는 사용하지 마세요.

아래 한국어 성경 구절을 참고하여 사용자의 고민에 대해 한국어로 위로와 희망의 메시지를 전해주세요.

[참고 성경 구절]
{verses_text}

[사용자 메시지]
{user_message}

[응답 지침]
- 반드시 한국어로만 응답하세요
- 따뜻하고 공감적인 어조로 응답하세요
- 성경 구절을 자연스럽게 인용하세요
- 실질적인 위로와 격려를 제공하세요
- 마지막에 짧은 기도나 축복의 말을 추가하세요
- 이모지는 최소한으로 사용하세요

Remember: Your entire response must be in Korean language only. Do not use English."""

    try:
        # 사용 가능한 모델들을 순서대로 시도
        models = [
            "llama3-70b-8192",
            "llama3-8b-8192", 
            "mixtral-8x7b-32768"
        ]
        
        for model in models:
            try:
                response = groq_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a Korean Christian counselor. You must respond only in Korean language. 당신은 한국어로만 대답하는 기독교 상담사입니다."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,  # 토큰 수 줄여서 응답 속도 향상
                    temperature=0.7,
                    timeout=4.0  # 4초 타임아웃 설정
                )
                print(f"✅ Groq 모델 {model} 사용 중")
                return response.choices[0].message.content
            except Exception as model_error:
                print(f"⚠️ {model} 모델 실패: {model_error}")
                continue
        
        # 모든 모델이 실패한 경우
        return "죄송합니다. 현재 AI 서비스에 일시적인 문제가 있습니다. 잠시 후 다시 시도해주세요."
        
    except Exception as e:
        print(f"Groq API 오류: {e}")
        return "죄송합니다. 잠시 후 다시 시도해주세요."


def generate_claude_response(user_message, bible_verses):
    """Claude AI를 사용하여 응답 생성"""
    if not claude_client:
        return "Claude API가 설정되지 않았습니다."
    
    verses_text = "\n".join(bible_verses) if bible_verses else "관련 성경 구절을 찾지 못했습니다."
    
    prompt = f"""당신은 깊이 있고 지혜로운 기독교 상담 전문가입니다.
반드시 한국어로 응답해주세요.

아래 성경 구절을 깊이 있게 해석하여 사용자의 상황에 맞는 통찰력 있는 조언을 제공해주세요.

[참고 성경 구절]
{verses_text}

[사용자 메시지]
{user_message}

[응답 지침]
- 반드시 한국어로 응답
- 성경적 원리를 깊이 있게 설명
- 사용자의 감정을 세심하게 이해하고 공감
- 실제 삶에 적용 가능한 구체적 조언 제공
- 필요시 관련된 다른 성경 구절도 언급
- 희망적이면서도 현실적인 관점 제시
- 마지막에 개인화된 기도 제안"""

    try:
        # Claude는 기본적으로 빠르므로 타임아웃 걱정 없음
        response = claude_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=500,  # 토큰 수 줄여서 응답 속도 향상
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
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
    print(f"[카카오 요청] {request.get_json()}")
    
    # API 키가 하나도 설정되지 않았다면 에러 메시지
    if not groq_client and not claude_client:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{
                    "simpleText": {
                        "text": "⚠️ AI API가 설정되지 않았습니다. 관리자에게 문의해주세요."
                    }
                }]
            }
        })
    
    kakao_request = request.get_json()
    user_id = kakao_request.get('userRequest', {}).get('user', {}).get('id', 'unknown')
    user_message = kakao_request.get('userRequest', {}).get('utterance', '')
    
    print(f"[사용자 메시지] {user_message}")
    
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
                        "text": "⚡ 빠른 상담 모드로 설정되었습니다.\n\n무엇이든 편하게 말씀해주세요. 성경 말씀으로 위로해드리겠습니다."
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
                        "text": "💎 깊이있는 상담 모드로 설정되었습니다.\n\n고민을 자세히 들려주세요. 성경의 지혜로 깊이 있는 상담을 도와드리겠습니다."
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
                        "text": "🙏 무엇이든 편하게 말씀해주세요. 성경 말씀으로 위로해드리겠습니다."
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
        # 타임아웃 방지를 위해 빠른 응답 처리
        try:
            # 사용자의 선택된 모델 확인 (기본값: groq)
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
            
            # 키워드가 없으면 기본 키워드로 검색
            if not bible_verses:
                default_keywords = ["사랑", "위로", "평안", "믿음", "소망", "기쁨"]
                bible_verses = search_bible(default_keywords)
            
            # AI 응답 생성
            print(f"[선택된 모델] {selected_model}")
            
            if selected_model == 'claude' and claude_client:
                ai_response = generate_claude_response(user_message, bible_verses)
            else:
                ai_response = generate_groq_response(user_message, bible_verses)
            
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
            
            return jsonify(response_json)
            
        except Exception as e:
            print(f"[오류] {e}")
            # 오류 발생 시 빠른 기본 응답
            return jsonify({
                "version": "2.0",
                "template": {
                    "outputs": [{
                        "simpleText": {
                            "text": "잠시 문제가 발생했습니다. 다시 한 번 말씀해주세요. 🙏"
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
            </div>
            <div class="endpoint">
                <h3>API Endpoints</h3>
                <p><code>POST /kakao</code> - 카카오톡 챗봇 요청 처리</p>
                <p><code>GET /health</code> - 서버 상태 확인</p>
            </div>
        </body>
    </html>
    """


# 서버 슬립 방지 (선택사항)
def keep_alive():
    """Render 무료 플랜 슬립 방지"""
    while True:
        time.sleep(600)  # 10분마다
        try:
            # 자기 자신에게 헬스체크 요청
            if os.environ.get('RENDER_EXTERNAL_URL'):
                url = f"{os.environ.get('RENDER_EXTERNAL_URL')}/health"
                requests.get(url, timeout=5)
                print(f"[Keep-Alive] 헬스체크 완료")
        except:
            pass

# 백그라운드 스레드로 keep_alive 실행 (선택사항)
# 주석 해제하면 서버가 자동으로 깨어있음 유지
# threading.Thread(target=keep_alive, daemon=True).start()


if __name__ == '__main__':
    # 개발 서버 실행 (프로덕션에서는 gunicorn 사용)
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
