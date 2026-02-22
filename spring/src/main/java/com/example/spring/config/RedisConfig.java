package com.example.spring.config;

import com.example.spring.redis.RedisSubscriber;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.listener.ChannelTopic;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;

@Configuration
public class RedisConfig {

    @Bean
    public RedisMessageListenerContainer redisMessageListenerContainer(
            RedisConnectionFactory connectionFactory,
            RedisSubscriber redisSubscriber) {

        RedisMessageListenerContainer container = new RedisMessageListenerContainer();
        container.setConnectionFactory(connectionFactory);

        // 예시 채널명: 실제 운영 채널명에 맞게 수정 필요
        container.addMessageListener(redisSubscriber, new ChannelTopic("booth:1:order:new"));
        container.addMessageListener(redisSubscriber, new ChannelTopic("booth:1:staffcall:newcall"));
        container.addMessageListener(redisSubscriber, new ChannelTopic("test:1:testname:moving"));

        return container;
    }
}
