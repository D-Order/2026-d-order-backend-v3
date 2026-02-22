package com.example.spring.event;

public class RedisMessageEvent {
    private final String channel;
    private final String message;

    public RedisMessageEvent(String channel, String message) {
        this.channel = channel;
        this.message = message;
    }

    public String getChannel() { return channel; }
    public String getMessage() { return message; }
}
