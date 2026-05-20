<script setup lang="ts">
import { ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { Check, Eye, X } from "@lucide/vue";
import { fetchCases, reviewCase, type CaseItem } from "../api";

const cases = ref<CaseItem[]>([]);
const loading = ref(false);
const loaded = ref(false);
const reviewing = ref<Record<string, boolean>>({});

async function loadCases() {
  loading.value = true;
  try {
    cases.value = (await fetchCases("pending_review")).items;
    loaded.value = true;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载待审核案例失败");
  } finally {
    loading.value = false;
  }
}

async function handleReview(caseItem: CaseItem, action: "approve" | "reject") {
  const label = action === "approve" ? "通过" : "拒绝";
  try {
    await ElMessageBox.confirm(
      `确认${label}案例「${caseItem.faultTitle}」？`,
      `审核${label}`,
      { confirmButtonText: label, cancelButtonText: "取消", type: action === "approve" ? "success" : "warning" }
    );
  } catch {
    return;
  }

  reviewing.value[caseItem.id] = true;
  try {
    await reviewCase(caseItem.id, action);
    ElMessage.success(`案例已${label}`);
    cases.value = cases.value.filter((item) => item.id !== caseItem.id);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : `审核${label}失败`);
  } finally {
    reviewing.value[caseItem.id] = false;
  }
}

defineExpose({ loadCases });
</script>

<template>
  <section class="review-panel">
    <div class="section-title">
      <Eye :size="18" />
      <span>案例审核</span>
      <el-button size="small" :loading="loading" @click="loadCases">刷新</el-button>
    </div>

    <div v-if="!loaded && !loading" class="empty-hint">
      <span>点击「刷新」加载待审核案例</span>
    </div>

    <div v-if="loading" class="loading-hint">
      <span>加载待审核案例中...</span>
    </div>

    <div v-if="loaded && !loading && cases.length === 0" class="empty-hint">
      <span>暂无待审核案例</span>
    </div>

    <div v-if="loaded && !loading && cases.length > 0" class="review-list">
      <div v-for="item in cases" :key="item.id" class="review-card">
        <div class="review-card-header">
          <strong>{{ item.faultTitle }}</strong>
          <el-tag size="small" type="warning">待审核</el-tag>
        </div>
        <div class="review-card-meta">
          <span>{{ item.deviceModel }}</span>
          <span>{{ item.createdAt?.slice(0, 10) }}</span>
        </div>
        <p class="review-card-text">{{ item.faultText }}</p>
        <div v-if="item.solution" class="review-card-text">
          <span class="label">方案：</span>{{ item.solution }}
        </div>
        <div class="review-card-tags">
          <el-tag v-for="tag in item.tags" :key="tag" size="small" type="info">{{ tag }}</el-tag>
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
