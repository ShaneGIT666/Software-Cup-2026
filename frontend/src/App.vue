<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  Activity,
  BookOpenCheck,
  Bot,
  Boxes,
  ChevronRight,
  ClipboardCheck,
  Database,
  LayoutDashboard,
  Menu,
  Network,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Wrench
} from "@lucide/vue";
import {
  clearAuthToken,
  fetchKnowledgeGraph,
  fetchKnowledgeGraphOverview,
  fetchProviderStatus,
  fetchWorkflow,
  getApiErrorMessage,
  hasAuthToken,
  rebuildKnowledgeGraph,
  requestMultimodalDiagnosis,
  requestRagAnswer,
  searchKnowledge,
  setAuthToken,
  submitCase,
  submitRagFeedback,
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

type ActiveArea = "assistant" | "management" | "status";
type ManagementTab = "knowledge" | "review" | "cases" | "graph" | "history";

const activeArea = ref<ActiveArea>("assistant");
const activeManagementTab = ref<ManagementTab>("knowledge");
const sidebarCollapsed = ref(false);
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
const authTokenInput = ref("");
const authTokenConfigured = ref(hasAuthToken());

const caseForm = ref({
  deviceType: "",
  component: "",
  faultCode: "",
  riskLevel: "medium",
  maintenanceLevel: "normal_repair",
  workflowId: "",
  cause: "火花塞积碳导致点火能量不足。",
  solution: "清理并更换火花塞，复核燃油滤清器。",
  result: "启动恢复正常，怠速稳定。",
  tags: "启动困难, 点火系统, 火花塞"
});

const workflowSteps = [
  { index: "1", title: "描述故障", detail: "录入设备、现象和图片线索" },
  { index: "2", title: "查看依据", detail: "仅使用已审核资料" },
  { index: "3", title: "生成指引", detail: "输出检查、维修和安全提醒" },
  { index: "4", title: "复核修正", detail: "提交回答标注进入审核" },
  { index: "5", title: "提交经验", detail: "沉淀现场处理经验" }
];

const managementTabs: Array<{ key: ManagementTab; label: string }> = [
  { key: "knowledge", label: "资料管理" },
  { key: "review", label: "审核工作台" },
  { key: "cases", label: "案例与反馈" },
  { key: "graph", label: "知识图谱" },
  { key: "history", label: "审核记录" }
];

const resultCount = computed(() => searchPayload.value?.results.length ?? 0);
const documentNodeCount = computed(() => knowledgeGraph.value?.nodes.filter((node) => node.type === "document").length ?? 0);
const graphEdgeCount = computed(() => knowledgeGraph.value?.edges.length ?? 0);
const systemStatus = computed(() => providerStatus.value?.system ?? null);
const activeAreaLabel = computed(() => {
  if (activeArea.value === "management") {
    return "管理中心";
  }
  if (activeArea.value === "status") {
    return "系统状态";
  }
  return "检修助手";
});
const statusGeneratedAt = computed(() => {
  const generatedAt = systemStatus.value?.generatedAt;
  return generatedAt ? generatedAt.slice(0, 19).replace("T", " ") : "等待服务响应";
});

const diagnosisSummary = computed(() => {
  const diagnosis = multimodalDiagnosis.value;
  if (!diagnosis) {
    return "";
  }
  return diagnosis.imageAnalysis.summary || diagnosis.queryContext.ocrText || diagnosis.queryContext.imageClues[0] || "已完成图片诊断。";
});

const providerModeLabel = computed(() => {
  if (!providerStatus.value) {
    return "模型服务状态读取中";
  }
  if (providerStatus.value.offlineFallback) {
    return "离线兜底模式";
  }
  const llm = providerStatus.value.llm;
  return llm.effectiveProvider === "mock" ? "演示兜底模式" : `真实模型服务：${llm.effectiveProvider}`;
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

const providerToneClass = computed(() => ({
  "is-offline": providerStatus.value?.offlineFallback,
  "is-cloud": providerStatus.value && providerStatus.value.llm.effectiveProvider !== "mock",
  "is-local": !providerStatus.value || providerStatus.value.llm.effectiveProvider === "mock"
}));

const systemMetricItems = computed(() => {
  const system = systemStatus.value;
  if (!system) {
    return [];
  }
  return [
    {
      label: "知识片段",
      value: system.knowledge.chunkCount,
      detail: `${system.knowledge.approvedChunkCount} 已审核 / ${system.knowledge.unknownChunkCount ?? 0} 状态未知`
    },
    {
      label: "待审核",
      value: system.knowledge.pendingReviewCount,
      detail: `资料 / 片段 / 案例，未知案例 ${system.knowledge.unknownCaseCount ?? 0}`
    },
    {
      label: "可检索来源",
      value: system.knowledge.retrievableSourceCount,
      detail: "手册 + 案例 + 片段"
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

const statusCards = computed(() => {
  const status = providerStatus.value;
  if (!status) {
    return [
      { label: "模型服务", value: "读取中", detail: "请确认后端服务已启动" },
      { label: "OCR / 多模态", value: "读取中", detail: "系统状态页会显示实际 provider" },
      { label: "向量检索", value: "读取中", detail: "默认具备本地轻量检索兜底" },
      { label: "离线兜底", value: "读取中", detail: "真实模型不可用时仍可演示主流程" }
    ];
  }
  return [
    {
      label: "模型服务",
      value: status.llm.effectiveProvider,
      detail: status.llm.keyConfigured ? `已配置 Key / ${status.llm.model ?? "未返回模型名"}` : "未配置 Key 或使用演示兜底"
    },
    {
      label: "OCR / 多模态",
      value: `${status.ocr?.effectiveProvider ?? "mock"} / ${status.multimodal.effectiveProvider}`,
      detail: status.multimodal.lastFallbackReason || "图片线索会进入检索上下文"
    },
    {
      label: "向量检索",
      value: status.embedding?.effectiveProvider ?? "hash",
      detail: status.embedding?.vectorStore ? `向量库：${status.embedding.vectorStore}` : "默认本地轻量检索兜底"
    },
    {
      label: "离线兜底",
      value: status.offlineFallback ? "已启用" : "未启用",
      detail: status.remoteApiMode === "off" ? "当前强制离线演示" : "真实模型失败时可自动降级"
    }
  ];
});

function switchArea(area: ActiveArea) {
  activeArea.value = area;
  if (area === "status") {
    refreshProviderStatus();
  }
}

function openManagementTab(tab: ManagementTab) {
  activeManagementTab.value = tab;
  if (tab === "graph") {
    loadKnowledgeGraphOverview();
  }
}

function useDemoSample() {
  deviceModel.value = "发动机-示例型号 A";
  faultText.value = "启动困难，怠速不稳，排气异常";
  maintenanceLevel.value = "normal_repair";
  ElMessage.success("已填入演示样例，下一步点击“开始诊断”。");
}

async function refreshProviderStatus() {
  try {
    providerStatus.value = await fetchProviderStatus();
  } catch (error) {
    providerStatus.value = null;
    ElMessage.warning(getApiErrorMessage(error, "后端服务暂不可用，请确认服务已启动。"));
  }
}

function saveSessionAuthToken() {
  if (!authTokenInput.value.trim()) {
    ElMessage.warning("请输入有效的会话 Token。");
    return;
  }
  setAuthToken(authTokenInput.value);
  authTokenConfigured.value = hasAuthToken();
  authTokenInput.value = "";
  ElMessage.success("会话 Token 已保存，输入框已清空。");
}

function clearSessionAuthToken() {
  clearAuthToken();
  authTokenConfigured.value = false;
  authTokenInput.value = "";
  ElMessage.success("会话 Token 已清除。");
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
    if (searchPayload.value.results.length) {
      ElMessage.success("已找到参考依据，下一步可生成智能检修建议。");
    } else {
      ElMessage.info("暂无参考依据，请补充故障描述或在管理中心上传资料。");
    }
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, "检索失败，请检查输入内容或后端服务状态。"));
  } finally {
    loading.value = false;
  }
}

async function generateRagAnswer() {
  ragLoading.value = true;
  try {
    ragAnswer.value = await requestRagAnswer(deviceModel.value, faultText.value, undefined, maintenanceLevel.value);
    await refreshProviderStatus();
    ElMessage.success("已生成智能检修建议，请结合引用来源和安全提醒进行复核。");
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, "模型服务暂不可用，系统将使用离线兜底模式。"));
  } finally {
    ragLoading.value = false;
  }
}

async function submitRagAnswerFeedback(payload: {
  correctedAnswer: string;
  labels: string[];
  reason: string;
  reviewer: string;
}) {
  if (!ragAnswer.value) {
    ElMessage.warning("请先生成智能检修建议。");
    return;
  }
  try {
    await submitRagFeedback({
      deviceModel: deviceModel.value,
      faultText: faultText.value,
      maintenanceLevel: maintenanceLevel.value,
      originalAnswer: ragAnswer.value.answer,
      correctedAnswer: payload.correctedAnswer,
      labels: payload.labels,
      reason: payload.reason,
      reviewer: payload.reviewer
    });
    await refreshKnowledgeGraph();
    ElMessage.success("修正已提交审核，审核通过后会进入知识关系图。");
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, "回答修正提交失败，请稍后重试。"));
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
    ElMessage.success("已提取图片识别线索，下一步可查看参考依据或生成智能检修建议。");
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, "图片诊断失败，请检查图片格式或稍后重试。"));
  } finally {
    diagnosisLoading.value = false;
  }
}

