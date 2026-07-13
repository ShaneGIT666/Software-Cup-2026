<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  Bot,
  CheckCircle2,
  ClipboardList,
  Cpu,
  FileText,
  Quote,
  Route,
  ShieldAlert,
  TriangleAlert
} from "@lucide/vue";
import type { EvidenceItem, EvidenceTrace, RagAnswerPayload } from "../api";
import VisualEvidenceThumbnail from "./VisualEvidenceThumbnail.vue";

const props = defineProps<{
  ragAnswer: RagAnswerPayload | null;
  loading: boolean;
  deviceModel: string;
  faultText: string;
  maintenanceLevel: string;
}>();

const emit = defineEmits<{
  answer: [];
  feedback: [
    payload: {
      correctedAnswer: string;
      labels: string[];
      reason: string;
      reviewer: string;
    }
  ];
}>();

const feedbackOpen = ref(false);
const feedbackSubmitting = ref(false);
const feedbackForm = ref({
  correctedAnswer: "",
  labels: "人工修正",
  reason: "",
  reviewer: "operator"
});

function sourceLabel(sourceType: string) {
  const labels: Record<string, string> = {
    manual: "手册",
    case: "案例",
    document: "资料",
    document_asset: "图片资料"
  };
  return labels[sourceType] ?? sourceType;
}

const structuredAnswer = computed(() => props.ragAnswer?.structuredAnswer ?? null);
const correctiveRag = computed(() => props.ragAnswer?.correctiveRag ?? null);
const safetyRules = computed(() => props.ragAnswer?.safetyRules ?? null);
const answerSourceLabel = computed(() => {
  const source = props.ragAnswer?.finalAnswerSource;
  if (source === "validated_llm") {
    return "真实模型回答";
  }
  if (source === "validated_llm_with_guardrails") {
    return "真实模型回答 + 安全护栏";
  }
  if (source === "template") {
    return "证据模板回答";
  }
  return source || "后端未声明";
});

const candidateStatusLabel = computed(() => {
  const accepted = props.ragAnswer?.llmCandidateAccepted;
  if (accepted === true) {
    return "已通过证据与安全校验";
  }
  if (accepted === false) {
    return "未采纳，已使用受控回答";
  }
  return "后端未声明";
});

function answerModeLabel(mode?: string) {
  const labels: Record<string, string> = {
    grounded: "证据充分",
    grounded_with_caution: "基于证据谨慎回答",
    insufficient_evidence: "证据不足"
  };
  return mode ? labels[mode] ?? mode : "";
}

const evidenceItems = computed<EvidenceItem[]>(() => {
  if (props.ragAnswer?.evidencePack?.items?.length) {
    return props.ragAnswer.evidencePack.items;
  }

  return (props.ragAnswer?.citations ?? []).map((citation, index) => ({
    evidenceId: `E${index + 1}`,
    resultId: citation.id,
    title: citation.title,
    sourceType: citation.sourceType,
    sourceName: citation.sourceName,
    sourceDocId: citation.sourceDocId ?? citation.documentId ?? citation.sourceId ?? citation.id,
    documentId: citation.documentId ?? null,
    chunkId: citation.chunkId ?? null,
    version: citation.scoreBreakdown?.version ?? null,
    page: citation.page ?? null,
    section: citation.section ?? citation.chapter ?? null,
    chapter: citation.chapter ?? null,
    snippet: citation.snippet,
    reason: citation.reason ?? "",
    confidence: citation.confidence,
    reviewStatus: citation.reviewStatus ?? "unknown",
    riskLevel: citation.riskLevel ?? citation.scoreBreakdown?.riskLevel ?? "unknown",
    score: citation.scoreBreakdown?.score ?? null,
    assetId: citation.assetId,
    assetType: citation.assetType,
    previewUrl: citation.previewUrl,
    visualType: citation.visualType,
    semanticVerified: citation.semanticVerified,
    analysisProvider: citation.analysisProvider,
    analysisFallback: citation.analysisFallback,
    trace: {
      evidenceId: `E${index + 1}`,
      chunkId: citation.chunkId ?? null,
      sourceDocId: citation.sourceDocId ?? citation.documentId ?? citation.sourceId ?? citation.id,
      page: citation.page ?? null,
      section: citation.section ?? citation.chapter ?? null
    }
  }));
});

