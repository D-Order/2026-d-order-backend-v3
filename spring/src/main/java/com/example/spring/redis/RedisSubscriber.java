package com.example.spring.redis;

import com.example.spring.event.RedisMessageEvent;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.data.redis.connection.Message;
import org.springframework.data.redis.connection.MessageListener;
import org.springframework.stereotype.Service;

import java.nio.charset.StandardCharsets;

@Slf4j
@Service
public class RedisSubscriber implements MessageListener {

    private final ApplicationEventPublisher eventPublisher;

    public RedisSubscriber(ApplicationEventPublisher eventPublisher) {
        this.eventPublisher = eventPublisher;
    }

    @Override
    public void onMessage(Message message, byte[] pattern) {
        String publishedMessage = new String(message.getBody(), StandardCharsets.UTF_8);
        String channel = new String(message.getChannel(), StandardCharsets.UTF_8);
        String patternStr = pattern != null ? new String(pattern, StandardCharsets.UTF_8) : null;

        log.info("[Redis 구독] channel={}, pattern={}, message={}",
                channel,
                patternStr,
                truncateBody(publishedMessage));
        eventPublisher.publishEvent(new RedisMessageEvent(channel, publishedMessage));
    }

    private static String truncateBody(String body) {
        if (body == null) {
            return "null";
        }
        int max = 800;
        if (body.length() <= max) {
            return body;
        }
        return body.substring(0, max) + "…(len=" + body.length() + ")";
    }
}