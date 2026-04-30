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
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.util.Collections;
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

    /**
     * Redis 테이블 초기화와 별도 트랜잭션으로 커밋한다.
     * 스냅샷 조회(listForBooth)와 같은 트랜잭션에 두면 flush/예외 시 호출 쪽 트랜잭션까지 롤백될 수 있다.
     */
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public List<StaffCall> voidActiveCallsForTable(Long boothId, Integer tableNum) {
        if (boothId == null || tableNum == null) {
            return Collections.emptyList();
        }

        List<StaffCall> toVoid = staffCallRepository.findForTableResetVoidCandidates(
                boothId,
                tableNum,
                StaffCallStatus.CANCELLED);

        if (toVoid.isEmpty()) {
            log.info("[staffcall table reset] 취소 대상 없음 boothId={}, tableNum={}", boothId, tableNum);
            return Collections.emptyList();
        }

        for (StaffCall sc : toVoid) {
            sc.cancelDueToTableReset();
        }
        staffCallRepository.saveAll(toVoid);
        log.info("[staffcall table reset] boothId={}, tableNum={}, cancelledCount={}", boothId, tableNum, toVoid.size());
        return toVoid;
    }

    /** DB 커밋 이후 호출 — 실패해도 staff_call 취소는 유지된다. */
    public void publishTableResetNotifications(Long boothId, List<StaffCall> voided) {
        if (voided == null || voided.isEmpty()) {
            return;
        }
        try {
            staffCallWebSocketHandler.broadcastSnapshot(boothId,
                    staffCallQueryService.listForBooth(boothId, 50, 0));
            for (StaffCall sc : voided) {
                customerStaffCallWebSocketHandler.broadcastStatus(sc);
            }
        } catch (Exception e) {
            log.error("[staffcall table reset] 스냅샷/고객 WS 푸시 실패 — DB 반영은 완료 boothId={}",
                    boothId, e);
        }
    }
}
