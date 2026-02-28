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

        // [Spring → Django] 발행용 채널명 리스트 (spring: 접두사 자동 추가)
        String[] springPublishChannels = {
            "booth:*:order:*",
            "booth:*:staffcall:*"
            
        };

        // [Django → Spring] 구독용 채널명 리스트 (django: 접두사 자동 추가)
        String[] djangoSubscribeChannels = {
            "booth:*:order:*",
            "booth:*:staffcall:*"
        };

        // spring: 채널은 발행용이지만, 필요시 구독도 가능
        for (String channel : springPublishChannels) {
            container.addMessageListener(redisSubscriber, new ChannelTopic("spring:" + channel));
        }

        // django: 채널은 장고에서 발행한 메시지 구독 (접두사 자동 추가)
        for (String channel : djangoSubscribeChannels) {
            container.addMessageListener(redisSubscriber, new ChannelTopic("django:" + channel));
        }

        return container;
    }
}
