# 🙏 성경 상담 카카오톡 챗봇

Claude와 Groq AI를 활용한 듀얼 모델 성경 상담 챗봇입니다.

## ✨ 주요 기능

- **듀얼 AI 모델**: Groq (빠른 응답) & Claude (깊이 있는 상담)
- **사용자 선택**: 상담 시작 시 AI 모델 선택 가능
- **성경 구절 검색**: 사용자 메시지에 맞는 성경 구절 자동 검색
- **카카오톡 통합**: 카카오톡 채널과 완벽 연동

## 🚀 배포 방법 (Render.com)

### 1. 사전 준비
- [Groq API Key](https://console.groq.com) 발급
- [Claude API Key](https://console.anthropic.com) 발급 (선택사항)
- [Render.com](https://render.com) 계정 (GitHub 로그인 추천)

### 2. Render.com 배포

1. [Render Dashboard](https://dashboard.render.com)에 접속
2. "New +" → "Web Service" 클릭
3. GitHub 저장소 연결 (이 저장소 선택)
4. 설정 확인:
   - **Name**: kakao-bible-chatbot
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn main:app`
5. 환경변수 설정:
   - `GROQ_API_KEY`: Groq API 키 입력
   - `CLAUDE_API_KEY`: Claude API 키 입력 (선택)
6. "Create Web Service" 클릭

### 3. 카카오 채널 설정

1. [카카오 비즈니스](https://business.kakao.com) 접속
2. 채널 관리자센터 → 챗봇 설정
3. 스킬 등록:
   - 스킬 이름: AI상담봇
   - URL: `https://your-app.onrender.com/kakao`
4. 시나리오 설정:
   - 폴백 블록 → 등록한 스킬 연결

## 📁 프로젝트 구조

```
claude-bible-chatbot/
├── main.py           # Flask 서버 메인 파일
├── bible.json        # 성경 구절 데이터
├── requirements.txt  # Python 패키지 목록
├── render.yaml       # Render 배포 설정
├── .env.example      # 환경변수 예시
└── README.md         # 프로젝트 설명
```

## 🔧 로컬 개발 환경

```bash
# 1. 저장소 클론
git clone https://github.com/binss1/claude-bible-chatbot.git
cd claude-bible-chatbot

# 2. 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 패키지 설치
pip install -r requirements.txt

# 4. 환경변수 설정
cp .env.example .env
# .env 파일 편집하여 API 키 입력

# 5. 서버 실행
python main.py
```

## 📝 사용 예시

### 대화 시작
- 사용자: "안녕하세요"
- 챗봇: AI 모델 선택 버튼 제공

### 빠른 상담 (Groq)
- 응답 속도: 매우 빠름 (0.5초 이내)
- 적합한 경우: 일반적인 위로, 간단한 상담

### 깊이있는 상담 (Claude)
- 응답 속도: 보통 (2-3초)
- 적합한 경우: 복잡한 고민, 깊이 있는 신앙 상담

## 🛠 API 엔드포인트

- `POST /kakao` - 카카오톡 메시지 처리
- `GET /health` - 서버 상태 확인
- `GET /` - 서비스 정보 페이지

## 📖 성경 데이터 추가

`bible.json` 파일에 성경 구절을 추가할 수 있습니다:

```json
{
  "성경책 장:절": "구절 내용",
  "시편 23:1": "여호와는 나의 목자시니..."
}
```

## 🤝 기여하기

1. Fork 이 저장소
2. 새 기능 브랜치 생성 (`git checkout -b feature/AmazingFeature`)
3. 변경사항 커밋 (`git commit -m 'Add some AmazingFeature'`)
4. 브랜치에 푸시 (`git push origin feature/AmazingFeature`)
5. Pull Request 생성

## 📄 라이센스

MIT License

## 💬 문의

이슈나 질문이 있으시면 [Issues](https://github.com/binss1/claude-bible-chatbot/issues) 페이지에 등록해주세요.

---

Made with ❤️ for spreading God's word through AI
