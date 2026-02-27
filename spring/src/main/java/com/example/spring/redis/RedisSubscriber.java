package com.example.spring.redis;

import com.example.spring.event.RedisMessageEvent;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.data.redis.connection.Message;
import org.springframework.data.redis.connection.MessageListener;
import org.springframework.stereotype.Service;

@Service
public class RedisSubscriber implements MessageListener {

    private final ApplicationEventPublisher eventPublisher;

    public RedisSubscriber(ApplicationEventPublisher eventPublisher) {
        this.eventPublisher = eventPublisher;
    }

@Override
public void onMessage(Message message, byte[] pattern) {
    String publishedMessage = new String(message.getBody());
    String channel = new String(message.getChannel());
    System.out.println("[구독 패턴] " + channel + " → 데이터: " + publishedMessage);
    eventPublisher.publishEvent(new RedisMessageEvent(channel, publishedMessage));
}
}
