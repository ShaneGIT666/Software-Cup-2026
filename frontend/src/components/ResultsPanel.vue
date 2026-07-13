<script setup lang="ts">
import { FileText, MapPin, ShieldCheck } from "@lucide/vue";
import type { SearchPayload, SearchResult } from "../api";

defineProps<{
  searchPayload: SearchPayload | null;
  selectedResult: SearchResult | null;
}>();

const emit = defineEmits<{
  openWorkflow: [result: SearchResult];
}>();

function sourceLabel(sourceType: SearchResult["sourceType"]) {
  const labels: Record<SearchResult["sourceType"], string> = {
    manual: "手册",
    case: "案例",
    document: "资料",
    document_asset: "图片资料"
  };
  return labels[sourceType] ?? sourceType;
}
</script>

<template>
  <section class="results-panel">
    <div class="section-title">
      <FileText :size="18" />
      <span>步骤 2：查看参考依据</span>
    </div>
    <p class="panel-note">系统仅使用已审核资料生成正式建议，未审核内容不会进入检修依据。</p>

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
          <span class="source-line">{{ item.sourceName }}{{ item.chapter ? ` / ${item.chapter}` : "" }}</span>
          <p>{{ item.snippet }}</p>
          <small v-if="item.reason" class="reason-line">{{ item.reason }}</small>
          <div class="result-trace">
            <span>
              <MapPin :size="12" />
              {{ item.documentId || item.sourceId || item.id }}{{ item.chunkId ? ` / ${item.chunkId}` : "" }}{{ item.page ? ` / p.${item.page}` : "" }}
            </span>
            <span><ShieldCheck :size="12" />{{ item.reviewStatus === "approved" ? "已审核" : item.reviewStatus || "状态未知" }}</span>
          </div>
          <div class="confidence-row">
            <span>可信度 {{ Math.round(item.confidence * 100) }}%</span>
            <progress :value="Math.round(item.confidence * 100)" max="100" :aria-label="`${item.title} 可信度`"></progress>
            <small v-if="item.scoreBreakdown">排序分 {{ item.scoreBreakdown.score }}</small>
          </div>
        </button>
      </div>
    </template>
    <div v-else-if="searchPayload && searchPayload.results.length === 0" class="empty-hint">
      <span>暂无参考依据，请尝试补充设备型号、故障现象，或在管理中心上传相关资料。</span>
    </div>
    <div v-else class="empty-hint">
      <span>请先描述故障并点击“开始诊断”，系统会匹配已审核资料作为参考依据。</span>
    </div>
  </section>
</template>
