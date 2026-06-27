<script setup lang="ts">
import { onMounted, ref } from "vue";
import { Database, History, Pencil, UploadCloud, WandSparkles } from "@lucide/vue";
import { ElMessage } from "element-plus";
import {
  analyzeKnowledgeDocument,
  fetchKnowledgeDocumentChunks,
  fetchKnowledgeDocumentRevisions,
  fetchKnowledgeDocuments,
  reviseKnowledgeChunk,
  updateKnowledgeChunkStatus,
  uploadKnowledgeDocument,
  type KnowledgeChunkPreview,
  type KnowledgeDocument,
  type KnowledgeRevision
} from "../api";

const documents = ref<KnowledgeDocument[]>([]);
const loading = ref(false);
const uploading = ref(false);
const analyzingId = ref("");
const sourceName = ref("设备检修资料");
const lastUploaded = ref<KnowledgeDocument | null>(null);

const revisionDialogVisible = ref(false);
const revisionLoading = ref(false);
const revisionSaving = ref(false);
const statusSaving = ref(false);
const selectedDocument = ref<KnowledgeDocument | null>(null);
const selectedChunkId = ref("");
const documentChunks = ref<KnowledgeChunkPreview[]>([]);
const documentRevisions = ref<KnowledgeRevision[]>([]);
const revisionForm = ref({
  title: "",
  sourceName: "",
  page: null as number | null,
  content: "",
  tags: "",
  reason: "",
  reviewer: "operator"
});
const lifecycleForm = ref({
  status: "pending_review" as "draft" | "pending_review" | "approved" | "rejected" | "deprecated" | "replaced",
  reason: "",
  reviewer: "operator",
  replacementChunkId: ""
});

function statusText(status: string) {
  const statusMap: Record<string, string> = {
    indexed: "已入库",
    pending_review: "待审核",
    analyzed: "多模态已分析",
    analyzing: "分析中",
    needs_multimodal_analysis: "待多模态分析",
    needs_parser: "待解析",
    needs_ocr: "待 OCR",
    empty: "无可解析文本"
  };
  return statusMap[status] ?? status;
}

function statusType(status: string) {
  if (status === "indexed" || status === "analyzed") {
    return "success";
  }
  if (
    status === "pending_review" ||
    status === "needs_parser" ||
    status === "needs_ocr" ||
    status === "needs_multimodal_analysis" ||
    status === "analyzing"
  ) {
    return "warning";
  }
  return "info";
}

function assetStatusText(status?: string) {
  if (status === "fallback_completed") {
    return "PDF 页面视觉资产已生成";
  }
  const statusMap: Record<string, string> = {
    queued: "图片资产待分析",
    running: "图片资产分析中",
    completed: "图片资产分析完成",
    failed: "图片资产分析失败",
    skipped: "未发现图片资产或未启用"
  };
  return status ? statusMap[status] ?? status : "未触发图片资产分析";
}

function assetStatusType(status?: string) {
  if (status === "completed" || status === "fallback_completed") {
    return "success";
  }
  if (status === "queued" || status === "running") {
    return "warning";
  }
  if (status === "failed") {
    return "danger";
  }
  return "info";
}

function knowledgeTypeText(type?: string) {
  if (type === "pdf_page_visual_asset") {
    return "PDF 页面视觉资产";
  }
  const labels: Record<string, string> = {
    manual_excerpt: "手册文本",
    ocr_result: "OCR 结果",
    image_analysis: "图片分析",
    inspection_step: "检查步骤",
    repair_step: "维修步骤",
    safety_warning: "安全提醒",
    acceptance_criteria: "验收标准",
    case_summary: "案例摘要",
    troubleshooting: "故障排查"
  };
  return type ? labels[type] ?? type : "知识片段";
}

function chunkAssetName(chunk?: KnowledgeChunkPreview) {
  return chunk?.assetName ?? chunk?.evidence_location?.assetName ?? "";
}

function canAnalyze(document: KnowledgeDocument) {
  return ["pdf", "docx", "pptx", "xlsx", "jpg", "jpeg", "png", "webp"].includes(document.suffix);
}

async function loadDocuments() {
  loading.value = true;
  try {
    const payload = await fetchKnowledgeDocuments();
    documents.value = payload.items;
  } catch {
    ElMessage.error("资料列表加载失败，请确认后端服务已启动。");
  } finally {
    loading.value = false;
  }
}

async function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) {
    return;
  }
  uploading.value = true;
  try {
    lastUploaded.value = await uploadKnowledgeDocument(file, sourceName.value);
    ElMessage.success(`资料已进入审核队列：${lastUploaded.value.fileName}`);
    await loadDocuments();
  } catch {
    ElMessage.error("资料上传失败，请检查文件格式或大小。");
  } finally {
    input.value = "";
    uploading.value = false;
  }
}

