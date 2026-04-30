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
import java.util.Map;
import java.util.Objects;
import java.util.stream.Collectors;

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
            log.warn("[테이블 초기화 staffcall] boothId/tableNum 없음 — 스킵. boothId={}, tableNum={}",
                    boothId, tableNum);
            return Collections.emptyList();
        }

        log.info("[테이블 초기화 staffcall] staff_call 취소 트랜잭션 시작 boothId={}, tableNum={}",
                boothId, tableNum);

        List<StaffCall> toVoid = staffCallRepository.findForTableResetVoidCandidates(
                boothId,
                tableNum,
                StaffCallStatus.CANCELLED);

        if (toVoid.isEmpty()) {
            log.info("[테이블 초기화 staffcall] 취소 대상 없음 boothId={}, tableNum={} (이미 취소이거나 행 없음)",
                    boothId, tableNum);
            return Collections.emptyList();
        }

        String beforeDetail = toVoid.stream()
                .map(sc -> sc.getId() + ":" + sc.getStatus())
                .collect(Collectors.joining(", "));
        log.info("[테이블 초기화 staffcall] 취소 적용 전 boothId={}, tableNum={}, 건수={}, id상태=[{}]",
                boothId, tableNum, toVoid.size(), beforeDetail);

        for (StaffCall sc : toVoid) {
            sc.cancelDueToTableReset();
        }
        staffCallRepository.saveAll(toVoid);

        String ids = toVoid.stream().map(sc -> Objects.toString(sc.getId())).collect(Collectors.joining(","));
        log.info("[테이블 초기화 staffcall] DB 저장 완료 boothId={}, tableNum={}, staffCallIds=[{}]",
                boothId, tableNum, ids);
        return toVoid;
    }

    /** DB 커밋 이후 호출 — 실패해도 staff_call 취소는 유지된다. */
    public void publishTableResetNotifications(Long boothId, List<StaffCall> voided) {
        if (voided == null || voided.isEmpty()) {
            log.info("[테이블 초기화 staffcall] 스냅샷/WS 스킵 — 취소된 호출 없음 boothId={}", boothId);
            return;
        }

        String ids = voided.stream().map(sc -> Objects.toString(sc.getId())).collect(Collectors.joining(","));
        log.info("[테이블 초기화 staffcall] 스냅샷·WS 푸시 시작 boothId={}, 건수={}, staffCallIds=[{}]",
                boothId, voided.size(), ids);
        try {
            Map<String, Object> snapshotBody = staffCallQueryService.listForBooth(boothId, 50, 0);
            log.info("[테이블 초기화 staffcall] 직원 목록 스냅샷 조회 완료 boothId={}, activeTotal={}, hasMore={}",
                    boothId, snapshotBody.get("total"), snapshotBody.get("has_more"));
            staffCallWebSocketHandler.broadcastSnapshot(boothId, snapshotBody);

            int wsOk = 0;
            for (StaffCall sc : voided) {
                customerStaffCallWebSocketHandler.broadcastStatus(sc);
                wsOk++;
            }
            log.info("[테이블 초기화 staffcall] 고객 WS 전송 완료 boothId={}, 전송건수={}", boothId, wsOk);
        } catch (Exception e) {
            log.error("[테이블 초기화 staffcall] 스냅샷/WS 푸시 실패 — DB 취소 반영은 완료됨 boothId={}, staffCallIds=[{}]",
                    boothId, ids, e);
        }
    }
}
