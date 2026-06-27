<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage } from "element-plus";
import { Bot, CheckCircle2, ClipboardList, FileText, Quote, ShieldAlert, TriangleAlert } from "@lucide/vue";
import type { EvidenceItem, EvidenceTrace, RagAnswerPayload } from "../api";

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
    document_asset: "图片资产"
  };
  return labels[sourceType] ?? sourceType;
}

const structuredAnswer = computed(() => props.ragAnswer?.structuredAnswer ?? null);
const correctiveRag = computed(() => props.ragAnswer?.correctiveRag ?? null);
const safetyRules = computed(() => props.ragAnswer?.safetyRules ?? null);

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
    reviewStatus: citation.reviewStatus ?? "approved",
    riskLevel: citation.riskLevel ?? citation.scoreBreakdown?.riskLevel ?? "unknown",
    score: citation.scoreBreakdown?.score ?? null,
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
    return `${evidenceItems.value.length} 条引用证据`;
  }
  const status = pack.approvedOnly ? "仅 approved" : "含待复核";
  const risk = pack.riskReviewRequired ? "需人工复核" : "未标记高风险";
  return `${pack.evidenceCount} 条证据 / ${status} / ${risk}`;
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
    needs_more_evidence: "需要补充证据"
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
    ElMessage.warning("请填写修正建议、标签或修正原因");
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
      <span>RAG 建议与证据 / Assisted Answer</span>
    </div>
    <p class="panel-note">
      基于当前检索证据生成检修建议，保留 chunk、来源、页码和不确定信息，便于现场复核。
    </p>

    <div class="action-row">
      <el-button type="primary" :loading="loading" @click="emit('answer')">
        <Bot :size="16" />
        生成检修建议
      </el-button>
      <el-tag v-if="ragAnswer?.fallback" type="warning">本地兜底</el-tag>
      <el-tag v-if="ragAnswer && !ragAnswer.fallback" type="success">云端增强</el-tag>
      <el-tag v-if="ragAnswer?.llmAnswerUsed" type="success">真实 LLM 结构化回答</el-tag>
      <el-tag v-if="ragAnswer" type="info">{{ ragAnswer.provider }} / requested {{ ragAnswer.requestedProvider }}</el-tag>
      <el-tag v-if="ragAnswer?.model" type="info">{{ ragAnswer.model }} / {{ ragAnswer.apiStyle }}</el-tag>
      <el-tag v-if="ragAnswer?.contextCount !== undefined" type="info">
        {{ ragAnswer.contextCount }} 条上下文 / {{ ragAnswer.contextChars ?? 0 }} 字符
      </el-tag>
    </div>

    <div v-if="loading" class="loading-hint processing-card">
      <span>正在组织检索上下文、引用来源和检修建议...</span>
    </div>

    <article v-else-if="ragAnswer" class="rag-answer">
      <div v-if="ragAnswer.riskReviewRequired" class="risk-banner">
        <ShieldAlert :size="17" />
        <span>包含 high / critical 风险证据，执行前必须人工复核。</span>
      </div>

      <div v-if="correctiveRag && correctiveRag.action !== 'answer'" class="corrective-panel">
        <div class="corrective-panel-header">
          <TriangleAlert :size="17" />
          <strong>Corrective RAG：{{ correctiveActionLabel(correctiveRag.action) }}</strong>
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
          <strong>安全规则：{{ severityLabel(safetyRules.highestSeverity) }}</strong>
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
          <h3><FileText :size="16" /> 建议检查步骤</h3>
          <ol>
            <li v-for="step in structuredAnswer.inspectionSteps" :key="step">{{ step }}</li>
          </ol>
        </section>

        <section class="structured-section">
          <h3><CheckCircle2 :size="16" /> 建议维修步骤</h3>
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
            {{ feedbackOpen ? "收起" : "标注/修正本回答" }}
          </el-button>
        </div>
        <p>
          标注结果默认进入 pending_review，审核通过后进入轻量知识关系网络，不会直接污染正式 RAG 检索证据。
        </p>
        <div v-if="feedbackOpen" class="rag-feedback-form">
          <el-input
            v-model="feedbackForm.correctedAnswer"
            type="textarea"
            :rows="4"
            placeholder="填写修正后的检修建议，可保留为空，仅提交标签或原因"
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
            引用证据
          </strong>
          <span>{{ evidenceSummary }}</span>
        </div>
        <article v-for="item in evidenceItems" :key="item.evidenceId" class="evidence-card">
          <div class="evidence-card-header">
            <span class="source-pill">{{ sourceLabel(item.sourceType) }}</span>
            <strong>{{ item.evidenceId }} / {{ item.title }}</strong>
            <el-tag size="small" :type="item.reviewStatus === 'approved' ? 'success' : 'warning'">
              {{ item.reviewStatus }}
            </el-tag>
          </div>
          <small>{{ item.sourceName }}{{ evidenceMeta(item) ? ` / ${evidenceMeta(item)}` : "" }}</small>
          <p>{{ item.snippet }}</p>
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
      <span>先完成检索或资料入库，再生成带引用的辅助建议。</span>
    </div>
  </section>
</template>
