package com.example.spring.domain.table;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * Django {@code table.Table} → DB 테이블 {@code table_table}
 */
@Entity
@Table(name = "table_table")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class BoothTable {

    @Id
    private Long id;

    @Column(name = "booth_id", nullable = false)
    private Long boothId;

    @Column(name = "table_num", nullable = false)
    private Integer tableNum;

    /**
     * Django: AVAILABLE, IN_USE, INACTIVE
     */
    @Column(name = "status", nullable = false, length = 20)
    private String status;
}