const evidenceSummary = computed(() => {
  const pack = props.ragAnswer?.evidencePack;
  if (!pack) {
    return `${evidenceItems.value.length} 条引用来源`;
  }
  const status = pack.approvedOnly ? "仅使用已审核资料" : "包含待复核内容";
  const risk = pack.riskReviewRequired ? "需要人工复核" : "未标记高风险";
  return `${pack.evidenceCount} 条依据 / ${status} / ${risk}`;
});

function traceText(trace: EvidenceTrace) {
  const parts = [trace.evidenceId];
  if (trace.sourceDocId) {
    parts.push(`source_doc_id=${trace.sourceDocId}`);
  }
  if (trace.chunkId) {
    parts.push(`chunk_id=${trace.chunkId}`);
  }
  if (trace.page !== undefined && trace.page !== null) {
    parts.push(`page=${trace.page}`);
  }
  if (trace.section) {
    parts.push(`section=${trace.section}`);
  }
  return parts.join(" / ");
}

function evidenceMeta(item: EvidenceItem) {
  const meta = [
    item.sourceDocId ? `source_doc_id ${item.sourceDocId}` : "",
    item.chunkId ? `chunk ${item.chunkId}` : "",
    item.version ? `v${item.version}` : "",
    item.page ? `p.${item.page}` : "",
    item.section ? item.section : "",
    item.score !== undefined && item.score !== null ? `排序分 ${item.score}` : ""
  ];
  return meta.filter(Boolean).join(" / ");
}

function correctiveActionLabel(action: string) {
  const labels: Record<string, string> = {
    answer: "证据充分",
    answer_with_caution: "谨慎回答",
    needs_more_evidence: "需要补充依据"
  };
  return labels[action] ?? action;
}

function severityLabel(severity: string) {
  const labels: Record<string, string> = {
    info: "提示",
    warning: "注意",
    high: "高风险",
    critical: "关键风险"
  };
  return labels[severity] ?? severity;
}

function resetFeedbackForm() {
  feedbackForm.value = {
    correctedAnswer: "",
    labels: "人工修正",
    reason: "",
    reviewer: "operator"
  };
}

async function submitFeedback() {
  const labels = feedbackForm.value.labels
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  const correctedAnswer = feedbackForm.value.correctedAnswer.trim();
  const reason = feedbackForm.value.reason.trim();
  if (!correctedAnswer && !labels.length && !reason) {
    ElMessage.warning("请填写修正建议、标签或修正原因。");
    return;
  }
  feedbackSubmitting.value = true;
  emit("feedback", {
    correctedAnswer,
    labels,
    reason,
    reviewer: feedbackForm.value.reviewer.trim() || "operator"
  });
  window.setTimeout(() => {
    feedbackSubmitting.value = false;
    feedbackOpen.value = false;
    resetFeedbackForm();
  }, 300);
}
</script>