async function handleAnalyze(document: KnowledgeDocument) {
  analyzingId.value = document.id;
  try {
    lastUploaded.value = await analyzeKnowledgeDocument(document.id);
    ElMessage.success(`资料分析已完成：${lastUploaded.value.fileName}`);
    await loadDocuments();
  } catch {
    ElMessage.error("资料分析失败，请稍后重试。");
  } finally {
    analyzingId.value = "";
  }
}

function fillRevisionForm(chunk: KnowledgeChunkPreview | undefined, document: KnowledgeDocument) {
  selectedChunkId.value = chunk?.id ?? "";
  revisionForm.value = {
    title: chunk?.title ?? document.fileName,
    sourceName: chunk?.sourceName ?? document.sourceName,
    page: chunk?.page ?? null,
    content: chunk?.content ?? chunk?.snippet ?? "",
    tags: chunk?.revisionTags?.join(", ") ?? "",
    reason: "",
    reviewer: "operator"
  };
  lifecycleForm.value = {
    status: (chunk?.review_status as typeof lifecycleForm.value.status) ?? "pending_review",
    reason: chunk?.review_reason ?? "",
    reviewer: chunk?.reviewer ?? "operator",
    replacementChunkId: chunk?.replaced_by ?? ""
  };
}

async function openRevisionDialog(document: KnowledgeDocument) {
  selectedDocument.value = document;
  revisionDialogVisible.value = true;
  revisionLoading.value = true;
  try {
    const [chunksPayload, revisionsPayload] = await Promise.all([
      fetchKnowledgeDocumentChunks(document.id),
      fetchKnowledgeDocumentRevisions(document.id)
    ]);
    documentChunks.value = chunksPayload.items;
    documentRevisions.value = revisionsPayload.items;
    fillRevisionForm(documentChunks.value[0], document);
  } catch {
    ElMessage.error("知识片段读取失败，请稍后重试。");
  } finally {
    revisionLoading.value = false;
  }
}

function handleChunkSelection(chunkId: string) {
  const chunk = documentChunks.value.find((item) => item.id === chunkId);
  if (chunk && selectedDocument.value) {
    fillRevisionForm(chunk, selectedDocument.value);
  }
}

async function saveRevision() {
  if (!selectedDocument.value || !selectedChunkId.value) {
    ElMessage.warning("请选择需要修正的知识片段。");
    return;
  }
  if (!revisionForm.value.content.trim()) {
    ElMessage.warning("修正内容不能为空。");
    return;
  }
  revisionSaving.value = true;
  try {
    await reviseKnowledgeChunk(selectedDocument.value.id, selectedChunkId.value, {
      title: revisionForm.value.title,
      sourceName: revisionForm.value.sourceName,
      page: revisionForm.value.page,
      content: revisionForm.value.content,
      tags: revisionForm.value.tags.split(",").map((tag) => tag.trim()).filter(Boolean),
      reason: revisionForm.value.reason,
      reviewer: revisionForm.value.reviewer
    });
    ElMessage.success("知识片段修正已保存，并重新同步索引。");
    await openRevisionDialog(selectedDocument.value);
    await loadDocuments();
  } catch {
    ElMessage.error("知识片段修正失败，请稍后重试。");
  } finally {
    revisionSaving.value = false;
  }
}

async function saveChunkStatus() {
  if (!selectedDocument.value || !selectedChunkId.value) {
    ElMessage.warning("请选择需要维护状态的知识片段。");
    return;
  }
  if (["rejected", "deprecated", "replaced"].includes(lifecycleForm.value.status) && !lifecycleForm.value.reason.trim()) {
    ElMessage.warning("拒绝、废弃或替换片段必须填写原因。");
    return;
  }
  if (lifecycleForm.value.status === "replaced" && !lifecycleForm.value.replacementChunkId.trim()) {
    ElMessage.warning("替换片段必须填写 replacementChunkId。");
    return;
  }
  statusSaving.value = true;
  try {
    await updateKnowledgeChunkStatus(selectedDocument.value.id, selectedChunkId.value, {
      status: lifecycleForm.value.status,
      reason: lifecycleForm.value.reason,
      reviewer: lifecycleForm.value.reviewer,
      replacementChunkId: lifecycleForm.value.replacementChunkId || null
    });
    ElMessage.success("知识片段状态已更新，并同步检索索引。");
    await openRevisionDialog(selectedDocument.value);
    await loadDocuments();
  } catch {
    ElMessage.error("知识片段状态更新失败，请稍后重试。");
  } finally {
    statusSaving.value = false;
  }
}

onMounted(loadDocuments);

