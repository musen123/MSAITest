<template>
  <div class="chat-fullpage">
    <ChatPanel :project-id="projectId" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import ChatPanel from '@/components/chat/ChatPanel.vue'

const route = useRoute()
const projectId = computed(() => Number(route.params.id))
</script>

<style scoped>
.chat-fullpage {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: white;
  border-radius: 8px;
  overflow: hidden;
  margin: 16px;
  box-shadow: 0 2px 8px rgba(var(--theme-rgb-black), 0.04);
}
</style>
