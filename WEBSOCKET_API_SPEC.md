# WebSocket API 명세서

---

# ① ADMIN_ORDER_UPDATE – 아이템 상태 변경

## 기능 설명
특정 아이템의 상태가 변경될 때(조리 중 → 조리 완료 → 서빙 중 → 서빙 완료) 실시간으로 발생합니다. 

## BE 구현 주의사항
- **상태 전이**
    - `cooking` → `cooked` : 조리 완료 버튼 클릭 시
    - `cooked` → `serving` : 서버가 서빙 수락 눌렀을 시 (Redis 구독)
    - `serving` → `served` : 서빙 완료 확인 시
    - `cancelled` 취소 시 리스트에서 제외

---

## WebSocket 연결 정보

### URL
```
wss://host/ws/v3/django/
```

### 인증 방식
쿠키 기반 인증 (세션 쿠키 자동 전송)

```javascript
const socket = new WebSocket("wss://host/ws/v3/django/");
// 브라우저가 자동으로 쿠키 전송
```

### 인증 실패
- 연결 즉시 종료 (close code: 4001)
- 토큰 갱신 후 재연결 필요

---

## Payload (서버 → 클라이언트)

### 공통 구조
```json
{
  "type": "이벤트_타입",
  "timestamp": "ISO 8601",
  "data": { }
}
```

### ADMIN_ORDER_UPDATE

```json
{
  "type": "ADMIN_ORDER_UPDATE",
  "timestamp": "2026-04-12T14:25:30.123456+09:00",
  "data": {
    "order_id": 15,
    "items": [
      {
        "order_item_id": 201,
        "menu_name": "아메리카노",
        "status": "COOKING",
        "is_set": false,
        "set_menu_name": null,
        "parent_order_item_id": null,
        "cooked_at": "2026-04-12T14:25:30.123456+09:00",
        "served_at": null
      }
    ]
  }
}
```

### 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `type` | String | 이벤트 타입 (항상 `ADMIN_ORDER_UPDATE`) |
| `data.order_id` | Integer | 변경 대상 주문 ID |
| `data.items[].order_item_id` | Integer | 변경된 아이템 ID |
| `data.items[].menu_name` | String | 메뉴 이름 |
| `data.items[].status` | String | 변경된 상태 (`cooking` \| `cooked` \| `serving` \| `served`) |
| `data.items[].is_set` | Boolean | 세트메뉴 자식 여부 |
| `data.items[].set_menu_name` | String \| null | 세트메뉴명 (세트메뉴 포함 시) |
| `data.items[].cooked_at` | String \| null | 조리 완료 시간 |
| `data.items[].served_at` | String \| null | 서빙 완료 시간 |

### 트리거 조건

- `cooking` → `cooked` : 조리 완료 버튼 클릭 시
- `cooked` → `serving` : 서버가 서빙 수락 눌렀을 시 (Redis 구독)
- `serving` → `served` : 서빙 완료 확인 시
- `cancelled` : 취소 시 아이템 리스트에서 제외

---

# ⑧ ADMIN_TABLE_RESET – 테이블 초기화 (주문 갱신)

## 기능 설명
테이블이 초기화될 때(손님 퇴장) 발생합니다. Django는 현재 부스에서 활성 중인 모든 주문을 즉시 재조회하여 프론트엔드로 전송합니다. 초기화된 테이블의 주문은 자동으로 제외됩니다.

## BE 구현 주의사항
- **테이블 초기화 조건**: 테이블의 `table_usage` 레코드의 `ended_at` 필드 설정됨
- **활성 주문 필터**: 쿼리에 `table_usage__ended_at__isnull=True` 필터 적용 (종료된 테이블 자동 제외)
- **메시지 발송 시점**: `table/services.py`의 `reset_tables()` 메서드에서 WebSocket 그룹으로 **즉시** 전송
- **데이터 무결성**: 초기화된 테이블의 주문은 이전 정산 기록이므로 별도 처리 가능

### WebSocket 채널
```
booth_{booth_id}.order
```

---

## Payload (서버 → 클라이언트)

```json
{
  "type": "ADMIN_TABLE_RESET",
  "timestamp": "2026-04-12T14:30:45.123456+09:00",
  "data": {
    "table_nums": [1],
    "count": 1,
    "total_sales": 100000,
    "orders": [
      {
        "order_id": 123,
        "table_num": 2,
        "table_usage_id": 456,
        "order_status": "PAID",
        "time_ago": "5분 전",
        "has_coupon": false,
        "items": [
          {
            "order_item_id": 789,
            "menu_name": "아메리카노",
            "image": "http://example.com/image.jpg",
            "quantity": 2,
            "fixed_price": 4500,
            "item_total_price": 9000,
            "status": "COOKING",
            "is_set": false
          }
        ]
      }
    ]
  }
}
```

### 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `data.table_nums` | Array | 초기화된 테이블 번호 배열 |
| `data.count` | Integer | 초기화된 테이블 개수 |
| `data.total_sales` | Integer | 현재 부스의 총 매출액 |
| `data.orders[]` | Array | **초기화된 테이블 제외** 현재 활성 주문 목록 |

### 트리거 조건

- 관리자가 테이블 초기화 버튼 클릭 시
- `table/services.py`의 `reset_tables()` 메서드 실행
- WebSocket 메시지가 `booth_{booth_id}.order` 채널 그룹으로 발송됨

---

# ⑨ ADMIN_TABLE_MERGE – 테이블 병합 (주문 갱신)

