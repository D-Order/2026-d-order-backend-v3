package com.example.spring.repository.staffcall;

import com.example.spring.domain.staffcall.StaffCall;
import com.example.spring.domain.staffcall.StaffCallStatus;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;
import java.util.Optional;

public interface StaffCallRepository extends JpaRepository<StaffCall, Long> {

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("SELECT sc FROM StaffCall sc WHERE sc.tableId = :tableId AND sc.cartId = :cartId AND sc.callType = :callType AND sc.status IN ('PENDING', 'ACCEPTED')")
    Optional<StaffCall> findByTableCartCallTypeForUpdate(
            @Param("tableId") Long tableId,
            @Param("cartId") Long cartId,
            @Param("callType") String callType
    );

    @Query(value = """
            SELECT sc.id, sc.booth_id, sc.table_id, sc.cart_id, sc.table_usage_id, sc.table_num, sc.cart_price,
                   sc.call_type, sc.category,
                   sc.status, sc.created_at, sc.updated_at, sc.accepted_at, sc.accepted_by, sc.completed_at, sc.version
            FROM staff_call sc
            WHERE sc.booth_id = :boothId
            AND sc.status IN ('PENDING', 'ACCEPTED')
            ORDER BY
              CASE
                WHEN sc.status = 'PENDING' THEN 0
                ELSE 1
              END ASC,
              CASE
                WHEN sc.status = 'ACCEPTED' THEN sc.accepted_at
                ELSE sc.created_at
              END DESC,
              sc.id DESC
            LIMIT :limit OFFSET :offset
            """, nativeQuery = true)
    List<StaffCall> findActiveCallsForBooth(
            @Param("boothId") Long boothId,
            @Param("limit") int limit,
            @Param("offset") int offset
    );

    @Query(value = """
            SELECT COUNT(*)
            FROM staff_call sc
            WHERE sc.booth_id = :boothId
            AND sc.status IN ('PENDING', 'ACCEPTED')
            """, nativeQuery = true)
    long countActiveCallsForBooth(@Param("boothId") Long boothId);

    long countByTableIdAndCartIdAndCallTypeAndStatus(
            Long tableId,
            Long cartId,
            String callType,
            StaffCallStatus status
    );

    long countByTableIdAndCartIdAndCallTypeAndStatusIn(
            Long tableId,
            Long cartId,
            String callType,
            Collection<StaffCallStatus> statuses
    );

    @Query("SELECT sc FROM StaffCall sc WHERE sc.boothId = :boothId AND sc.tableNum = :tableNum "
            + "AND sc.status IN :statuses")
    List<StaffCall> findByBoothIdAndTableNumAndStatusIn(
            @Param("boothId") Long boothId,
            @Param("tableNum") Integer tableNum,
            @Param("statuses") Collection<StaffCallStatus> statuses
    );
}
