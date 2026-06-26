<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  fetchKnowledgeGraph,
  fetchKnowledgeGraphOverview,
  fetchProviderStatus,
  fetchWorkflow,
  rebuildKnowledgeGraph,
  requestMultimodalDiagnosis,
  requestRagAnswer,
  searchKnowledge,
  submitCase,
  uploadFaultFile,
  type KnowledgeGraphPayload,
  type MultimodalDiagnosisPayload,
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
import ReviewEventsPanel from "./components/ReviewEventsPanel.vue";
import ReviewPanel from "./components/ReviewPanel.vue";
import WorkflowPanel from "./components/WorkflowPanel.vue";

const deviceModel = ref("发动机-示例型号 A");
const faultText = ref("启动困难，怠速不稳，排气异常");
const maintenanceLevel = ref("normal_repair");
const loading = ref(false);
const graphLoading = ref(false);
const ragLoading = ref(false);
const submitting = ref(false);
const uploading = ref(false);
const diagnosisLoading = ref(false);
const searchPayload = ref<SearchPayload | null>(null);
const knowledgeGraph = ref<KnowledgeGraphPayload | null>(null);
const selectedWorkflow = ref<WorkflowPayload | null>(null);
const selectedResult = ref<SearchResult | null>(null);
const uploadResult = ref<UploadPayload | null>(null);
const ragAnswer = ref<RagAnswerPayload | null>(null);
const multimodalDiagnosis = ref<MultimodalDiagnosisPayload | null>(null);
const providerStatus = ref<ProviderStatusPayload | null>(null);
const reviewPanel = ref<InstanceType<typeof ReviewPanel> | null>(null);

const caseForm = ref({
  cause: "火花塞积碳导致点火能量不足。",
  solution: "清理并更换火花塞，复查燃油滤清器。",
  result: "启动恢复正常，怠速稳定。",
  tags: "启动困难, 点火系统, 火花塞"
});

const resultCount = computed(() => searchPayload.value?.results.length ?? 0);
const documentNodeCount = computed(() => knowledgeGraph.value?.nodes.filter((node) => node.type === "document").length ?? 0);
const graphEdgeCount = computed(() => knowledgeGraph.value?.edges.length ?? 0);
const diagnosisSummary = computed(() => {
  const diagnosis = multimodalDiagnosis.value;
  if (!diagnosis) {
    return "";
  }
  return diagnosis.imageAnalysis.summary || diagnosis.queryContext.ocrText || diagnosis.queryContext.imageClues[0] || "已完成图片诊断。";
});

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
  const embedding = providerStatus.value.embedding;
  const ocr = providerStatus.value.ocr;
  const embeddingProvider = embedding?.effectiveProvider ?? "hash";
  const ocrProvider = ocr?.effectiveProvider ?? "mock";
  return `LLM ${llm.effectiveProvider} / 多模态 ${multimodal.effectiveProvider} / OCR ${ocrProvider} / 向量 ${embeddingProvider}`;
});

const systemStatus = computed(() => providerStatus.value?.system ?? null);

const systemMetricItems = computed(() => {
  const system = systemStatus.value;
  if (!system) {
    return [];
  }
  return [
    {
      label: "知识片段",
      value: system.knowledge.chunkCount,
      detail: `${system.knowledge.approvedChunkCount} 已审核`
    },
    {
      label: "待审核",
      value: system.knowledge.pendingReviewCount,
      detail: "资料/片段/案例"
    },
    {
      label: "可检索源",
      value: system.knowledge.retrievableSourceCount,
      detail: "手册+案例+片段"
    },
    {
      label: "修正记录",
      value: system.knowledge.revisionCount,
      detail: "人工修正"
    }
  ];
});

const systemSignalItems = computed(() => {
  const system = systemStatus.value;
  if (!system) {
    return [];
  }
  const latestTask = system.parsing.latestTask;
  const latestTaskLabel = latestTask
    ? `${latestTask.fileName || latestTask.documentId} / ${latestTask.status || "unknown"}`
    : "暂无解析任务";
  const latestIndexLabel =
    system.indexing.latestIndexTime ?? system.indexing.latestKnownIndexActivityAt ?? "未记录";
  return [
    `MinerU ${system.parsing.mineru.status}`,
    `Chroma ${system.indexing.chroma.status}`,
    `最近解析：${latestTaskLabel}`,
    `最近索引：${latestIndexLabel}`
  ];
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
    searchPayload.value = await searchKnowledge(deviceModel.value, faultText.value, maintenanceLevel.value);
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
    ragAnswer.value = await requestRagAnswer(deviceModel.value, faultText.value, undefined, maintenanceLevel.value);
    await refreshProviderStatus();
    ElMessage.success(ragAnswer.value.fallback ? "已生成本地兜底建议" : "已生成云端增强建议");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "辅助建议生成失败");
  } finally {
    ragLoading.value = false;
  }
}

