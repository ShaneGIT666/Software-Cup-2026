<script setup lang="ts">
import { Bot, Quote } from "@lucide/vue";
import type { RagAnswerPayload } from "../api";

defineProps<{
  ragAnswer: RagAnswerPayload | null;
  loading: boolean;
}>();

const emit = defineEmits<{
  answer: [];
}>();

function sourceLabel(sourceType: string) {
  const labels: Record<string, string> = {
    manual: "手册",
    case: "案例",
    document: "资料"
  };
  return labels[sourceType] ?? sourceType;
}
</script>

<template>
  <section class="rag-panel">
    <div class="section-title">
      <Bot :size="18" />
      <span>RAG 辅助建议</span>
    </div>
    <p class="panel-note">基于当前检索结果生成带引用的 Mock 回答。无模型密钥也可演示，后续可替换为 OpenAI/Anthropic Provider。</p>

    <div class="action-row">
      <el-button type="primary" :loading="loading" @click="emit('answer')">
        <Bot :size="16" />
        生成辅助建议
      </el-button>
      <el-tag v-if="ragAnswer?.fallback" type="warning">Mock 降级</el-tag>
      <el-tag v-if="ragAnswer" type="info">{{ ragAnswer.provider }} / requested {{ ragAnswer.requestedProvider }}</el-tag>
    </div>

    <div v-if="loading" class="loading-hint">
      <span>正在组织检索上下文...</span>
    </div>
    <article v-else-if="ragAnswer" class="rag-answer">
      <p>{{ ragAnswer.answer }}</p>
      <div class="rag-actions">
        <strong>建议动作</strong>
        <ul>
          <li v-for="action in ragAnswer.recommendedActions" :key="action">{{ action }}</li>
        </ul>
      </div>
      <div class="citation-list">
        <strong>
          <Quote :size="15" />
          引用来源
        </strong>
        <div v-for="citation in ragAnswer.citations" :key="citation.id" class="citation-card">
          <span class="source-pill">{{ sourceLabel(citation.sourceType) }}</span>
          <strong>{{ citation.title }}</strong>
          <small>{{ citation.sourceName }} {{ citation.page ? ` · p.${citation.page}` : "" }}</small>
          <p>{{ citation.snippet }}</p>
        </div>
      </div>
      <small v-if="ragAnswer.fallbackReason" class="fallback-note">{{ ragAnswer.fallbackReason }}</small>
    </article>
    <div v-else class="empty-hint">
      <span>先完成检索或入库资料，再生成带引用的辅助建议。</span>
    </div>
  </section>
</template>