<template>
  <section class="rag-panel panel-highlight">
    <div class="section-title">
      <Bot :size="18" />
      <span>步骤 4：生成智能检修建议</span>
    </div>
    <p class="panel-note">
      基于当前参考依据生成检修建议，保留引用来源、页码、资料片段和不确定信息，便于现场人员复核。
    </p>

    <div class="action-row">
      <el-button type="primary" :loading="loading" @click="emit('answer')">
        <Bot :size="16" />
        生成智能检修建议
      </el-button>
      <el-tag v-if="ragAnswer?.fallback" type="warning">离线兜底</el-tag>
      <el-tag v-if="ragAnswer && !ragAnswer.fallback" type="success">已调用真实模型</el-tag>
      <el-tag v-if="ragAnswer?.llmAnswerUsed" type="success">模型回答已采纳</el-tag>
      <el-tag v-if="ragAnswer && !ragAnswer.fallback && ragAnswer.llmAnswerUsed === false" type="warning">
        最终未采用模型原文
      </el-tag>
      <el-tag
        v-if="ragAnswer?.answerMode"
        :type="
          ragAnswer.answerMode === 'grounded'
            ? 'success'
            : ragAnswer.answerMode === 'grounded_with_caution'
              ? 'warning'
              : 'danger'
        "
      >
        {{ answerModeLabel(ragAnswer.answerMode) }}
      </el-tag>
      <el-tag v-if="ragAnswer" type="info">{{ ragAnswer.provider || "unknown" }} / requested {{ ragAnswer.requestedProvider || "default" }}</el-tag>
      <el-tag v-if="ragAnswer?.model" type="info">{{ ragAnswer.model }} / {{ ragAnswer.apiStyle }}</el-tag>
      <el-tag v-if="ragAnswer?.contextCount !== undefined" type="info">
        {{ ragAnswer.contextCount }} 条上下文 / {{ ragAnswer.contextChars ?? 0 }} 字符
      </el-tag>
    </div>

    <div v-if="loading" class="loading-hint processing-card">
      <span>正在组织参考依据、引用来源和检修建议...</span>
    </div>

    <article v-else-if="ragAnswer" class="rag-answer">
      <section class="provenance-panel" aria-label="模型与答案溯源">
        <div class="provenance-title"><Route :size="16" /><strong>模型与答案溯源</strong></div>
        <dl>
          <div>
            <dt>请求 / 实际 Provider</dt>
            <dd>{{ ragAnswer.requestedProvider || "default" }} / {{ ragAnswer.provider || "unknown" }}</dd>
          </div>
          <div>
            <dt>模型 / API 风格</dt>
            <dd>{{ ragAnswer.model || "未返回" }} / {{ ragAnswer.apiStyle || "未返回" }}</dd>
          </div>
          <div>
            <dt>最终答案来源</dt>
            <dd>{{ answerSourceLabel }}</dd>
          </div>
          <div>
            <dt>LLM 候选状态</dt>
            <dd>{{ candidateStatusLabel }}</dd>
          </div>
        </dl>
        <p v-if="ragAnswer.fallbackReason" class="provenance-fallback">
          <Cpu :size="14" />降级原因：{{ ragAnswer.fallbackReason }}
        </p>
      </section>

      <div v-if="ragAnswer.riskReviewRequired" class="risk-banner">
        <ShieldAlert :size="17" />
        <span>包含 high / critical 风险依据，执行前必须人工复核。</span>
      </div>

      <div v-if="correctiveRag && correctiveRag.action !== 'answer'" class="corrective-panel">
        <div class="corrective-panel-header">
          <TriangleAlert :size="17" />
          <strong>依据充分性检查：{{ correctiveActionLabel(correctiveRag.action) }}</strong>
          <span>质量分 {{ Math.round(correctiveRag.qualityScore * 100) }}%</span>
        </div>
        <ul v-if="correctiveRag.reasons.length">
          <li v-for="reason in correctiveRag.reasons" :key="reason">{{ reason }}</li>
        </ul>
        <div v-if="correctiveRag.suggestedQueries.length" class="query-suggestion-list">
          <span v-for="query in correctiveRag.suggestedQueries" :key="query">{{ query }}</span>
        </div>
      </div>

      <div v-if="safetyRules && safetyRules.findings.length" class="safety-rules-panel">
        <div class="safety-rules-header">
          <ShieldAlert :size="17" />
          <strong>安全提醒：{{ severityLabel(safetyRules.highestSeverity) }}</strong>
          <span v-if="safetyRules.blocking">阻断复核</span>
          <span v-else-if="safetyRules.manualReviewRequired">人工复核</span>
        </div>
        <div class="safety-finding-list">
          <article v-for="finding in safetyRules.findings" :key="finding.ruleId" class="safety-finding">
            <strong>{{ finding.title }}</strong>
            <small>{{ finding.ruleId }} / {{ severityLabel(finding.severity) }}</small>
            <p>{{ finding.message }}</p>
          </article>
        </div>
        <div v-if="safetyRules.checklist.length" class="safety-checklist">
          <span v-for="item in safetyRules.checklist" :key="item">{{ item }}</span>
        </div>
      </div>

      <div v-if="structuredAnswer" class="structured-answer">
        <section class="structured-section is-full">
          <h3><ClipboardList :size="16" /> 初步判断</h3>
          <p>{{ structuredAnswer.preliminaryJudgment }}</p>
        </section>

        <section class="structured-section">
          <h3><FileText :size="16" /> 检查步骤</h3>
          <ol>
            <li v-for="step in structuredAnswer.inspectionSteps" :key="step">{{ step }}</li>
          </ol>
        </section>

        <section class="structured-section">
          <h3><CheckCircle2 :size="16" /> 维修步骤</h3>
          <ol>
            <li v-for="step in structuredAnswer.repairSteps" :key="step">{{ step }}</li>
          </ol>
        </section>

        <section class="structured-section">
          <h3><ShieldAlert :size="16" /> 安全提醒</h3>
          <ul>
            <li v-for="warning in structuredAnswer.safetyWarnings" :key="warning">{{ warning }}</li>
          </ul>
        </section>

        <section class="structured-section">
          <h3><CheckCircle2 :size="16" /> 验收标准</h3>
          <ul>
            <li v-for="criteria in structuredAnswer.acceptanceCriteria" :key="criteria">{{ criteria }}</li>
          </ul>
        </section>

        <section class="structured-section is-full uncertainty-section">
          <h3><TriangleAlert :size="16" /> 不确定信息</h3>
          <ul>
            <li v-for="item in structuredAnswer.uncertainInformation" :key="item">{{ item }}</li>
          </ul>
        </section>
      </div>

      <pre v-else class="rag-answer-text">{{ ragAnswer.answer }}</pre>

      <div class="rag-feedback-panel">
        <div class="rag-feedback-header">
          <strong>回答标注 / 修正</strong>
          <el-button size="small" plain @click="feedbackOpen = !feedbackOpen">
            {{ feedbackOpen ? "收起" : "标注/修正本次回答" }}
          </el-button>
        </div>
        <p>
          发现建议不准确或缺少安全提醒时，可提交修正。修正默认进入待审核，审核通过后进入知识关系图，不会直接污染正式检索依据。
        </p>
        <div v-if="feedbackOpen" class="rag-feedback-form">
          <el-input
            v-model="feedbackForm.correctedAnswer"
            type="textarea"
            :rows="4"
            placeholder="填写修正后的检修建议，可留空并只提交标签或原因"
          />
          <div class="feedback-grid">
            <el-input v-model="feedbackForm.labels" placeholder="标签，用英文逗号分隔" />
            <el-input v-model="feedbackForm.reviewer" placeholder="提交人" />
          </div>
          <el-input v-model="feedbackForm.reason" placeholder="修正原因，例如：缺少安全复核或检查顺序不完整" />
          <div class="action-row">
            <el-button type="primary" size="small" :loading="feedbackSubmitting" @click="submitFeedback">
              提交修正
            </el-button>
            <span>{{ deviceModel }} / {{ maintenanceLevel }}</span>
          </div>
        </div>
      </div>

      <div class="evidence-list">
        <div class="evidence-list-header">
          <strong>
            <Quote :size="15" />
            引用来源
          </strong>
          <span>{{ evidenceSummary }}</span>
        </div>
        <article v-for="item in evidenceItems" :key="item.evidenceId" class="evidence-card">
          <div class="evidence-card-header">
            <span class="source-pill">{{ sourceLabel(item.sourceType) }}</span>
            <strong>{{ item.evidenceId }} / {{ item.title }}</strong>
            <el-tag size="small" :type="item.reviewStatus === 'approved' ? 'success' : 'warning'">
              {{ item.reviewStatus === "approved" ? "已审核" : item.reviewStatus }}
            </el-tag>
          </div>
          <small>{{ item.sourceName }}{{ evidenceMeta(item) ? ` / ${evidenceMeta(item)}` : "" }}</small>
          <p>{{ item.snippet }}</p>
          <div v-if="item.previewUrl" class="visual-citation">
            <VisualEvidenceThumbnail :preview-url="item.previewUrl" :alt="`${item.title} 引用图片`" />
            <dl>
              <div><dt>页码</dt><dd>{{ item.page ? `第 ${item.page} 页` : "未上报" }}</dd></div>
              <div><dt>视觉类型</dt><dd>{{ item.visualType || "unknown" }}</dd></div>
              <div><dt>Provider</dt><dd>{{ item.analysisProvider || "未上报" }}</dd></div>
              <div><dt>Fallback</dt><dd>{{ item.analysisFallback ? "是" : "否" }}</dd></div>
              <div><dt>语义验证</dt><dd>{{ item.semanticVerified ? "真实图片理解" : "OCR/上下文降级" }}</dd></div>
            </dl>
          </div>
          <span class="trace-line">{{ traceText(item.trace) }}</span>
        </article>
      </div>

      <details v-if="ragAnswer.rawAnswer" class="raw-answer">
        <summary>查看模型原文</summary>
        <p>{{ ragAnswer.rawAnswer }}</p>
      </details>
      <small v-if="ragAnswer.fallbackReason" class="fallback-note">{{ ragAnswer.fallbackReason }}</small>
    </article>

    <div v-else class="empty-hint">
      <span>请先完成故障描述和参考依据匹配，再生成智能检修建议。</span>
    </div>
  </section>
</template>
