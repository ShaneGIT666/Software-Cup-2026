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
  <section class="rag-panel panel-highlight">
    <div class="section-title">
      <Bot :size="18" />
      <span>RAG 辅助建议</span>
    </div>
    <p class="panel-note">
      基于当前检索证据生成带引用的检修建议。网络或 Key 不可用时，会使用本地兜底结果，保证演示不断链。
    </p>

    <div class="action-row">
      <el-button type="primary" :loading="loading" @click="emit('answer')">
        <Bot :size="16" />
        生成辅助建议
      </el-button>
      <el-tag v-if="ragAnswer?.fallback" type="warning">本地兜底</el-tag>
      <el-tag v-if="ragAnswer && !ragAnswer.fallback" type="success">云端增强</el-tag>
      <el-tag v-if="ragAnswer" type="info">{{ ragAnswer.provider }} / requested {{ ragAnswer.requestedProvider }}</el-tag>
      <el-tag v-if="ragAnswer?.model" type="info">{{ ragAnswer.model }} · {{ ragAnswer.apiStyle }}</el-tag>
      <el-tag v-if="ragAnswer?.contextCount !== undefined" type="info">
        {{ ragAnswer.contextCount }} 条上下文 / {{ ragAnswer.contextChars ?? 0 }} 字符
      </el-tag>
    </div>

    <div v-if="loading" class="loading-hint processing-card">
      <span>正在组织检索上下文、引用来源和检修建议...</span>
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
          <small>
            {{ citation.sourceName }}
            {{ citation.scoreBreakdown ? ` · 排序分 ${citation.scoreBreakdown.score}` : "" }}
            {{ citation.page ? ` · p.${citation.page}` : "" }}
          </small>
          <p>{{ citation.snippet }}</p>
        </div>
      </div>
      <small v-if="ragAnswer.fallbackReason" class="fallback-note">{{ ragAnswer.fallbackReason }}</small>
    </article>
    <div v-else class="empty-hint">
      <span>先完成检索或资料入库，再生成带引用的辅助建议。</span>
    </div>
  </section>
</template>
