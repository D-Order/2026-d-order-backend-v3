package com.example.spring.repository.table;

import com.example.spring.domain.table.BoothTable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface BoothTableRepository extends JpaRepository<BoothTable, Long> {

    Optional<BoothTable> findByIdAndBoothId(Long id, Long boothId);
}