async function refreshKnowledgeGraph() {
  graphLoading.value = true;
  try {
    knowledgeGraph.value = await fetchKnowledgeGraph(deviceModel.value, faultText.value);
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, "知识关系图生成失败，请稍后重试。"));
  } finally {
    graphLoading.value = false;
  }
}

async function loadKnowledgeGraphOverview() {
  graphLoading.value = true;
  try {
    knowledgeGraph.value = await fetchKnowledgeGraphOverview();
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, "知识关系图总览读取失败，请稍后重试。"));
  } finally {
    graphLoading.value = false;
  }
}

async function rebuildKnowledgeGraphOverview() {
  graphLoading.value = true;
  try {
    knowledgeGraph.value = await rebuildKnowledgeGraph();
    ElMessage.success("知识关系图已根据资料、案例、流程和回答修正重建。");
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, "知识关系图重建失败，请稍后重试。"));
  } finally {
    graphLoading.value = false;
  }
}

async function openWorkflow(result: SearchResult) {
  if (!result.workflowId) {
    ElMessage.warning("该参考依据暂未关联标准作业步骤。");
    return;
  }
  try {
    selectedResult.value = result;
    selectedWorkflow.value = await fetchWorkflow(result.workflowId);
  } catch (error) {
    selectedWorkflow.value = null;
    ElMessage.error(getApiErrorMessage(error, "标准作业步骤加载失败，请稍后重试。"));
  }
}

