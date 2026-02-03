# D-Order Backend v3
D-Order 백엔드 레포입니다.
---

## Contributors
| 이름 | Email | 담담 |
| --- | --- | --- |
|  |  |  |
|  |  |  |
|  |  |  |
## 📁 프로젝트 구조

```
2026-d-order-backend-v3/
├── .env                          # 환경 변수 (Django + Docker) notion 참조
├── README.md                     # 이 파일
├── docker-compose.local.yml      # 로컬 개발 환경시 postgre + redis 컨테이너 만들기
├── docker-compose.prod.yml       # 작성 예정 / 배포 시 docker-compose
├── docker-compose.staging.yml    # 작성 예정 / 개발서버 docker-compose
├── django/
│   ├── manage.py                 
│   ├── requirements.txt          # Python 의존성 파일들
│   ├── apps/
│   └── project/                  # Django 프로젝트 폴더
└── Spring/                       # Spring
```

## 3. 커밋 및 PR 컨벤션

시간이 없기때문에..최소한의 태그만 사용하는거로 컨벤션 정했습니다. 

### ✅ Commit Convention

| 태그 | 설명 | 예시 |
| --- | --- | --- |
| Feat | 새로운 기능 추가(새 API/유스케이스/도메인 기능) | `Feat: 주문 생성 API 추가` |
| Fix | 버그 수정(오류/예외/로직 결함) | `Fix: 결제 승인 시 NPE 수정` |
| Design | UI 스타일 및 레이아웃 변경(백엔드엔 보통 거의 없음; Swagger/문서 UI 정도만 해당) | `Design: Swagger UI 테마 변경` |
| Docs | 문서 수정(README, API 문서, 주석 등) | `Docs: 로컬 실행 방법 업데이트` |
| Refactor | 리팩토링(기능 변화 없음, 구조/가독성/중복 개선) | `Refactor: 주문 서비스 메서드 분리` |
| Chore | 설정/패키지/환경 변경(빌드, 의존성, 설정 파일 등) | `Chore: Spring profile 설정 정리` |

> ⚠️ Feat은 진짜 "새 기능"에만! 오타 수정 등에는 Fix 사용
> 
- **`Refactor`**: **기존 코드의 내부 구조를 개선**하는 데 중점을둠. 외부 동작은 동일하지만 코드를 더 효율적이고 읽기 쉽게 만드는 변경에 해당 (예: 함수 분리, 변수명 개선, 중복 코드 제거).
- **`Chore`**: **프로젝트의 빌드 환경, 종속성, 관리 관련 작업**에 중점을 둠. 코드 자체의 로직 변경보다는 개발 환경 설정, 라이브러리 업데이트, 빌드 스크립트 수정 등.



### ✅ PR 제목 규칙

| 아이콘 | 태그 | 설명 | 예시 |
| --- | --- | --- | --- |
| ✨ | [Feature] | 새로운 기능 추가 | ✨ [Feature] #12 - 마이페이지 기능 추가 |
| 🐛 | [Fix] | 버그 수정 | 🐛 [Fix] #15 - 로그인 버튼 오류 수정 |
| 🎨 | [Design] | UI 스타일 및 레이아웃 | 🎨 [Design] #21 - 헤더 스타일 변경 |
| 📝 | [Docs] | 문서 수정 | 📝 [Docs] #30 - README 사용법 수정 |
| ♻️ | [Refactor] | 리팩토링 | ♻️ [Refactor] #35 - API 요청 함수 리팩토링 |
| 🔧 | [Chore] | 환경 설정 변경 | 🔧 [Chore] #40 - webpack 설정 변경 |

---