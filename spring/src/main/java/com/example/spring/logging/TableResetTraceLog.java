package com.example.spring.logging;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Django 테이블 초기화 → Redis({@code django:booth:*:order:reset}) → Spring 처리 구간을
 * 한 줄로 grep 하기 위한 공통 로그. (버튼 시점은 Django 쪽; Spring 에서는 Redis 수신을 구간 시작으로 본다.)
 */
public final class TableResetTraceLog {

    private static final Logger log = LoggerFactory.getLogger(TableResetTraceLog.class);

    private TableResetTraceLog() {}

    public static void info(String step, String outcome, Long boothId, Integer tableNum, String detail) {
        log.info("[테이블초기화-추적] step={} outcome={} booth={} table={} | {}",
                step, outcome, nz(boothId), nz(tableNum), detail == null ? "" : detail);
    }

    public static void warn(String step, String outcome, Long boothId, Integer tableNum, String detail) {
        log.warn("[테이블초기화-추적] step={} outcome={} booth={} table={} | {}",
                step, outcome, nz(boothId), nz(tableNum), detail == null ? "" : detail);
    }

    public static void error(String step, String outcome, Long boothId, Integer tableNum, String detail,
                           Throwable t) {
        log.error("[테이블초기화-추적] step={} outcome={} booth={} table={} | {}",
                step, outcome, nz(boothId), nz(tableNum), detail == null ? "" : detail, t);
    }

    public static void error(String step, String outcome, Long boothId, Integer tableNum, String detail) {
        log.error("[테이블초기화-추적] step={} outcome={} booth={} table={} | {}",
                step, outcome, nz(boothId), nz(tableNum), detail == null ? "" : detail);
    }

    private static String nz(Object o) {
        return o == null ? "-" : String.valueOf(o);
    }

    /** {@code django:booth:{id}:...} → booth id */
    public static Long tryParseBoothIdFromChannel(String channel) {
        if (channel == null || !channel.startsWith("django:booth:")) {
            return null;
        }
        String[] parts = channel.split(":");
        if (parts.length < 3) {
            return null;
        }
        try {
            return Long.valueOf(parts[2]);
        } catch (NumberFormatException e) {
            return null;
        }
    }
}
