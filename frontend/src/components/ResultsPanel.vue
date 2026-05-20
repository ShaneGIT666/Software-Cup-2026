<script setup lang="ts">
import { FileText } from "@lucide/vue";
import type { SearchPayload, SearchResult } from "../api";

defineProps<{
  searchPayload: SearchPayload | null;
  selectedResult: SearchResult | null;
}>();

const emit = defineEmits<{
  openWorkflow: [result: SearchResult];
}>();
</script>

<template>
  <section class="results-panel">
    <div class="section-title">
      <FileText :size="18" />
      <span>知识结果</span>
    </div>
    <p class="summary">{{ searchPayload?.summary }}</p>
    <div class="result-list">
      <button
        v-for="item in searchPayload?.results"
        :key="item.id"
        class="result-item"
        :class="{ active: selectedResult?.id === item.id }"
        @click="emit('openWorkflow', item)"
      >
        <div>
          <strong>{{ item.title }}</strong>
          <span>{{ item.sourceName }} {{ item.chapter ? ` / ${item.chapter}` : "" }}</span>
        </div>
        <p>{{ item.snippet }}</p>
        <small>置信度 {{ Math.round(item.confidence * 100) }}%</small>
      </button>
    </div>
  </section>
</template>
