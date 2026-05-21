<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";
import { fetchWorkflow, searchKnowledge, submitCase, uploadFaultFile, type SearchPayload, type SearchResult, type UploadPayload, type WorkflowPayload } from "./api";
import CasePanel from "./components/CasePanel.vue";
import KnowledgePanel from "./components/KnowledgePanel.vue";
import QueryPanel from "./components/QueryPanel.vue";
import ResultsPanel from "./components/ResultsPanel.vue";
import ReviewPanel from "./components/ReviewPanel.vue";
import WorkflowPanel from "./components/WorkflowPanel.vue";

const deviceModel = ref("发动机-示例型号 A");
const faultText = ref("启动困难，怠速不稳，排气异常");
const loading = ref(false);
const submitting = ref(false);
const uploading = ref(false);
const searchPayload = ref<SearchPayload | null>(null);
const selectedWorkflow = ref<WorkflowPayload | null>(null);
const selectedResult = ref<SearchResult | null>(null);
const uploadResult = ref<UploadPayload | null>(null);
const reviewPanel = ref<InstanceType<typeof ReviewPanel> | null>(null);

const caseForm = ref({
  cause: "火花塞积碳",
  solution: "清理并更换火花塞，复查燃油滤清器。",
  result: "启动恢复正常，怠速稳定。",
  tags: "启动困难, 点火系统, 火花塞"
});

const resultCount = computed(() => searchPayload.value?.results.length ?? 0);

async function runSearch() {
  loading.value = true;
  selectedWorkflow.value = null;
  selectedResult.value = null;
  try {
    searchPayload.value = await searchKnowledge(deviceModel.value, faultText.value);
    const firstWorkflowId = searchPayload.value.results.find((item) => item.workflowId)?.workflowId;
    if (firstWorkflowId) {
      await openWorkflow(searchPayload.value.results[0]);
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "检索失败");
  } finally {
    loading.value = false;
  }
}

async function openWorkflow(result: SearchResult) {
  if (!result.workflowId) {
    ElMessage.warning("该结果暂未关联作业流程");
    return;
  }
  selectedResult.value = result;
  selectedWorkflow.value = await fetchWorkflow(result.workflowId);
}

async function createCase() {
  submitting.value = true;
  try {
    const result = await submitCase({
      deviceModel: deviceModel.value,
      faultText: faultText.value,
      cause: caseForm.value.cause,
      solution: caseForm.value.solution,
      result: caseForm.value.result,
      tags: caseForm.value.tags.split(",").map((tag) => tag.trim()).filter(Boolean)
    });
    ElMessage.success(`案例已提交：${result.id}`);
    reviewPanel.value?.loadCases();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "提交失败");
  } finally {
    submitting.value = false;
  }
}

async function uploadFile(file: File) {
  uploading.value = true;
  try {
    uploadResult.value = await uploadFaultFile(file);
    ElMessage.success(`文件已上传：${uploadResult.value.id}`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "上传失败");
  } finally {
    uploading.value = false;
  }
}

runSearch();
</script>

<template>
  <main class="shell">
    <section class="hero">
      <div>
        <p class="eyebrow">Software Cup 2026 · Maintenance Copilot</p>
        <h1>设备检修知识检索与作业辅助系统</h1>
        <p class="subtle">面向一线检修场景，把手册、案例、作业流程和审核沉淀整合到一个可演示的工业知识工作台。</p>
        <div class="hero-insights" aria-label="系统能力摘要">
          <span><strong>{{ resultCount }}</strong> 条当前结果</span>
          <span><strong>{{ selectedWorkflow?.steps.length ?? 0 }}</strong> 个作业步骤</span>
          <span><strong>{{ uploadResult ? "1" : "0" }}</strong> 份现场材料</span>
        </div>
      </div>
      <div class="status-strip">
        <span>可解释检索</span>
        <span>Mock 降级模式</span>
        <span>本地知识库</span>
      </div>
    </section>

    <section class="workspace">
      <QueryPanel
        v-model:device-model="deviceModel"
        v-model:fault-text="faultText"
        :loading="loading"
        :result-count="resultCount"
        :step-count="selectedWorkflow?.steps.length ?? 0"
        :upload-result="uploadResult"
        :uploading="uploading"
        @search="runSearch"
        @upload="uploadFile"
      />
      <ResultsPanel :search-payload="searchPayload" :selected-result="selectedResult" @open-workflow="openWorkflow" />
      <WorkflowPanel :selected-workflow="selectedWorkflow" />
      <KnowledgePanel />
      <CasePanel
        v-model:cause="caseForm.cause"
        v-model:solution="caseForm.solution"
        v-model:result="caseForm.result"
        v-model:tags="caseForm.tags"
        :submitting="submitting"
        @submit="createCase"
      />
      <ReviewPanel ref="reviewPanel" />
    </section>
  </main>
</template>
