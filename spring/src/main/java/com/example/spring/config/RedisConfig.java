package com.example.spring.config;

import com.example.spring.redis.RedisSubscriber;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.RedisConnectionFactory;
// PatternTopic을 import 해야 합니다!
import org.springframework.data.redis.listener.PatternTopic;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;

@Configuration
public class RedisConfig {

    @Bean
    public RedisMessageListenerContainer redisMessageListenerContainer(
            RedisConnectionFactory connectionFactory,
            RedisSubscriber redisSubscriber) {

        RedisMessageListenerContainer container = new RedisMessageListenerContainer();
        container.setConnectionFactory(connectionFactory);

        // [Spring → Django] 발행용 채널명 리스트
        String[] springPublishChannels = {
                "booth:*:order:*",
                "booth:*:staffcall:*"
        };

        // [Django → Spring] 구독용 채널명 리스트
        String[] djangoSubscribeChannels = {
                "booth:*:order:*",
                "booth:*:staffcall:*"
        };

        // ChannelTopic -> PatternTopic 으로 변경해야 와일드카드(*)가 정상 작동합니다!
        for (String channel : springPublishChannels) {
            container.addMessageListener(redisSubscriber, new PatternTopic("spring:" + channel));
        }

        for (String channel : djangoSubscribeChannels) {
            container.addMessageListener(redisSubscriber, new PatternTopic("django:" + channel));
        }

        return container;
    }
}