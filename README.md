# D-Order Backend v3
D-Order 백엔드 레포입니다.
---

## 🚀 빠른 시작

### 요구사항

- Python 3.12
- Docker & Docker Compose
- Git

### local 개발 시 Docker Compose로 데이터베이스 실행

```bash
# 프로젝트 루트 경로에서 실행
cd ..
docker-compose -f docker-compose.local.yml up -d
```

상태 확인:
```bash
docker-compose -f docker-compose.local.yml ps
```


###  python 가상환경 생성 및 활성화

```bash
cd django
python3.12 -m venv venv # 3.12

source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows
```

### 의존성 설치

```bash
pip install -r requirements.txt
```

### DB 마이그레이션 실행

```bash
cd django
python manage.py migrate
```

### 서버 실행

## Django
```bash
python manage.py runserver
```

서버가 `http://localhost:8000`에서 실행됩니다.

## Spring

작성바람~~~
---

## 📁 프로젝트 구조

```
2026-d-order-backend-v3/
├── .env                          # 환경 변수 (Django + Docker) notion 참조
├── README.md                     # 이 파일
├── docker-compose.local.yml      # 로컬 개발 환경시 postgre + redis 컨테이너 만들기
│
├── django/
│   ├── manage.py                 
│   ├── requirements.txt          # Python 의존성 파일들
│   ├── apps/
│   └── project/                  # Django 프로젝트 폴더
└── Spring/
```

---

## 🔧 환경 변수 설정

`.env` notion 참고

---

## 🐳 Docker Compose 명령어

### 컨테이너 시작

```bash
docker-compose -f docker-compose.local.yml up -d
```
하나만 실행
```bash
docker-compose -f django/docker-compose.local.yml up -d postgres
docker-compose -f django/docker-compose.local.yml up -d redis
```
### 컨테이너 상태 확인

```bash
docker-compose -f docker-compose.local.yml ps
```
### 컨테이너 종료
```bash
docker-compose -f django/docker-compose.local.yml down

```
### 로그 확인

```bash
# 모든 로그
docker-compose -f docker-compose.local.yml logs -f

# PostgreSQL만
docker-compose -f docker-compose.local.yml logs postgres

# Redis만
docker-compose -f docker-compose.local.yml logs redis
```

### 컨테이너 중지

```bash
docker-compose -f docker-compose.local.yml down # db 데이터는 남음
docker-compose -f django/docker-compose.local.yml down -v # -v 옵션이 붙으면 db 데이터도 삭제
```


---

