package com.example.spring.repository.table;

import com.example.spring.domain.table.TableUsageEntity;
import org.springframework.data.jpa.repository.JpaRepository;

public interface TableUsageEntityRepository extends JpaRepository<TableUsageEntity, Long> {
}
