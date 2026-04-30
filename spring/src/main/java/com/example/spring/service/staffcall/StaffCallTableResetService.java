package com.example.spring.service.staffcall;

import com.example.spring.domain.staffcall.StaffCall;
import com.example.spring.domain.staffcall.StaffCallStatus;
import com.example.spring.repository.staffcall.StaffCallRepository;
import com.example.spring.websocket.CustomerStaffCallWebSocketHandler;
import com.example.spring.websocket.StaffCallWebSocketHandler;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Lazy;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * Django 테이블 초기화 시 Redis({@code django:booth:*:order:reset})와 맞춰
 * 해당 부스·테이블 번호의 직원 호출을 {@link StaffCallStatus#CANCELLED}로 맞춘다(이미 취소된 행은 스킵).
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class StaffCallTableResetService {

    private final StaffCallRepository staffCallRepository;
    private final StaffCallQueryService staffCallQueryService;

    @Lazy
    @Autowired
    private StaffCallWebSocketHandler staffCallWebSocketHandler;

    @Lazy
    @Autowired
    private CustomerStaffCallWebSocketHandler customerStaffCallWebSocketHandler;

    @Transactional
    public void voidActiveCallsForTable(Long boothId, Integer tableNum) {
        if (boothId == null || tableNum == null) {
            return;
        }

        List<StaffCall> toVoid = staffCallRepository.findByBoothIdAndTableNumAndStatusNot(
                boothId,
                tableNum,
                StaffCallStatus.CANCELLED);

        if (toVoid.isEmpty()) {
            return;
        }

        for (StaffCall sc : toVoid) {
            sc.cancelDueToTableReset();
        }
        staffCallRepository.saveAll(toVoid);

        try {
            staffCallWebSocketHandler.broadcastSnapshot(boothId,
                    staffCallQueryService.listForBooth(boothId, 50, 0));
            for (StaffCall sc : toVoid) {
                customerStaffCallWebSocketHandler.broadcastStatus(sc);
            }
        } catch (Exception e) {
            log.error("[staffcall table reset] 스냅샷/고객 WS 푸시 실패 — DB 반영은 완료 boothId={}, tableNum={}",
                    boothId, tableNum, e);
        }
    }
}
