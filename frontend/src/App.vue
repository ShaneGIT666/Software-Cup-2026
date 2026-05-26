<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  fetchKnowledgeGraph,
  fetchProviderStatus,
  fetchWorkflow,
  requestRagAnswer,
  searchKnowledge,
  submitCase,
  uploadFaultFile,
  type KnowledgeGraphPayload,
  type ProviderStatusPayload,
  type RagAnswerPayload,
  type SearchPayload,
  type SearchResult,
  type UploadPayload,
  type WorkflowPayload
} from "./api";
import CasePanel from "./components/CasePanel.vue";
import KnowledgeGraphPanel from "./components/KnowledgeGraphPanel.vue";
import KnowledgePanel from "./components/KnowledgePanel.vue";
import QueryPanel from "./components/QueryPanel.vue";
import RagPanel from "./components/RagPanel.vue";
import ResultsPanel from "./components/ResultsPanel.vue";
import ReviewPanel from "./components/ReviewPanel.vue";
import WorkflowPanel from "./components/WorkflowPanel.vue";

const deviceModel = ref("发动机-示例型号 A");
const faultText = ref("启动困难，怠速不稳，排气异常");
const loading = ref(false);
const graphLoading = ref(false);
const ragLoading = ref(false);
const submitting = ref(false);
const uploading = ref(false);
const searchPayload = ref<SearchPayload | null>(null);
const knowledgeGraph = ref<KnowledgeGraphPayload | null>(null);
const selectedWorkflow = ref<WorkflowPayload | null>(null);
const selectedResult = ref<SearchResult | null>(null);
const uploadResult = ref<UploadPayload | null>(null);
const ragAnswer = ref<RagAnswerPayload | null>(null);
const providerStatus = ref<ProviderStatusPayload | null>(null);
const reviewPanel = ref<InstanceType<typeof ReviewPanel> | null>(null);

const caseForm = ref({
  cause: "火花塞积碳",
  solution: "清理并更换火花塞，复查燃油滤清器。",
  result: "启动恢复正常，怠速稳定。",
  tags: "启动困难, 点火系统, 火花塞"
});

const resultCount = computed(() => searchPayload.value?.results.length ?? 0);
const documentNodeCount = computed(() => knowledgeGraph.value?.nodes.filter((node) => node.type === "document").length ?? 0);

const providerModeLabel = computed(() => {
  if (!providerStatus.value) {
    return "Provider 状态读取中";
  }
  if (providerStatus.value.offlineFallback) {
    return "离线兜底模式";
  }
  const llm = providerStatus.value.llm;
  return llm.effectiveProvider === "mock" ? "本地兜底结果" : `云端增强：${llm.effectiveProvider}`;
});

const providerDetailLabel = computed(() => {
  if (!providerStatus.value) {
    return "等待后端状态";
  }
  const llm = providerStatus.value.llm;
  const multimodal = providerStatus.value.multimodal;
  return `RAG ${llm.effectiveProvider} / 多模态 ${multimodal.effectiveProvider}`;
});

const providerToneClass = computed(() => ({
  "is-offline": providerStatus.value?.offlineFallback,
  "is-cloud": providerStatus.value && providerStatus.value.llm.effectiveProvider !== "mock",
  "is-local": !providerStatus.value || providerStatus.value.llm.effectiveProvider === "mock"
}));

async function refreshProviderStatus() {
  try {
    providerStatus.value = await fetchProviderStatus();
  } catch {
    providerStatus.value = null;
  }
}

async function runSearch() {
  loading.value = true;
  selectedWorkflow.value = null;
  selectedResult.value = null;
  ragAnswer.value = null;
  try {
    searchPayload.value = await searchKnowledge(deviceModel.value, faultText.value);
    const firstResultWithWorkflow = searchPayload.value.results.find((item) => item.workflowId);
    if (firstResultWithWorkflow) {
      await openWorkflow(firstResultWithWorkflow);
    }
    await refreshKnowledgeGraph();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "检索失败，请检查输入或后端服务。");
  } finally {
    loading.value = false;
  }
}

async function generateRagAnswer() {
  ragLoading.value = true;
  try {
    ragAnswer.value = await requestRagAnswer(deviceModel.value, faultText.value);
    await refreshProviderStatus();
    ElMessage.success(ragAnswer.value.fallback ? "已生成本地兜底建议" : "已生成云端增强建议");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "辅助建议生成失败");
  } finally {
    ragLoading.value = false;
  }
}

async function refreshKnowledgeGraph() {
  graphLoading.value = true;
  try {
    knowledgeGraph.value = await fetchKnowledgeGraph(deviceModel.value, faultText.value);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "知识关系网络生成失败");
  } finally {
    graphLoading.value = false;
  }
}

async function openWorkflow(result: SearchResult) {
  if (!result.workflowId) {
    ElMessage.warning("该证据暂未关联标准作业流程");
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
    ElMessage.success(`案例已提交审核：${result.id}`);
    reviewPanel.value?.loadCases();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "案例提交失败");
  } finally {
    submitting.value = false;
  }
}

async function uploadFile(file: File) {
  uploading.value = true;
  try {
    uploadResult.value = await uploadFaultFile(file);
    ElMessage.success(`现场材料已上传：${uploadResult.value.fileName}`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "现场材料上传失败");
  } finally {
    uploading.value = false;
  }
}

refreshProviderStatus();
runSearch();
</script>

<template>
  <main class="shell">
    <section class="hero">
      <div class="hero-copy">
        <p class="eyebrow">Software Cup 2026 · Maintenance Copilot</p>
        <h1>设备检修知识检索与作业指挥台</h1>
        <p class="subtle">
          面向一线检修场景，把手册、案例、资料入库、RAG 引用回答、标准作业流程和审核沉淀汇聚成一个可演示、可追溯、可兜底的工业 AI 工作台。
        </p>
        <div class="hero-insights" aria-label="系统态势总览">
          <span><strong>{{ resultCount }}</strong> 条证据命中</span>
          <span><strong>{{ selectedWorkflow?.steps.length ?? 0 }}</strong> 个作业步骤</span>
          <span><strong>{{ documentNodeCount }}</strong> 个资料节点</span>
          <span><strong>{{ ragAnswer?.citations.length ?? 0 }}</strong> 条回答引用</span>
        </div>
      </div>

      <aside class="command-card" :class="providerToneClass">
        <span class="command-label">运行状态</span>
        <strong>{{ providerModeLabel }}</strong>
        <p>{{ providerDetailLabel }}</p>
        <div class="status-strip">
          <span>可解释检索</span>
          <span>本地知识库</span>
          <span>弱网兜底</span>
        </div>
      </aside>
    </section>

    <nav class="demo-flow" aria-label="演示流程">
      <span class="flow-step active">1 输入故障</span>
      <span class="flow-step">2 检索证据</span>
      <span class="flow-step">3 作业指引</span>
      <span class="flow-step">4 资料入库</span>
      <span class="flow-step">5 RAG 建议</span>
      <span class="flow-step">6 审核沉淀</span>
    </nav>

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
      <RagPanel :rag-answer="ragAnswer" :loading="ragLoading" @answer="generateRagAnswer" />
      <KnowledgeGraphPanel :graph="knowledgeGraph" :loading="graphLoading" @refresh="refreshKnowledgeGraph" />
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
