# 📑 목차

- [📑 목차](#-목차)
- [🔥🔥🔥 이거 대체 왜 함? 🔥🔥🔥](#-이거-대체-왜-함-)
    - [✨✨ 초기세팅 귀찮더라도 딱 한번만 해주십쇼 ✨✨](#-초기세팅-귀찮더라도-딱-한번만-해주십쇼-)
- [🔧 환경 변수 설정](#-환경-변수-설정)
- [🚀 빠른 시작](#-빠른-시작)
    - [요구사항](#요구사항)
    - [설치 가이드](#설치-가이드)
    - [시스템 요구사항](#시스템-요구사항)
    - [1. WSL 2 설치 (필수)](#1-wsl-2-설치-필수)
    - [2. Docker Desktop 다운로드 및 설치](#2-docker-desktop-다운로드-및-설치)
    - [3. 설치 확인](#3-설치-확인)
    - [문제 해결](#문제-해결)
    - [참고 자료](#참고-자료)
    - [2. 설치 확인](#2-설치-확인)
    - [문제 해결](#문제-해결-1)
    - [Homebrew + Colima로 설치 (Docker Desktop 대안)](#homebrew--colima로-설치-docker-desktop-대안)
      - [1. Homebrew 설치 **(없는 경우)**](#1-homebrew-설치-없는-경우)
      - [2. Docker CLI 및 Colima 설치](#2-docker-cli-및-colima-설치)
      - [3. Colima 시작](#3-colima-시작)
      - [4. 설치 확인](#4-설치-확인)
      - [Colima 명령어](#colima-명령어)
      - [문제 해결](#문제-해결-2)
  - [local 개발 시 Docker Compose로 postgresql + redis 실행](#local-개발-시-docker-compose로-postgresql--redis-실행)
  - [python 가상환경 생성 및 활성화](#python-가상환경-생성-및-활성화)
  - [의존성 설치](#의존성-설치)
  - [DB 마이그레이션 실행](#db-마이그레이션-실행)
- [서버 실행](#서버-실행)
  - [Django](#django)
  - [Spring](#spring)
- [🐳 Docker Compose 명령어](#-docker-compose-명령어)
    - [컨테이너 시작](#컨테이너-시작)
    - [컨테이너 상태 확인](#컨테이너-상태-확인)
    - [컨테이너 종료](#컨테이너-종료)
    - [로그 확인](#로그-확인)
    - [컨테이너 중지](#컨테이너-중지)

---

# 🔥🔥🔥 이거 대체 왜 함? 🔥🔥🔥

현 프로젝트는 postgresql과 reids를 두 개의 어플리케이션이 공유하고 있는 구조입니다. \
django 웹소켓을 시스템 메모리에서만 사용하면 spring에서 접근이 불가능해요.\
postgresql도 django에 강하게 묶여있어서 django를 이용해서 migration을 해줘야 합니다.\
개발하는 입장에서 **프로덕션과 개발 환경의 괴리가 너무 커서 줄이기 위해서 로컬에선 최소한(postgres+redis)만 docker로 올려서 사용할 수 있도록 한겁니다.**\
로컬에서 in-memory로 그냥 돌리면 웹소켓 내용을 spring에서 못 확인해요 허허

### ✨✨ 초기세팅 귀찮더라도 딱 한번만 해주십쇼 ✨✨

# 🔧 환경 변수 설정

Notion 'BE space'>'info' 참고

프로젝트 루트 경로에 '.env' 파일 생성하여 넣기.

# 🚀 빠른 시작

### 요구사항

- Python 3.12
- Docker & Docker Compose
- Git

### 설치 가이드

<details>
<summary>Windows docker 설치</summary>

   ### 시스템 요구사항

   - WSL 2 기능 활성화 필요
   - **BIOS에서 가상화 활성화 필요** [참고](https://m.blog.naver.com/presiddd/222699352932)

   ### 1. WSL 2 설치 (필수)

   PowerShell을 **관리자 권한**으로 실행 후:

   ```powershell
   # WSL 설치
   wsl --install

   # 재부팅 필요
   ```

   재부팅 후 WSL 버전 확인:

   ```powershell
   wsl --list --verbose
   ```

   ### 2. Docker Desktop 다운로드 및 설치

   1. [Docker Desktop 공식 사이트](https://www.docker.com/products/docker-desktop/)에서 다운로드
   2. `Docker Desktop Installer.exe` 실행
   3. 설치 옵션에서 **"Use WSL 2 instead of Hyper-V"** 선택
   4. 설치 완료 후 **재부팅**

   ### 3. 설치 확인

   PowerShell 또는 CMD에서 실행:

   ```bash
   docker --version
   docker-compose --version
   ```

   정상적으로 버전이 출력되면 설치 완료!

   ### 문제 해결

   - **가상화 오류**: BIOS에서 Intel VT-x 또는 AMD-V 활성화
   - **WSL 2 오류**: `wsl --update` 실행 후 재부팅
   - **Docker가 시작되지 않음**: Windows 업데이트 확인 후 재설치

   ### 참고 자료

</details>
<br>
<details>
<summary>MacOS docker 설치</summary>
   <details>
   <summary>1. Docker Desktop 다운로드 및 설치 (무거워서 colima로 설치하길 추천)</summary>

1. [Docker Desktop 공식 사이트](https://www.docker.com/products/docker-desktop/)에서 다운로드
2. **본인 Mac 칩에 맞는 버전 선택**:
   - Apple Silicon (M1/M2/M3): "Mac with Apple chip" 클릭
   - Intel: "Mac with Intel chip" 클릭
3. 다운로드된 `Docker.dmg` 파일 실행
4. Docker 아이콘을 Applications 폴더로 드래그
5. Applications에서 Docker 실행
6. 권한 요청 시 비밀번호 입력 후 허용

### 2. 설치 확인

터미널에서 실행:

```bash
docker --version
docker-compose --version
```

정상적으로 버전이 출력되면 설치 완료!

### 문제 해결

- **권한 오류**: 시스템 환경설정 > 보안 및 개인 정보 보호에서 Docker 허용
- **Rosetta 오류 (Apple Silicon)**: `softwareupdate --install-rosetta` 실행
- **Docker가 시작되지 않음**: Docker Desktop 재설치 또는 Mac 재부팅

   </details>
   <br>
   <details>
   <summary>2. Homebrew + colima 를 이용한 설치</summary>

### Homebrew + Colima로 설치 (Docker Desktop 대안)

Docker Desktop 대신 무료 오픈소스인 Colima를 사용할 수 있습니다.

#### 1. Homebrew 설치 **(없는 경우)**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

#### 2. Docker CLI 및 Colima 설치

```bash
brew install docker docker-compose colima
```

#### 3. Colima 시작

```bash
# 기본 설정으로 시작
colima start

# 또는 리소스 지정하여 시작 (권장)
colima start --cpu 2 --memory 4
```

#### 4. 설치 확인

```bash
docker --version
docker-compose --version
colima status
```

#### Colima 명령어

```bash
colima start      # 시작
colima stop       # 중지
colima status     # 상태 확인
colima delete     # 삭제 (초기화)
```

#### 문제 해결

- **colima가 시작되지 않음**: `colima delete` 후 다시 `colima start`
- **docker 명령어가 안됨**: `colima start`로 colima가 실행 중인지 확인
- **리소스 부족**: `colima stop` 후 `colima start --cpu 4 --memory 8`로 재시작

   </details>

</details>

## local 개발 시 Docker Compose로 postgresql + redis 실행

:round_pushpin: **docker 설치가 선행되어있어야하며 docker가 실행중이여야합니다.**

컨테이너 실행:

```bash
# 프로젝트 루트 경로에서 실행
docker-compose -f docker-compose.local_env.yml up -d
```

상태 확인:

```bash
docker-compose -f docker-compose.local_env.yml ps
```

[Docker Compose 명령어로 이동하기](#-docker-compose-명령어)

## python 가상환경 생성 및 활성화

:round_pushpin: **python3.12 설치가 선행되어야합니다.**

```bash
cd django #django 프로젝트 폴더에서 실행
python3.12 -m venv venv # python3.12 버전으로 실행.

source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows
```

## 의존성 설치

**가상환경 설치 후 회초 1회만 하면 됩니다.**

```bash
pip install -r requirements.txt
```

<details>
<summary>MacOS psycopg2 에러</summary>

   psycopg2를 설치할 때 PATH 관련 설정이 필요합니다.

   개발 환경에서는 그게 필요없는 psycopg2-binary을 사용하면 되는데
   배포환경에서는 맞지 않습니다.

   아예 해결하실분들은 PATH 설정법을 검색해보셔도 되고
   가장 간단한 방법은 requirements.txt에서

   **psycopg2를 주석처리 하셔도 상관은 없습니다.**

   ```bash
   psycopg2==2.9.11  ->  # psycopg2==2.9.11
   ```

</details>

## DB 마이그레이션 실행

DB 모델들이 django에 묶여있기 때문에 마이그레이션은 **django 통해서 하셔야합니다**

```bash
cd django

# 가상환경 실행 후 실행
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

python manage.py migrate
```
**주의**\
migrations파일은 git을 통해 추적중입니다. 유의해서 작업해주시고 작업시 스키마의 변경점이 있다면, makemigrations 해주십시오.

# 서버 실행

## Django

```bash
# Daphne 서버 실행 (HTTP + WebSocket 지원) / Spring 개발자분들은 이거 사용
daphne -b 0.0.0.0 -p 8000 project.asgi:application

# runserver (WebSocket 안됨)
python manage.py runserver
```

서버가 `http://localhost:8000`에서 실행됩니다.

**주의:**

- Docker로 PostgreSQL + Redis를 먼저 실행해야 합니다
- Daphne은 Django Channels의 WebSocket을 지원하므로 웹소켓을 사용하고자하면 사용하셔야합니다.
- 근데 변경사항 자동 적용이 안되어서 Django 개발자분들은 runserver 사용이 편하실겁니다. (웹소켓 안쓸땐 runserver)
- `python manage.py runserver`는 WebSocket을 지원하지 않습니다

**django 테스트 실행**
```bash
# 상세 출력
pytest -v

# 간단한 출력
pytest

# 실행 후 실패한 테스트만 재실행
pytest --lf

# 특정 앱만 테스트
pytest {폴더이름}/ -v
# ex pytest authentication -v
```

## Spring

spring 담당자 분이 작성바람~~~

```bash
실행코드
```

서버가 `http://localhost:8080`에서 실행됩니다.

# 🐳 Docker Compose 명령어

### 컨테이너 시작

```bash
docker-compose -f docker-compose.local_env.yml up -d
```

하나만 실행

```bash
docker-compose -f docker-compose.local_env.yml up -d postgres
docker-compose -f docker-compose.local_env.yml up -d redis
```

### 컨테이너 상태 확인

```bash
docker-compose -f docker-compose.local_env.yml ps
```

### 컨테이너 종료

```bash
docker-compose -f docker-compose.local_env.yml down
```

### 로그 확인

```bash
# 모든 로그
docker-compose -f docker-compose.local_env.yml logs -f

# PostgreSQL만
docker-compose -f docker-compose.local_env.yml logs postgres

# Redis만
docker-compose -f docker-compose.local_env.yml logs redis
```

### 컨테이너 중지

```bash
docker-compose -f docker-compose.local_env.yml down # db 데이터는 남음
docker-compose -f docker-compose.local_env.yml down -v # -v 옵션이 붙으면 db 데이터도 삭제
```

---
