<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  clearAuthToken,
  fetchKnowledgeGraph,
  fetchKnowledgeGraphOverview,
  fetchProviderStatus,
  fetchWorkflow,
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

const activeArea = ref<ActiveArea>("assistant");
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

const navItems: Array<{ key: ActiveArea; label: string; desc: string }> = [
  { key: "assistant", label: "检修助手", desc: "一线作业链路" },
  { key: "management", label: "管理中心", desc: "资料与审核" },
  { key: "status", label: "系统状态", desc: "模型与部署" }
];

const workflowSteps = [
  { index: "1", title: "描述故障", detail: "录入设备、现象和图片线索" },
  { index: "2", title: "查看依据", detail: "仅使用已审核资料" },
  { index: "3", title: "生成指引", detail: "输出检查、维修和安全提醒" },
  { index: "4", title: "复核修正", detail: "提交回答标注进入审核" },
  { index: "5", title: "提交经验", detail: "沉淀现场处理经验" }
];

const resultCount = computed(() => searchPayload.value?.results.length ?? 0);
const documentNodeCount = computed(() => knowledgeGraph.value?.nodes.filter((node) => node.type === "document").length ?? 0);
const graphEdgeCount = computed(() => knowledgeGraph.value?.edges.length ?? 0);
const systemStatus = computed(() => providerStatus.value?.system ?? null);

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

function useDemoSample() {
  deviceModel.value = "发动机-示例型号 A";
  faultText.value = "启动困难，怠速不稳，排气异常";
  maintenanceLevel.value = "normal_repair";
  ElMessage.success("已填入演示样例，下一步点击“开始诊断”。");
}

async function refreshProviderStatus() {
  try {
    providerStatus.value = await fetchProviderStatus();
  } catch {
    providerStatus.value = null;
    ElMessage.warning("后端服务暂不可用，请确认服务已启动。");
  }
}

function saveSessionAuthToken() {
  setAuthToken(authTokenInput.value);
  authTokenConfigured.value = hasAuthToken();
  authTokenInput.value = "";
  ElMessage.success("Access token saved for this browser session.");
}

function clearSessionAuthToken() {
  clearAuthToken();
  authTokenConfigured.value = false;
  authTokenInput.value = "";
  ElMessage.success("Access token cleared.");
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
  } catch {
    ElMessage.error("检索失败，请检查输入内容或后端服务状态。");
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
  } catch {
    ElMessage.error("模型服务暂不可用，系统将使用离线兜底模式。");
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
  } catch {
    ElMessage.error("回答修正提交失败，请稍后重试。");
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
  } catch {
    ElMessage.error("图片诊断失败，请检查图片格式或稍后重试。");
  } finally {
    diagnosisLoading.value = false;
  }
}

async function refreshKnowledgeGraph() {
  graphLoading.value = true;
  try {
    knowledgeGraph.value = await fetchKnowledgeGraph(deviceModel.value, faultText.value);
  } catch {
    ElMessage.error("知识关系图生成失败，请稍后重试。");
  } finally {
    graphLoading.value = false;
  }
}

async function loadKnowledgeGraphOverview() {
  graphLoading.value = true;
  try {
    knowledgeGraph.value = await fetchKnowledgeGraphOverview();
  } catch {
    ElMessage.error("知识关系图总览读取失败，请稍后重试。");
  } finally {
    graphLoading.value = false;
  }
}

async function rebuildKnowledgeGraphOverview() {
  graphLoading.value = true;
  try {
    knowledgeGraph.value = await rebuildKnowledgeGraph();
    ElMessage.success("知识关系图已根据资料、案例、流程和回答修正重建。");
  } catch {
    ElMessage.error("知识关系图重建失败，请稍后重试。");
  } finally {
    graphLoading.value = false;
  }
}

