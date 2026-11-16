<script setup lang="ts">
/**
 * 探索結果報告 →「對話紀錄」分頁。對應 Figma「Student_Result_02」（node 785:4795）。
 * 白色卡片裡依序列出這次的對話；AI 訊息下面有喇叭，可以用瀏覽器語音朗讀。
 *
 * 用法：<ChatRecordTab :messages="messages" />
 *   messages 就是 GET /sessions/{sessionId}/messages 回傳的 `messages`。
 */
import ChatBubble from '@/components/common/ChatBubble.vue'
import SpeakButton from '@/components/common/SpeakButton.vue'
import type { SessionMessage } from '@/api/sessions'

defineProps<{
  messages: SessionMessage[]
  /** 學生頭像旁的名字，預設「學生」 */
  studentName?: string
}>()
</script>

<template>
  <ol
    class="flex flex-col gap-[22px] rounded-2xl bg-card px-4 py-2 shadow-elevated sm:px-5"
    aria-label="對話紀錄"
  >
    <li v-for="message in messages" :key="message.message_id" class="flex flex-col">
      <ChatBubble
        :from="message.sender"
        :name="message.sender === 'student' ? studentName : undefined"
      >
        {{ message.content }}
        <template v-if="message.sender === 'ai'" #after>
          <SpeakButton :id="message.message_id" :text="message.content" />
        </template>
      </ChatBubble>
    </li>
  </ol>
</template>
