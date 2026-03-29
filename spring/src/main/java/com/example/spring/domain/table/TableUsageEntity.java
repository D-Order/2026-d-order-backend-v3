package com.example.spring.domain.table;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

/**
 * Django {@code table.TableUsage} → {@code table_tableusage}
 */
@Entity
@Table(name = "table_tableusage")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class TableUsageEntity {

    @Id
    private Long id;

    @Column(name = "table_id", nullable = false)
    private Long tableId;
}
