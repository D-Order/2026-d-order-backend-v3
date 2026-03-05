package com.example.spring.dto.serving.request;

import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class CatchCallRequest {

    // 누가 이 서빙 콜을 잡았는지 (예: "Robot_01", "Staff_A")
    private String catchedBy;

}