async function createCase() {
  submitting.value = true;
  try {
    await submitCase({
      deviceModel: deviceModel.value,
      deviceType: caseForm.value.deviceType || deviceModel.value,
      component: caseForm.value.component,
      faultCode: caseForm.value.faultCode,
      faultText: faultText.value,
      cause: caseForm.value.cause,
      solution: caseForm.value.solution,
      result: caseForm.value.result,
      experienceSummary: `${caseForm.value.cause} ${caseForm.value.solution}`,
      lessonsLearned: caseForm.value.result,
      maintenanceLevel: caseForm.value.maintenanceLevel || maintenanceLevel.value,
      riskLevel: caseForm.value.riskLevel,
      workflowId: caseForm.value.workflowId || undefined,
      tags: caseForm.value.tags.split(",").map((tag) => tag.trim()).filter(Boolean)
    });
    ElMessage.success("处理经验已提交审核，审核通过后将沉淀到知识库。");
    reviewPanel.value?.loadCases();
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, "处理经验提交失败，请检查填写内容后重试。"));
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
    ElMessage.error(getApiErrorMessage(error, "资料上传失败，请检查文件格式或大小。"));
  } finally {
    uploading.value = false;
  }
}

refreshProviderStatus();
</script>

<template>
  <main class="shell" :class="{ 'sidebar-is-collapsed': sidebarCollapsed }">
    <aside class="app-sidebar">
      <div class="sidebar-brand">
        <span class="brand-mark"><Wrench :size="19" /></span>
        <div class="brand-copy">
          <strong>设备检修</strong>
          <small>知识与作业辅助</small>
        </div>
      </div>

      <nav class="sidebar-nav" aria-label="主功能区域">
        <button :class="{ active: activeArea === 'assistant' }" type="button" @click="switchArea('assistant')">
          <Bot :size="18" />
          <span><strong>检修助手</strong><small>现场作业链路</small></span>
        </button>
        <button :class="{ active: activeArea === 'management' }" type="button" @click="switchArea('management')">
          <LayoutDashboard :size="18" />
          <span><strong>管理中心</strong><small>资料与审核</small></span>
        </button>
        <button :class="{ active: activeArea === 'status' }" type="button" @click="switchArea('status')">
          <Activity :size="18" />
          <span><strong>系统状态</strong><small>模型与部署</small></span>
        </button>
      </nav>

      <div class="sidebar-context">
        <ShieldCheck :size="17" />
        <span>仅使用已审核知识</span>
      </div>
      <button
        class="sidebar-collapse"
        type="button"
        :aria-label="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
        :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
        @click="sidebarCollapsed = !sidebarCollapsed"
      >
        <PanelLeftOpen v-if="sidebarCollapsed" :size="18" />
        <PanelLeftClose v-else :size="18" />
      </button>
    </aside>

    <div class="app-frame">
      <header class="top-status-bar">
        <div class="topbar-location">
          <button class="compact-sidebar-toggle" type="button" aria-label="切换导航栏" @click="sidebarCollapsed = !sidebarCollapsed">
            <Menu :size="18" />
          </button>
          <span>设备检修知识检索与作业辅助系统</span>
          <ChevronRight :size="14" />
          <strong>{{ activeAreaLabel }}</strong>
        </div>
        <div class="topbar-signals">
          <span class="live-signal" :class="{ offline: providerStatus?.offlineFallback }">
            <i></i>{{ providerModeLabel }}
          </span>
          <span>{{ statusGeneratedAt }}</span>
        </div>
      </header>

      <section v-if="activeArea === 'assistant'" class="area-section assistant-area">
        <div class="area-intro">
          <div>
            <span class="section-eyebrow">现场作业台</span>
            <h1>检修助手</h1>
            <p>从故障描述到依据核验、作业指引与经验沉淀，全程保留证据和模型来源。</p>
          </div>
          <div class="area-actions">
            <el-button plain @click="useDemoSample">载入演示工况</el-button>
            <el-button type="primary" :loading="loading" @click="runSearch">
              <RefreshCw :size="15" />重新检索
            </el-button>
          </div>
        </div>

        <ol class="workflow-strip" aria-label="五步检修辅助流程">
          <li
            v-for="step in workflowSteps"
            :key="step.index"
            :class="{ complete: Number(step.index) === 1 || (Number(step.index) === 2 && resultCount > 0) }"
          >
            <span>{{ step.index }}</span>
            <div><strong>{{ step.title }}</strong><small>{{ step.detail }}</small></div>
          </li>
        </ol>

        <section class="workspace assistant-workspace">
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
            :multimodal-signals="multimodalDiagnosis?.multimodalSignals ?? null"
            @search="runSearch"
            @upload="uploadFile"
            @diagnose="runMultimodalDiagnosis"
            @demo="useDemoSample"
          />
          <div class="assistant-output-column">
            <ResultsPanel
              :search-payload="searchPayload"
              :selected-result="selectedResult"
              :loading="loading"
              @open-workflow="openWorkflow"
            />
            <WorkflowPanel :selected-workflow="selectedWorkflow" />
          </div>
        </section>

        <RagPanel
          :rag-answer="ragAnswer"
          :loading="ragLoading"
          :device-model="deviceModel"
          :fault-text="faultText"
          :maintenance-level="maintenanceLevel"
          @answer="generateRagAnswer"
          @feedback="submitRagAnswerFeedback"
        />

        <details class="case-disclosure">
          <summary><ClipboardCheck :size="17" />步骤 5：沉淀现场案例与反馈</summary>
          <CasePanel
            v-model:device-type="caseForm.deviceType"
            v-model:component="caseForm.component"
            v-model:fault-code="caseForm.faultCode"
            v-model:risk-level="caseForm.riskLevel"
            v-model:maintenance-level="caseForm.maintenanceLevel"
            v-model:workflow-id="caseForm.workflowId"
            v-model:cause="caseForm.cause"
            v-model:solution="caseForm.solution"
            v-model:result="caseForm.result"
            v-model:tags="caseForm.tags"
            :submitting="submitting"
            @submit="createCase"
          />
        </details>
      </section>

      <section v-else-if="activeArea === 'management'" class="area-section management-area">
        <div class="area-intro">
          <div>
            <span class="section-eyebrow">知识治理</span>
            <h1>管理中心</h1>
            <p>资料入库、内容审核、案例反馈和知识关系统一在一个可追溯工作区内完成。</p>
          </div>
        </div>
        <nav class="management-tabs" aria-label="管理中心功能">
          <button
            v-for="tab in managementTabs"
            :key="tab.key"
            type="button"
            :class="{ active: activeManagementTab === tab.key }"
            @click="openManagementTab(tab.key)"
          >
            {{ tab.label }}
          </button>
        </nav>
        <section class="management-workspace">
          <KnowledgePanel v-if="activeManagementTab === 'knowledge'" />
          <ReviewPanel v-else-if="activeManagementTab === 'review'" ref="reviewPanel" />
          <CasePanel
            v-else-if="activeManagementTab === 'cases'"
            v-model:device-type="caseForm.deviceType"
            v-model:component="caseForm.component"
            v-model:fault-code="caseForm.faultCode"
            v-model:risk-level="caseForm.riskLevel"
            v-model:maintenance-level="caseForm.maintenanceLevel"
            v-model:workflow-id="caseForm.workflowId"
            v-model:cause="caseForm.cause"
            v-model:solution="caseForm.solution"
            v-model:result="caseForm.result"
            v-model:tags="caseForm.tags"
            :submitting="submitting"
            @submit="createCase"
          />
          <KnowledgeGraphPanel
            v-else-if="activeManagementTab === 'graph'"
            :graph="knowledgeGraph"
            :loading="graphLoading"
            @refresh="refreshKnowledgeGraph"
            @overview="loadKnowledgeGraphOverview"
            @rebuild="rebuildKnowledgeGraphOverview"
          />
          <ReviewEventsPanel v-else />
        </section>
      </section>

      <section v-else class="area-section status-area">
        <div class="area-intro">
          <div>
            <span class="section-eyebrow">运行与验收</span>
            <h1>系统状态</h1>
            <p>查看模型通道、知识服务、鉴权和 LoongArch / 银河麒麟实机验收结论。</p>
          </div>
          <el-button plain @click="refreshProviderStatus"><RefreshCw :size="15" />刷新状态</el-button>
        </div>

        <section class="status-overview">
          <article class="status-panel" :class="providerToneClass">
            <span>当前运行模式</span><strong>{{ providerModeLabel }}</strong><small>{{ providerDetailLabel }}</small>
          </article>
          <article v-for="item in statusCards" :key="item.label" class="status-card">
            <span>{{ item.label }}</span><strong>{{ item.value }}</strong><small>{{ item.detail }}</small>
          </article>
        </section>

        <section class="acceptance-board">
          <div class="acceptance-heading">
            <div><h2>阶段 2 部署验收</h2><p>结论与当前验收文档保持一致，不把未验证项标记为通过。</p></div>
            <el-tag type="warning" effect="plain">暂不形成最终 GO</el-tag>
          </div>
          <div class="acceptance-list">
            <div><ShieldCheck :size="17" /><span><strong>LoongArch 核心链路</strong><small>已完成实机核心链路验证</small></span><b class="is-pass">已验证</b></div>
            <div><BookOpenCheck :size="17" /><span><strong>人工检索与作业流程</strong><small>已完成现场手工验收</small></span><b class="is-pass">已验证</b></div>
            <div><Bot :size="17" /><span><strong>真实文本模型</strong><small>qwen3.6-flash OpenAI-compatible 链路</small></span><b class="is-pass">已验证</b></div>
            <div><Boxes :size="17" /><span><strong>真实故障图片 / Docker</strong><small>图片样本与 Docker 环境仍待补齐</small></span><b class="is-pending">未验证</b></div>
          </div>
        </section>

        <section class="status-detail-grid">
          <article class="system-card auth-session-card">
            <h3>会话访问令牌</h3>
            <p v-if="systemStatus?.auth?.mode === 'off'">当前 AUTH_MODE=off，离线演示未启用 API 鉴权。</p>
            <p v-else-if="systemStatus?.auth?.mode === 'token'">当前 AUTH_MODE=token，受保护操作需要 Bearer Token。</p>
            <p v-else>鉴权状态暂不可用，请检查后端配置。</p>
            <el-input v-model="authTokenInput" type="password" show-password placeholder="输入 operator / reviewer / admin token" />
            <div class="auth-actions">
              <el-button type="primary" @click="saveSessionAuthToken">保存到本次会话</el-button>
              <el-button plain @click="clearSessionAuthToken">清除</el-button>
            </div>
            <small>{{ authTokenConfigured ? "当前会话已配置 Token。" : "当前会话未配置 Token。" }}</small>
            <small>仅存储于 sessionStorage，关闭会话后自动失效；前端不会回显或写入构建产物。</small>
          </article>

          <article class="system-card">
            <h3>知识服务指标</h3>
            <div v-if="systemMetricItems.length" class="status-metrics">
              <div v-for="item in systemMetricItems" :key="item.label">
                <b>{{ item.value }}</b><span>{{ item.label }}</span><small>{{ item.detail }}</small>
              </div>
            </div>
            <div v-else class="empty-hint"><span>暂未读取到系统指标，请确认后端服务已启动。</span></div>
            <div v-if="systemSignalItems.length" class="status-signals">
              <span v-for="item in systemSignalItems" :key="item">{{ item }}</span>
            </div>
          </article>

          <article class="system-card">
            <h3>部署策略</h3>
            <p>真实模型使用 OpenAI-compatible 配置；文档解析、向量增强与 OCR 均保留明确降级路径。</p>
            <div class="deployment-facts">
              <span><Database :size="15" />Chroma / Qdrant / sqlite-vec 为可选增强</span>
              <span><Network :size="15" />远程模型失败时记录 fallback 原因</span>
              <span><Settings2 :size="15" />API Key 仅保存在本地未提交的 .env</span>
            </div>
          </article>
        </section>
      </section>
    </div>
  </main>
</template>