async function openWorkflow(result: SearchResult) {
  if (!result.workflowId) {
    ElMessage.warning("该参考依据暂未关联标准作业步骤。");
    return;
  }
  selectedResult.value = result;
  selectedWorkflow.value = await fetchWorkflow(result.workflowId);
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
  } catch {
    ElMessage.error("处理经验提交失败，请检查填写内容后重试。");
  } finally {
    submitting.value = false;
  }
}

async function uploadFile(file: File) {
  uploading.value = true;
  try {
    uploadResult.value = await uploadFaultFile(file);
    ElMessage.success(`现场资料已上传：${uploadResult.value.fileName}`);
  } catch {
    ElMessage.error("资料上传失败，请检查文件格式或大小。");
  } finally {
    uploading.value = false;
  }
}

refreshProviderStatus();
</script>

<template>
  <main class="shell">
    <header class="app-header">
      <div class="brand-block">
        <span class="product-kicker">中国软件杯 A1 · 设备检修知识检索与作业辅助系统</span>
        <h1>面向现场检修的知识检索与作业助手</h1>
        <p>
          按 5 步完成一次检修辅助：描述故障 → 查看依据 → 生成指引 → 复核修正 → 提交经验。
        </p>
      </div>
      <nav class="main-nav" aria-label="主功能区域">
        <button
          v-for="item in navItems"
          :key="item.key"
          type="button"
          :class="{ active: activeArea === item.key }"
          @click="switchArea(item.key)"
        >
          <strong>{{ item.label }}</strong>
          <span>{{ item.desc }}</span>
        </button>
      </nav>
    </header>

    <section v-if="activeArea === 'assistant'" class="area-section assistant-area">
      <div class="area-intro">
        <div>
          <h2>检修助手</h2>
          <p>输入设备型号、故障现象和检修等级；可上传现场故障图片，系统会提取图片识别线索辅助诊断。</p>
        </div>
        <el-button plain @click="useDemoSample">使用演示样例</el-button>
      </div>

      <ol class="workflow-strip" aria-label="五步检修辅助流程">
        <li v-for="step in workflowSteps" :key="step.index">
          <span>{{ step.index }}</span>
          <div>
            <strong>{{ step.title }}</strong>
            <small>{{ step.detail }}</small>
          </div>
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
        <ResultsPanel :search-payload="searchPayload" :selected-result="selectedResult" @open-workflow="openWorkflow" />
        <WorkflowPanel :selected-workflow="selectedWorkflow" />
      </section>

      <section class="assistant-followup" aria-label="智能建议与经验沉淀">
        <RagPanel
          :rag-answer="ragAnswer"
          :loading="ragLoading"
          :device-model="deviceModel"
          :fault-text="faultText"
          :maintenance-level="maintenanceLevel"
          @answer="generateRagAnswer"
          @feedback="submitRagAnswerFeedback"
        />
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
      </section>
    </section>

    <section v-else-if="activeArea === 'management'" class="area-section management-area">
      <div class="area-intro">
        <div>
          <h2>管理中心</h2>
          <p>用于上传维修手册和现场资料，审核资料片段、案例经验和回答修正，并查看知识沉淀结果。</p>
        </div>
        <el-button plain :loading="graphLoading" @click="loadKnowledgeGraphOverview">查看知识关系图总览</el-button>
      </div>

      <section class="management-grid">
        <div class="area-group-title">资料入库</div>
        <KnowledgePanel />
        <div class="area-group-title">待审核内容</div>
        <ReviewPanel ref="reviewPanel" />
        <div class="area-group-title">审核记录</div>
        <ReviewEventsPanel />
        <div class="area-group-title">知识关系图</div>
        <KnowledgeGraphPanel
          :graph="knowledgeGraph"
          :loading="graphLoading"
          @refresh="refreshKnowledgeGraph"
          @overview="loadKnowledgeGraphOverview"
          @rebuild="rebuildKnowledgeGraphOverview"
        />
      </section>
    </section>

    <section v-else class="area-section status-area">
      <div class="area-intro">
        <div>
          <h2>系统状态</h2>
          <p>集中查看模型服务、OCR、多模态、向量检索、离线兜底和 LoongArch / Kylin 适配状态。</p>
        </div>
        <el-button plain @click="refreshProviderStatus">刷新状态</el-button>
      </div>

      <section class="status-overview">
        <article class="status-panel" :class="providerToneClass">
          <span>当前运行模式</span>
          <strong>{{ providerModeLabel }}</strong>
          <small>{{ providerDetailLabel }}</small>
        </article>
        <article v-for="item in statusCards" :key="item.label" class="status-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <small>{{ item.detail }}</small>
        </article>
      </section>

      <section class="status-detail-grid">
        <article class="system-card auth-session-card">
          <h3>Session access token</h3>
          <p v-if="systemStatus?.auth?.mode === 'off'">AUTH_MODE=off. Offline demo mode has API protection disabled.</p>
          <p v-else-if="systemStatus?.auth?.mode === 'token'">AUTH_MODE=token. Protected actions require a bearer token.</p>
          <p v-else>Auth mode status is unavailable or misconfigured.</p>
          <el-input
            v-model="authTokenInput"
            type="password"
            show-password
            placeholder="Paste operator, reviewer, or admin token"
          />
          <div class="auth-actions">
            <el-button type="primary" @click="saveSessionAuthToken">Save for session</el-button>
            <el-button plain @click="clearSessionAuthToken">Clear</el-button>
          </div>
          <small>{{ authTokenConfigured ? "Token configured for current session." : "No session token configured." }}</small>
          <small>Stored only in sessionStorage; it disappears when this browser session ends and is not bundled into source or build output.</small>
        </article>

        <article class="system-card">
          <h3>系统指标</h3>
          <div v-if="systemMetricItems.length" class="status-metrics">
            <div v-for="item in systemMetricItems" :key="item.label">
              <b>{{ item.value }}</b>
              <span>{{ item.label }}</span>
              <small>{{ item.detail }}</small>
            </div>
          </div>
          <div v-else class="empty-hint">
            <span>暂未读取到系统指标，请确认后端服务已启动。</span>
          </div>
          <div v-if="systemSignalItems.length" class="status-signals">
            <span v-for="item in systemSignalItems" :key="item">{{ item }}</span>
          </div>
        </article>

        <article class="system-card">
          <h3>初始化配置</h3>
          <p>系统支持离线演示模式和真实 LLM 模式。配置完成后请重启服务，并刷新系统状态页查看模型服务状态。</p>
          <div class="command-list">
            <code>powershell -ExecutionPolicy Bypass -File .\scripts\init-config.ps1</code>
            <code>bash scripts/init-config.sh</code>
          </div>
          <small>前端不会保存 API Key；真实 Key 只写入本地未提交的 .env，并在脚本输出中脱敏显示。</small>
        </article>

        <article class="system-card">
          <h3>LoongArch / Kylin 说明</h3>
          <p>
            主链路按比赛环境优先：真实模型通过 OpenAI-compatible 配置接入，向量增强和文档解析保留 fallback；
            Chroma、Qdrant、sqlite-vec 为可选增强，不作为现场演示硬依赖。
          </p>
        </article>

        <article class="system-card">
          <h3>常见说明</h3>
          <details open>
            <summary>术语解释</summary>
            <ul>
              <li>参考依据：系统从已审核资料、案例和手册中匹配出的依据。</li>
              <li>仅使用已审核资料：待审核或被拒绝的内容不会进入正式建议。</li>
              <li>离线兜底：真实模型不可用时，系统仍可使用本地演示能力完成流程。</li>
              <li>人工复核：当证据不足或风险较高时，需要现场人员确认后再执行。</li>
              <li>知识关系图：展示设备、故障、资料、案例、流程和回答修正之间的关系。</li>
            </ul>
          </details>
        </article>
      </section>
    </section>
  </main>
</template>
