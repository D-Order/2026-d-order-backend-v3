# api spec 양식파일

# API 명세서 상세 양식

## API 설명

- API URL : /api/v3/spring/~~ 의형태
- HTTP METHOD :
- 모델 :
- 인증필요 여부:

## **기능 설명**

`[해당 API가 백엔드에서 어떤 로직으로 동작하는지, 프론트엔드와 어떤 방식으로 데이터를 주고받는지 등 상세하게 설명합니다. 사용자 시나리오를 포함하여 설명할 수도 있습니다.]`

## **BE 구현 주의 사항**

`[백엔드 개발 시 특별히 주의해야 할 사항, 특정 비즈니스 로직, 데이터 유효성 검사 규칙, 에러 처리 방식, 성능 고려사항 등을 구체적으로 명시하는 공간입니다.]`

---

## **Request (요청)**

### **Headers**

요청 시 포함될 HTTP 헤더 정보 (Content-Type, Authorization 등)

```json
# 인증이 필요한 경우에 🔒 필요 (쿠키 자동) 작성
# 쿠키로 관리하기에 Authorization Header를 추가할 필요없이 밑 부분만 있으면 됨.
# credentials: 'include'  // 쿠키 자동 전송

Content-Type: application/json
```

### **Request Body (JSON)**

```json

```

### **유효성 검사 규칙**

```json

```

### **Request Body 예시**

```json

```

---

## Response (응답)

### 성공 응답 (Status)

- **설명**: API 호출 성공 시 예상되는 HTTP 상태 코드
- **기입 내용**: 200 - OK

### Response Body (JSON)

- **설명**:

```json
{
  "message": "String",
  "data": {}
}
```

## Response Body 예시

- **설명**:

```json
# 200 OK
{
	"message" : "내용",
	"data" : {


	}
}

# Other Code
```

### 오류 응답 (Status)

- **설명**: API 호출 실패 시 예상되는 HTTP 상태 코드 및 유형
- **기입내용:**

### 오류 응답 Body (JSON)

- **설명**: 오류 발생 시 서버로부터 받는 에러 메시지 및 상세 정보및 응답데이터 JSON 예시
- **기입 내용**:

  ```json

  ```

---

## 기타

### 비고

- **설명**: 프론트엔드/백엔드 공유 특이사항, ToDo, 추가 설명 등
- **기입 내용**:
