package com.example.spring.logging;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Spring 이 Redis 로 {@code spring:booth:*} 메시지를 보낼 때 Django 쪽({@code listen_redis} 등)으로 전달되는 구간 로그.
 */
public final class SpringToDjangoRedisLog {

    private static final Logger log = LoggerFactory.getLogger(SpringToDjangoRedisLog.class);

    private SpringToDjangoRedisLog() {}

    public static void publishOrder(Long boothId, String channel, String jsonPayload) {
        log.info("[Spring→Django Redis] kind=order channel={} booth={} payload={}",
                channel, nz(boothId), truncate(jsonPayload, 1200));
    }

    public static void publishStaffcall(Long boothId, String channel, String eventHint, String jsonPayload) {
        log.info("[Spring→Django Redis] kind=staffcall channel={} booth={} event={} payload={}",
                channel, nz(boothId), eventHint, truncate(jsonPayload, 1200));
    }

    public static void publishFail(String kind, Long boothId, String channel, Throwable t) {
        log.error("[Spring→Django Redis] FAIL kind={} booth={} channel={}",
                kind, nz(boothId), channel, t);
    }

    private static String nz(Long boothId) {
        return boothId == null ? "-" : String.valueOf(boothId);
    }

    private static String truncate(String s, int maxChars) {
        if (s == null) {
            return "null";
        }
        if (s.length() <= maxChars) {
            return s;
        }
        return s.substring(0, maxChars) + "…(len=" + s.length() + ")";
    }
}