defineExpose({ loadDocuments });
</script>

<template>
  <section class="knowledge-panel panel-highlight">
    <div class="section-title">
      <Database :size="18" />
      <span>资料入库</span>
    </div>
    <p class="panel-note">
      上传 PDF、Office、Markdown 或图片资料。解析结果默认进入待审核，审核通过前不会参与正式检索；
      若 MinerU 提取到图片资产，系统会生成 OCR 和图片分析片段。
    </p>

    <div class="knowledge-upload">
      <el-input v-model="sourceName" placeholder="资料来源名称，例如：设备检修手册" />
      <label class="upload-button knowledge-upload-button" :class="{ disabled: uploading }">
        <UploadCloud :size="16" />
        <span>{{ uploading ? "入库中" : "上传资料" }}</span>
        <input
          type="file"
          accept=".pdf,.docx,.pptx,.xlsx,.txt,.md,.jpg,.jpeg,.png,.webp,text/plain,text/markdown,application/pdf,image/jpeg,image/png,image/webp"
          :disabled="uploading"
          @change="handleFileChange"
        />
      </label>
    </div>

    <div v-if="lastUploaded" class="knowledge-status">
      <strong>{{ lastUploaded.fileName }}</strong>
      <span>{{ statusText(lastUploaded.status) }} / {{ lastUploaded.chunkCount }} 个片段 / {{ lastUploaded.parser }}</span>
      <small v-if="lastUploaded.assetAnalysisStatus" class="asset-status-line">
        图片资产：{{ assetStatusText(lastUploaded.assetAnalysisStatus) }}
        / {{ lastUploaded.assetAnalysisCount ?? 0 }} 个片段
        / {{ lastUploaded.assetAnalysisFallbackCount ?? 0 }} 次降级
      </small>
      <small v-if="lastUploaded.parserFallbackReason" class="fallback-note">{{ lastUploaded.parserFallbackReason }}</small>
      <p v-if="lastUploaded.analysis?.summary">{{ lastUploaded.analysis.summary }}</p>
      <small v-if="lastUploaded.analysis?.fallbackReason" class="fallback-note">{{ lastUploaded.analysis.fallbackReason }}</small>
    </div>

    <div v-if="loading" class="loading-hint processing-card">
      <span>正在读取资料库...</span>
    </div>
    <div v-else-if="documents.length" class="knowledge-list">
      <article v-for="document in documents" :key="document.id" class="knowledge-card">
        <div>
          <strong>{{ document.sourceName }}</strong>
          <el-tag :type="statusType(document.status)" size="small">{{ statusText(document.status) }}</el-tag>
        </div>
        <p>{{ document.fileName }}</p>
        <small>
          {{ document.chunkCount }} 个片段 / {{ document.parser }} / {{ document.uploadedAt }}
          <span v-if="document.pendingReviewCount"> / {{ document.pendingReviewCount }} 个待审核</span>
          <span v-if="document.revisionCount"> / {{ document.revisionCount }} 次修正</span>
        </small>
        <div class="asset-status-row">
          <el-tag :type="assetStatusType(document.assetAnalysisStatus)" size="small" effect="plain">
            {{ assetStatusText(document.assetAnalysisStatus) }}
          </el-tag>
          <span>{{ document.assetAnalysisCount ?? 0 }} 个图片片段</span>
          <span>{{ document.assetAnalysisFallbackCount ?? 0 }} 次 LLM/OCR 降级</span>
        </div>
        <small v-if="document.assetAnalysisError" class="fallback-note">{{ document.assetAnalysisError }}</small>
        <small v-if="document.parserFallbackReason" class="fallback-note">{{ document.parserFallbackReason }}</small>
        <p v-if="document.analysis?.summary" class="knowledge-analysis-summary">{{ document.analysis.summary }}</p>
        <small v-if="document.analysis?.fallbackReason" class="fallback-note">{{ document.analysis.fallbackReason }}</small>
        <div v-if="document.analysis?.keyComponents?.length" class="knowledge-tags">
          <el-tag v-for="item in document.analysis.keyComponents" :key="item" size="small" effect="plain">{{ item }}</el-tag>
        </div>
        <div class="knowledge-actions">
          <el-button
            v-if="canAnalyze(document)"
            class="knowledge-analyze-button"
            type="warning"
            size="small"
            plain
            :loading="analyzingId === document.id"
            @click="handleAnalyze(document)"
          >
            <WandSparkles :size="14" />
            分析图片资产
          </el-button>
          <el-button class="knowledge-analyze-button" type="primary" size="small" plain @click="openRevisionDialog(document)">
            <Pencil :size="14" />
            修正片段
          </el-button>
        </div>
      </article>
    </div>
    <div v-else class="empty-hint">
      <span>尚未入库资料。建议先上传一份检修手册 PDF 或 Markdown 摘要。</span>
    </div>

    <el-dialog v-model="revisionDialogVisible" title="知识片段人工修正" width="760px">
      <div v-loading="revisionLoading" class="revision-editor">
        <div v-if="selectedDocument" class="revision-header">
          <strong>{{ selectedDocument.sourceName }}</strong>
          <span>{{ selectedDocument.chunkCount }} 个片段 / {{ selectedDocument.revisionCount ?? 0 }} 次修正</span>
        </div>
        <el-form label-position="top">
          <el-form-item label="选择片段">
            <el-select v-model="selectedChunkId" class="revision-select" @change="handleChunkSelection">
              <el-option
                v-for="chunk in documentChunks"
                :key="chunk.id"
                :label="`${chunk.id} / ${knowledgeTypeText(chunk.knowledge_type)} / ${chunkAssetName(chunk) || chunk.snippet}`"
                :value="chunk.id"
              />
            </el-select>
          </el-form-item>
          <div v-if="selectedChunkId" class="asset-status-row">
            <el-tag size="small" effect="plain">
              {{ knowledgeTypeText(documentChunks.find((item) => item.id === selectedChunkId)?.knowledge_type) }}
            </el-tag>
            <span v-if="chunkAssetName(documentChunks.find((item) => item.id === selectedChunkId))">
              {{ chunkAssetName(documentChunks.find((item) => item.id === selectedChunkId)) }}
            </span>
          </div>
          <div class="revision-grid">
            <el-form-item label="标题">
              <el-input v-model="revisionForm.title" />
            </el-form-item>
            <el-form-item label="来源">
              <el-input v-model="revisionForm.sourceName" />
            </el-form-item>
          </div>
          <el-form-item label="修正内容">
            <el-input v-model="revisionForm.content" type="textarea" :rows="7" />
          </el-form-item>
          <div class="revision-grid">
            <el-form-item label="标签">
              <el-input v-model="revisionForm.tags" placeholder="用逗号分隔，例如：火花塞, 启动困难" />
            </el-form-item>
            <el-form-item label="修正人">
              <el-input v-model="revisionForm.reviewer" />
            </el-form-item>
          </div>
          <el-form-item label="修正原因">
            <el-input v-model="revisionForm.reason" placeholder="例如：一线技师确认模型输出需要修正" />
          </el-form-item>
        </el-form>

        <section class="chunk-lifecycle-panel">
          <div class="revision-history-title">
            <History :size="14" />
            <span>片段状态维护</span>
          </div>
          <div class="revision-grid">
            <el-form-item label="目标状态">
              <el-select v-model="lifecycleForm.status" class="revision-select">
                <el-option label="草稿 draft" value="draft" />
                <el-option label="待审核 pending_review" value="pending_review" />
                <el-option label="已审核 approved" value="approved" />
                <el-option label="已拒绝 rejected" value="rejected" />
                <el-option label="已废弃 deprecated" value="deprecated" />
                <el-option label="已替换 replaced" value="replaced" />
              </el-select>
            </el-form-item>
            <el-form-item label="审核人">
              <el-input v-model="lifecycleForm.reviewer" />
            </el-form-item>
          </div>
          <el-form-item v-if="lifecycleForm.status === 'replaced'" label="替换片段 ID">
            <el-input v-model="lifecycleForm.replacementChunkId" placeholder="例如：doc-xxxx-chunk-002" />
          </el-form-item>
          <el-form-item label="状态原因">
            <el-input
              v-model="lifecycleForm.reason"
              type="textarea"
              :rows="2"
              placeholder="拒绝、废弃或替换时必须填写原因"
            />
          </el-form-item>
          <el-button type="warning" plain :loading="statusSaving" @click="saveChunkStatus">保存状态</el-button>
        </section>

        <section v-if="documentRevisions.length" class="revision-history">
          <div class="revision-history-title">
            <History :size="14" />
            <span>最近修正记录</span>
          </div>
          <article v-for="revision in documentRevisions.slice(0, 3)" :key="revision.id">
            <strong>{{ revision.reviewer }} / {{ revision.createdAt }}</strong>
            <p>{{ revision.reason || "未填写修正原因" }}</p>
            <small>{{ revision.before.content.slice(0, 72) }} -> {{ revision.after.content.slice(0, 72) }}</small>
          </article>
        </section>
      </div>
      <template #footer>
        <el-button @click="revisionDialogVisible = false">关闭</el-button>
        <el-button type="primary" :loading="revisionSaving" @click="saveRevision">保存修正并入库</el-button>
      </template>
    </el-dialog>
  </section>
</template>