## 기능 설명
여러 테이블을 하나로 병합할 때 발생합니다. Django는 현재 부스에서 활성 중인 모든 주문을 즉시 재조회하여 프론트엔드로 전송합니다. 각 주문은 별개의 대시보드 빌지로 표시됩니다.

## BE 구현 주의사항
- **테이블 병합 조건**: 여러 테이블의 `table_usage` 레코드를 대표 테이블로 통합
- **Table ID 변경**: 병합된 테이블의 주문들은 대표 테이블의 TableUsage와 연결되며, `table_num`이 대표 테이블 번호로 변경됨
- **활성 주문 필터**: 쿼리에 `table_usage__ended_at__isnull=True` 필터 적용
- **메시지 발송 시점**: `table/services.py`의 `merge_tables()` 메서드에서 WebSocket 그룹으로 **즉시** 전송
- **최소 요구**: 병합하려면 최소 2개 테이블 이상 필요

### WebSocket 채널
```
booth_{booth_id}.order
```

---

## Payload (서버 → 클라이언트)

```json
{
  "type": "ADMIN_TABLE_MERGE",
  "timestamp": "2026-04-12T14:35:22.654321+09:00",
  "data": {
    "table_nums": [1, 2],
    "representative_table": 1,
    "count": 2,
    "total_sales": 250000,
    "orders": [
      {
        "order_id": 100,
        "table_num": 1,
        "table_usage_id": 456,
        "order_status": "PAID",
        "time_ago": "5분 전",
        "has_coupon": false,
        "items": [
          {
            "order_item_id": 789,
            "menu_name": "아메리카노",
            "image": "http://example.com/image.jpg",
            "quantity": 2,
            "fixed_price": 4500,
            "item_total_price": 9000,
            "status": "COOKING",
            "is_set": false
          }
        ]
      },
      {
        "order_id": 101,
        "table_num": 1,
        "table_usage_id": 456,
        "order_status": "PAID",
        "time_ago": "3분 전",
        "has_coupon": true,
        "items": [...]
      }
    ]
  }
}
```

### 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `data.table_nums` | Array | 병합된 모든 테이블 번호 배열 |
| `data.representative_table` | Integer | 대표 테이블 번호 (가장 낮은 번호) |
| `data.count` | Integer | 병합된 테이블 개수 |
| `data.total_sales` | Integer | 현재 부스의 총 매출액 |
| `data.orders[]` | Array | **병합된 모든 테이블의 활성 주문** (각각 별개의 빌지) |

### 특징
- **각 order_id는 별개**: order_id 100, 101이 배열에 각각 포함
- **table_num 통합**: 원래 order 101의 table_num이 2 → 1로 변경됨
- **같은 table_usage**: 병합된 모든 주문이 대표 테이블의 TableUsage를 공유
- **프론트 렌더링**: 프론트는 각 order를 별개의 빌지로 표시 (총 2개 빌지)

### 트리거 조건

- 관리자가 여러 테이블 병합 버튼 클릭 시
- `table/services.py`의 `merge_tables()` 메서드 실행
- 최소 2개 테이블 이상 선택 필요
- WebSocket 메시지가 `booth_{booth_id}.order` 채널 그룹으로 발송됨

---

## 프론트엔드 컨슈머 구현 가이드

### 메시지 수신 및 처리

```javascript
socket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  switch(message.type) {
    case 'ADMIN_ORDER_UPDATE':
      // 아이템 상태 변경 처리
      const { order_id, items } = message.data;
      updateOrderItemStatus(order_id, items);
      break;
      
    case 'ADMIN_TABLE_RESET':
      // 테이블 초기화 처리
      // 프론트가 갖고 있던 주문 목록을 받은 목록으로 완전히 갱신
      this.orders = message.data.orders;
      this.totalSales = message.data.total_sales;
      this.renderAllBills();
      break;
      
    case 'ADMIN_TABLE_MERGE':
      // 테이블 병합 처리
      // 마찬가지로 현재 주문 목록을 갱신
      this.orders = message.data.orders;
      this.totalSales = message.data.total_sales;
      this.representativeTable = message.data.representative_table;
      // 각 주문이 별개 빌지로 렌더링됨
      this.renderAllBills();
      break;
  }
};
```

### 주문 빌지 렌더링 로직

```javascript
renderAllBills() {
  // orders 배열의 각 요소가 하나의 빌지
  this.orders.forEach(order => {
    renderBillCard(order.order_id, order.table_num, order.items);
  });
}

// RESET: orders = [order_2, order_3] → 빌지 2개 표시
// MERGE: orders = [order_1, order_2] (같은 table_num 1) → 빌지 2개 표시 (같은 테이블이지만 별개 주문)
```

---

## 에러 응답

### 에러 Payload

```json
{
  "type": "ERROR",
  "data": {
    "code": "에러코드",
    "message": "에러 메시지"
  }
}
```

### 에러 코드 목록

| 코드 | 설명 | 재연결 필요 |
| --- | --- | --- |
| `AUTH_ERROR` | 인증 실패 또는 토큰 만료 | ✅ 토큰 갱신 후 재연결 |
| `PERMISSION_DENIED` | 권한 없음 (관리자 아님) | ❌ |
| `INVALID_MESSAGE` | 잘못된 메시지 형식 | ❌ |
| `SERVER_ERROR` | 서버 내부 오류 | ✅ 즉시 재연결 |
