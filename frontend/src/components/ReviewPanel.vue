<script setup lang="ts">
import { ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Check, Eye, X } from "@lucide/vue";
import { fetchReviewItems, reviewCase, reviewKnowledgeChunk, type ReviewItem } from "../api";

const items = ref<ReviewItem[]>([]);
const loading = ref(false);
const loaded = ref(false);
const reviewing = ref<Record<string, boolean>>({});

function typeLabel(item: ReviewItem) {
  if (item.objectType === "knowledge_chunk") {
    return "知识片段";
  }
  if (item.objectType === "case") {
    return "维修案例";
  }
  return item.objectType;
}

function locationLabel(item: ReviewItem) {
  const parts = [item.fileName, item.page ? `p.${item.page}` : "", item.section].filter(Boolean);
  return parts.join(" / ") || item.sourceName;
}

async function loadCases() {
  loading.value = true;
  try {
    items.value = (await fetchReviewItems("pending_review")).items;
    loaded.value = true;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "待审核内容加载失败");
  } finally {
    loading.value = false;
  }
}

async function confirmReview(item: ReviewItem, action: "approve" | "reject") {
  const label = action === "approve" ? "通过" : "拒绝";
  if (action === "reject") {
    try {
      const result = await ElMessageBox.prompt(
        `请填写拒绝「${item.title}」的原因。`,
        `${typeLabel(item)}审核：${label}`,
        {
          confirmButtonText: label,
          cancelButtonText: "取消",
          inputPlaceholder: "例如：来源不清晰、内容与设备型号不匹配、需要重新 OCR",
          inputValidator: (value) => Boolean(value.trim()) || "拒绝审核必须填写原因",
          type: "warning"
        }
      );
      return result.value.trim();
    } catch {
      return null;
    }
  }

  try {
    await ElMessageBox.confirm(`确认通过「${item.title}」？`, `${typeLabel(item)}审核：${label}`, {
      confirmButtonText: label,
      cancelButtonText: "取消",
      type: "success"
    });
    return "";
  } catch {
    return null;
  }
}

async function handleReview(item: ReviewItem, action: "approve" | "reject") {
  const reason = await confirmReview(item, action);
  if (reason === null) {
    return;
  }

  reviewing.value[item.id] = true;
  try {
    if (item.objectType === "case") {
      await reviewCase(item.caseId || item.objectId, action, reason, "operator");
    } else if (item.objectType === "knowledge_chunk" && item.documentId && item.chunkId) {
      await reviewKnowledgeChunk(item.documentId, item.chunkId, { action, reason, reviewer: "operator" });
    } else {
      throw new Error("该审核对象暂不支持操作");
    }
    ElMessage.success(`${typeLabel(item)}已${action === "approve" ? "通过" : "拒绝"}`);
    items.value = items.value.filter((candidate) => candidate.id !== item.id);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "审核操作失败");
  } finally {
    reviewing.value[item.id] = false;
  }
}

defineExpose({ loadCases });
</script>

<template>
  <section class="review-panel">
    <div class="section-title">
      <Eye :size="18" />
      <span>审核入库 / Quality Gate</span>
      <el-button size="small" :loading="loading" @click="loadCases">刷新</el-button>
    </div>
    <p class="panel-note">
      统一查看维修案例和资料片段。通过后进入正式检索链路，拒绝时必须留下原因，便于后续修正和追溯。
    </p>

    <div v-if="!loaded && !loading" class="empty-hint">
      <span>点击“刷新”加载待审核内容。</span>
    </div>

    <div v-if="loading" class="loading-hint processing-card">
      <span>正在加载待审核内容...</span>
    </div>

    <div v-if="loaded && !loading && items.length === 0" class="empty-hint">
      <span>暂无待审核内容。</span>
    </div>

    <div v-if="loaded && !loading && items.length > 0" class="review-list">
      <div v-for="item in items" :key="item.id" class="review-card">
        <div class="review-card-header">
          <strong>{{ item.title }}</strong>
          <el-tag size="small" type="warning">{{ typeLabel(item) }}</el-tag>
        </div>
        <div class="review-card-meta">
          <span>{{ item.deviceModel || locationLabel(item) }}</span>
          <span>{{ item.createdAt?.slice(0, 10) }}</span>
        </div>
        <p class="review-card-text">{{ item.content }}</p>
        <div v-if="item.summary" class="review-card-text">
          <span class="label">摘要：</span>{{ item.summary }}
        </div>
        <div v-if="item.objectType === 'knowledge_chunk'" class="review-card-text">
          <span class="label">来源：</span>{{ locationLabel(item) }}
        </div>
        <div v-if="item.tags?.length" class="review-card-tags">
          <el-tag v-for="tag in item.tags.slice(0, 6)" :key="tag" size="small" type="info">{{ tag }}</el-tag>
        </div>
        <div class="review-card-actions">
          <el-button size="small" type="success" :loading="reviewing[item.id]" @click="handleReview(item, 'approve')">
            <Check :size="14" />
            通过
          </el-button>
          <el-button size="small" type="danger" :loading="reviewing[item.id]" @click="handleReview(item, 'reject')">
            <X :size="14" />
            拒绝
          </el-button>
        </div>
      </div>
    </div>
  </section>
</template>
