package com.example.spring.repository.serving;

import com.example.spring.domain.serving.ServingStatus;
import com.example.spring.domain.serving.ServingTask;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface ServingTaskRepository extends JpaRepository<ServingTask, Long> {

    /**
     * 운영자 인증으로 추출한 booth_id 기준으로
     * 해당 부스의 서빙 대기 목록만 조회
     */
    List<ServingTask> findByBoothIdAndStatusOrderByRequestedAtAsc(Long boothId, ServingStatus status);

    Optional<ServingTask> findFirstByBoothIdAndOrderItemIdAndStatusIn(Long boothId, Long orderItemId, List<ServingStatus> statuses);

    long deleteByBoothIdAndOrderItemIdAndStatusIn(Long boothId, Long orderItemId, List<ServingStatus> statuses);

    long deleteByBoothIdAndTableNumberAndStatusIn(Long boothId, Integer tableNumber, List<ServingStatus> statuses);

    @Query("""
            select distinct st.menuName
            from ServingTask st
            where st.boothId = :boothId
              and st.status = :status
              and st.menuName is not null
            order by st.menuName asc
            """)
    List<String> findDistinctMenuNamesByBoothIdAndStatus(@Param("boothId") Long boothId, @Param("status") ServingStatus status);

    @Query("""
            select distinct st.tableNumber
            from ServingTask st
            where st.boothId = :boothId
              and st.status = :status
              and st.tableNumber is not null
            order by st.tableNumber asc
            """)
    List<Integer> findDistinctTableNumbersByBoothIdAndStatus(@Param("boothId") Long boothId, @Param("status") ServingStatus status);

}