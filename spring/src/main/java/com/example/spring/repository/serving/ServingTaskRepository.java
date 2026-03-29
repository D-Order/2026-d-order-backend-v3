package com.example.spring.repository.serving;

import com.example.spring.domain.serving.ServingStatus;
import com.example.spring.domain.serving.ServingTask;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.util.List;

public interface ServingTaskRepository extends JpaRepository<ServingTask, Long> {

    // 🌟 join fetch를 사용하여 OrderItem 정보를 한 번의 쿼리로 묶어 가져옵니다.
    @Query("SELECT st FROM ServingTask st JOIN FETCH st.orderItem WHERE st.status = :status")
    List<ServingTask> findAllByStatusWithOrderItem(@Param("status") ServingStatus status);
}