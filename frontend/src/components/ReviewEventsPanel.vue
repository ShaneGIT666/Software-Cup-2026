<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { History, RefreshCw } from "@lucide/vue";
import { fetchReviewEvents, type KnowledgeReviewEvent } from "../api";

const events = ref<KnowledgeReviewEvent[]>([]);
const objectType = ref("all");
const loading = ref(false);
const loaded = ref(false);

function typeLabel(value: string) {
  if (value === "case") {
    return "维修案例";
  }
  if (value === "knowledge_chunk") {
    return "知识片段";
  }
  if (value === "knowledge_revision") {
    return "人工修正";
  }
  return value || "未知对象";
}

function actionLabel(value: string) {
  const labels: Record<string, string> = {
    approve: "通过",
    reject: "拒绝",
    revise: "修正"
  };
  if (value.startsWith("set_")) {
    return `状态变更：${value.slice(4)}`;
  }
  return labels[value] ?? value;
}

function eventTitle(event: KnowledgeReviewEvent) {
  return `${typeLabel(event.objectType)} · ${actionLabel(event.action)}`;
}

function afterSummary(event: KnowledgeReviewEvent) {
  const after = event.after ?? {};
  const content = after.content;
  const faultText = after.faultText;
  if (typeof content === "string" && content.trim()) {
    return content;
  }
  if (typeof faultText === "string" && faultText.trim()) {
    return faultText;
  }
  return event.reason || `${event.beforeStatus} -> ${event.afterStatus}`;
}

async function loadEvents() {
  loading.value = true;
  try {
    events.value = (
      await fetchReviewEvents({
        objectType: objectType.value === "all" ? undefined : objectType.value,
        limit: 20
      })
    ).items;
    loaded.value = true;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "审计流水加载失败");
  } finally {
    loading.value = false;
  }
}

onMounted(loadEvents);
</script>

<template>
  <section class="review-events-panel">
    <div class="section-title">
      <History :size="18" />
      <span>审核流水 / Audit Trail</span>
      <el-select v-model="objectType" size="small" class="audit-filter" @change="loadEvents">
        <el-option label="全部" value="all" />
        <el-option label="案例" value="case" />
        <el-option label="片段" value="knowledge_chunk" />
        <el-option label="修正" value="knowledge_revision" />
      </el-select>
      <el-button size="small" :loading="loading" title="刷新审核流水" aria-label="刷新审核流水" @click="loadEvents">
        <RefreshCw :size="14" />
      </el-button>
    </div>

    <div v-if="loading" class="loading-hint processing-card">
      <span>正在加载审计流水...</span>
    </div>

    <div v-if="loaded && !loading && events.length === 0" class="empty-hint">
      <span>暂无审计记录。</span>
    </div>

    <div v-if="loaded && !loading && events.length > 0" class="audit-list">
      <article v-for="event in events" :key="event.id" class="audit-row">
        <div class="audit-row-main">
          <strong>{{ eventTitle(event) }}</strong>
          <span>{{ event.reviewer || "operator" }} · {{ event.reviewTime?.slice(0, 19).replace("T", " ") }}</span>
        </div>
        <p>{{ afterSummary(event) }}</p>
        <div class="audit-row-meta">
          <el-tag size="small" type="info">{{ event.beforeStatus || "-" }}</el-tag>
          <span>-></span>
          <el-tag size="small" type="success">{{ event.afterStatus || "-" }}</el-tag>
          <small>{{ event.objectId }}</small>
        </div>
      </article>
    </div>
  </section>
</template>
