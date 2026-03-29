package com.example.spring.service.staffcall;

import com.example.spring.domain.staffcall.StaffCall;
import com.example.spring.dto.staffcall.response.StaffCallItemResponse;
import com.example.spring.repository.staffcall.StaffCallRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class StaffCallQueryService {

    private final StaffCallRepository staffCallRepository;

    @Transactional(readOnly = true)
    public Map<String, Object> listForBooth(Long boothId, int limit, int offset) {
        int safeLimit = Math.min(Math.max(limit, 1), 200);
        int safeOffset = Math.max(offset, 0);

        List<StaffCall> page = staffCallRepository.findActiveCallsForBooth(boothId, safeLimit + 1, safeOffset);
        boolean hasMore = page.size() > safeLimit;
        List<StaffCall> slice = hasMore ? page.subList(0, safeLimit) : page;

        List<StaffCallItemResponse> items = slice.stream()
                .map(StaffCallItemResponse::from)
                .collect(Collectors.toList());

        Map<String, Object> body = new HashMap<>();
        body.put("message", "ok");
        body.put("data", items);
        body.put("has_more", hasMore);
        return body;
    }
}
