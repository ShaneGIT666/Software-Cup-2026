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
const sourceName = ref("摩托车检修手册");
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
    needs_parser: "待解析器",
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

function canAnalyze(document: KnowledgeDocument) {
  return ["pdf", "jpg", "jpeg", "png", "webp"].includes(document.suffix);
}

async function loadDocuments() {
  loading.value = true;
  try {
    const payload = await fetchKnowledgeDocuments();
    documents.value = payload.items;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "资料列表加载失败");
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
    ElMessage.success(`资料已入库：${lastUploaded.value.fileName}`);
    await loadDocuments();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "资料入库失败");
  } finally {
    input.value = "";
    uploading.value = false;
  }
}

async function handleAnalyze(document: KnowledgeDocument) {
  analyzingId.value = document.id;
  try {
    lastUploaded.value = await analyzeKnowledgeDocument(document.id);
    ElMessage.success(`多模态分析完成：${lastUploaded.value.fileName}`);
    await loadDocuments();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "多模态分析失败");
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
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "知识片段读取失败");
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
    ElMessage.warning("请选择需要修正的知识片段");
    return;
  }
  if (!revisionForm.value.content.trim()) {
    ElMessage.warning("修正内容不能为空");
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
    ElMessage.success("知识片段修正已保存并重新入库");
    await openRevisionDialog(selectedDocument.value);
    await loadDocuments();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "知识片段修正失败");
  } finally {
    revisionSaving.value = false;
  }
}

async function saveChunkStatus() {
  if (!selectedDocument.value || !selectedChunkId.value) {
    ElMessage.warning("请选择需要维护状态的知识片段");
    return;
  }
  if (["rejected", "deprecated", "replaced"].includes(lifecycleForm.value.status) && !lifecycleForm.value.reason.trim()) {
    ElMessage.warning("拒绝、废弃或替换片段必须填写原因");
    return;
  }
  if (lifecycleForm.value.status === "replaced" && !lifecycleForm.value.replacementChunkId.trim()) {
    ElMessage.warning("替换片段必须填写 replacementChunkId");
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
    ElMessage.success("知识片段状态已更新并同步检索索引");
    await openRevisionDialog(selectedDocument.value);
    await loadDocuments();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "知识片段状态更新失败");
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
      <span>资料知识库 / Knowledge Dock</span>
    </div>
    <p class="panel-note">
      上传 PDF、TXT、Markdown 或图片资料。文本会直接切片入库，扫描 PDF 和图片可通过多模态/OCR 生成可检索知识片段，并支持人工修正。
    </p>

    <div class="knowledge-upload">
      <el-input v-model="sourceName" placeholder="资料来源名称，例如：摩托车维修手册" />
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
            多模态分析
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
                :label="`${chunk.id} · ${chunk.snippet}`"
                :value="chunk.id"
              />
            </el-select>
          </el-form-item>
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
              <el-input v-model="revisionForm.tags" placeholder="用逗号分隔，如 火花塞, 启动困难" />
            </el-form-item>
            <el-form-item label="修正人">
              <el-input v-model="revisionForm.reviewer" />
            </el-form-item>
          </div>
          <el-form-item label="修正原因">
            <el-input v-model="revisionForm.reason" placeholder="例如：一线技师确认模型输出需修正" />
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
            <el-input v-model="lifecycleForm.replacementChunkId" placeholder="例如：kdoc-xxxx-chunk-002" />
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
