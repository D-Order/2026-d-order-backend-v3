package com.example.spring.controller.test;

import com.example.spring.event.RedisMessageEvent;
import com.example.spring.service.test.RedisPublishService;
import org.springframework.context.event.EventListener;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.ArrayList;
import java.util.List;

@RestController
@RequestMapping("/redis")
public class RedisTestController {

    private final RedisPublishService redisPublishService;
    private final List<RedisMessageEvent> receivedMessages = new ArrayList<>();

    public RedisTestController(RedisPublishService redisPublishService) {
        this.redisPublishService = redisPublishService;
    }

    @EventListener
    public void handleRedisMessage(RedisMessageEvent event) {
        receivedMessages.add(event);
    }

    @GetMapping("/messages")
    public ResponseEntity<List<RedisMessageEvent>> getMessages() {
        return ResponseEntity.ok(receivedMessages);
    }

    @PostMapping("/publish")
    public String publish(@RequestParam String channel, @RequestBody String message) {
        redisPublishService.publish(channel, message);
        return "published";
    }
}