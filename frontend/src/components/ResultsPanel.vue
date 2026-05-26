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

function sourceLabel(sourceType: SearchResult["sourceType"]) {
  const labels = {
    manual: "手册",
    case: "案例",
    document: "资料"
  };
  return labels[sourceType];
}
</script>

<template>
  <section class="results-panel">
    <div class="section-title">
      <FileText :size="18" />
      <span>证据检索</span>
    </div>
    <template v-if="searchPayload && searchPayload.results.length">
      <p class="summary">{{ searchPayload.summary }}</p>
      <div class="result-list">
        <button
          v-for="item in searchPayload.results"
          :key="item.id"
          class="result-item"
          :class="{ active: selectedResult?.id === item.id }"
          @click="emit('openWorkflow', item)"
        >
          <div>
            <strong>{{ item.title }}</strong>
            <span class="source-pill">{{ sourceLabel(item.sourceType) }}</span>
          </div>
          <span class="source-line">{{ item.sourceName }} {{ item.chapter ? ` / ${item.chapter}` : "" }}</span>
          <p>{{ item.snippet }}</p>
          <small v-if="item.reason" class="reason-line">{{ item.reason }}</small>
          <small>
            置信度 {{ Math.round(item.confidence * 100) }}%
            {{ item.scoreBreakdown ? ` · 排序分 ${item.scoreBreakdown.score}` : "" }}
            {{ item.page ? ` · p.${item.page}` : "" }}
          </small>
        </button>
      </div>
    </template>
    <div v-else-if="searchPayload && searchPayload.results.length === 0" class="empty-hint">
      <span>未找到匹配结果，可调整故障描述或更换设备型号。</span>
    </div>
    <div v-else class="empty-hint">
      <span>输入设备型号和故障现象后开始检索。</span>
    </div>
  </section>
</template>