async function runMultimodalDiagnosis(file: File | null) {
  diagnosisLoading.value = true;
  ragAnswer.value = null;
  try {
    multimodalDiagnosis.value = await requestMultimodalDiagnosis({
      deviceModel: deviceModel.value,
      faultText: faultText.value,
      maintenanceLevel: maintenanceLevel.value,
      riskLevel: maintenanceLevel.value === "emergency" ? "critical" : "medium",
      image: file,
      topK: 5
    });
    if (multimodalDiagnosis.value.raw) {
      ragAnswer.value = multimodalDiagnosis.value.raw;
    }
    await refreshProviderStatus();
    await refreshKnowledgeGraph();
    ElMessage.success(multimodalDiagnosis.value.fallback ? "图片诊断已降级完成" : "图片诊断已完成");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "图片诊断失败");
  } finally {
    diagnosisLoading.value = false;
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

async function loadKnowledgeGraphOverview() {
  graphLoading.value = true;
  try {
    knowledgeGraph.value = await fetchKnowledgeGraphOverview();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "知识图谱总览读取失败");
  } finally {
    graphLoading.value = false;
  }
}

async function rebuildKnowledgeGraphOverview() {
  graphLoading.value = true;
  try {
    knowledgeGraph.value = await rebuildKnowledgeGraph();
    ElMessage.success("知识图谱已根据资料、案例和流程重建");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "知识图谱重建失败");
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
      experienceSummary: `${caseForm.value.cause} ${caseForm.value.solution}`,
      lessonsLearned: caseForm.value.result,
      maintenanceLevel: maintenanceLevel.value,
      tags: caseForm.value.tags.split(",").map((tag) => tag.trim()).filter(Boolean)
    });
    ElMessage.success(`案例 / 经验总结已提交审核：${result.id}`);
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
    ElMessage.success(`现场资料已上传：${uploadResult.value.fileName}`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "现场资料上传失败");
  } finally {
    uploading.value = false;
  }
}

refreshProviderStatus();
runSearch();
</script>

<template>
  <main class="shell">
    <header class="app-header">
      <div>
        <h1>设备检修知识检索与作业辅助系统</h1>
        <p>
          输入设备与故障现象，先获得可追溯证据和标准作业步骤，再按需进入 RAG 建议、资料入库和案例沉淀。
        </p>
      </div>
      <aside class="status-panel" :class="providerToneClass">
        <span>{{ providerModeLabel }}</span>
        <strong>{{ providerDetailLabel }}</strong>
        <div v-if="systemMetricItems.length" class="status-metrics" aria-label="系统状态摘要">
          <div v-for="item in systemMetricItems" :key="item.label">
            <b>{{ item.value }}</b>
            <span>{{ item.label }}</span>
            <small>{{ item.detail }}</small>
          </div>
        </div>
        <div v-if="systemSignalItems.length" class="status-signals">
          <span v-for="item in systemSignalItems" :key="item">{{ item }}</span>
        </div>
      </aside>
    </header>

    <section class="task-summary" aria-label="当前检修上下文">
      <div>
        <span>检索诊断</span>
        <strong>{{ deviceModel }}</strong>
      </div>
      <div>
        <span>证据命中</span>
        <strong>{{ resultCount }}</strong>
      </div>
      <div>
        <span>资料入库 / 审核</span>
        <strong>{{ systemStatus?.knowledge.pendingReviewCount ?? 0 }}</strong>
      </div>
      <div>
        <span>RAG 建议 / 证据</span>
        <strong>{{ documentNodeCount + graphEdgeCount }}</strong>
      </div>
    </section>

    <section class="workspace">
      <QueryPanel
        v-model:device-model="deviceModel"
        v-model:fault-text="faultText"
        v-model:maintenance-level="maintenanceLevel"
        :loading="loading"
        :diagnosis-loading="diagnosisLoading"
        :result-count="resultCount"
        :step-count="selectedWorkflow?.steps.length ?? 0"
        :upload-result="uploadResult"
        :uploading="uploading"
        :diagnosis-summary="diagnosisSummary"
        :diagnosis-fallback="multimodalDiagnosis?.fallback ?? false"
        @search="runSearch"
        @upload="uploadFile"
        @diagnose="runMultimodalDiagnosis"
      />
      <ResultsPanel :search-payload="searchPayload" :selected-result="selectedResult" @open-workflow="openWorkflow" />
      <WorkflowPanel :selected-workflow="selectedWorkflow" />
    </section>

    <section class="secondary-workspace" aria-label="知识维护与增强能力">
      <KnowledgePanel />
      <RagPanel :rag-answer="ragAnswer" :loading="ragLoading" @answer="generateRagAnswer" />
      <KnowledgeGraphPanel
        :graph="knowledgeGraph"
        :loading="graphLoading"
        @refresh="refreshKnowledgeGraph"
        @overview="loadKnowledgeGraphOverview"
        @rebuild="rebuildKnowledgeGraphOverview"
      />
      <CasePanel
        v-model:cause="caseForm.cause"
        v-model:solution="caseForm.solution"
        v-model:result="caseForm.result"
        v-model:tags="caseForm.tags"
        :submitting="submitting"
        @submit="createCase"
      />
      <ReviewPanel ref="reviewPanel" />
      <ReviewEventsPanel />
    </section>
  </main>
</template>
