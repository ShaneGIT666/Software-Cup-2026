<script setup lang="ts">
import { onMounted, ref } from "vue";
import { Database, UploadCloud, WandSparkles } from "@lucide/vue";
import { ElMessage } from "element-plus";
import { analyzeKnowledgeDocument, fetchKnowledgeDocuments, uploadKnowledgeDocument, type KnowledgeDocument } from "../api";

const documents = ref<KnowledgeDocument[]>([]);
const loading = ref(false);
const uploading = ref(false);
const analyzingId = ref("");
const sourceName = ref("摩托车检修手册");
const lastUploaded = ref<KnowledgeDocument | null>(null);

function statusText(status: string) {
  const statusMap: Record<string, string> = {
    indexed: "已入库",
    analyzed: "多模态已分析",
    analyzing: "分析中",
    needs_multimodal_analysis: "待多模态分析",
    needs_parser: "待安装解析器",
    needs_ocr: "待 OCR",
    empty: "无可解析文本"
  };
  return statusMap[status] ?? status;
}

function statusType(status: string) {
  if (status === "indexed" || status === "analyzed") {
    return "success";
  }
  if (status === "needs_parser" || status === "needs_ocr" || status === "needs_multimodal_analysis" || status === "analyzing") {
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

onMounted(loadDocuments);

defineExpose({ loadDocuments });
</script>

<template>
  <section class="knowledge-panel">
    <div class="section-title">
      <Database :size="18" />
      <span>资料知识库</span>
    </div>
    <p class="panel-note">上传 PDF、TXT、Markdown 或图片资料。系统优先解析本地文本，扫描 PDF 和图片可通过多模态分析生成可检索知识片段。</p>

    <div class="knowledge-upload">
      <el-input v-model="sourceName" placeholder="资料来源名称，例如：摩托车检修手册" />
      <label class="upload-button knowledge-upload-button" :class="{ disabled: uploading }">
        <UploadCloud :size="16" />
        <span>{{ uploading ? "入库中" : "上传资料" }}</span>
        <input type="file" accept=".pdf,.txt,.md,.jpg,.jpeg,.png,.webp,text/plain,text/markdown,application/pdf,image/jpeg,image/png,image/webp" :disabled="uploading" @change="handleFileChange" />
      </label>
    </div>

    <div v-if="lastUploaded" class="knowledge-status">
      <strong>{{ lastUploaded.fileName }}</strong>
      <span>{{ statusText(lastUploaded.status) }} · {{ lastUploaded.chunkCount }} 个片段 · {{ lastUploaded.parser }}</span>
      <p v-if="lastUploaded.analysis?.summary">{{ lastUploaded.analysis.summary }}</p>
    </div>

    <div v-if="loading" class="loading-hint">
      <span>正在读取资料库...</span>
    </div>
    <div v-else-if="documents.length" class="knowledge-list">
      <article v-for="document in documents" :key="document.id" class="knowledge-card">
        <div>
          <strong>{{ document.sourceName }}</strong>
          <el-tag :type="statusType(document.status)" size="small">{{ statusText(document.status) }}</el-tag>
        </div>
        <p>{{ document.fileName }}</p>
        <small>{{ document.chunkCount }} 个片段 · {{ document.parser }} · {{ document.uploadedAt }}</small>
        <p v-if="document.analysis?.summary" class="knowledge-analysis-summary">{{ document.analysis.summary }}</p>
        <div v-if="document.analysis?.keyComponents?.length" class="knowledge-tags">
          <el-tag v-for="item in document.analysis.keyComponents" :key="item" size="small" effect="plain">{{ item }}</el-tag>
        </div>
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
      </article>
    </div>
    <div v-else class="empty-hint">
      <span>尚未入库资料。建议先上传一份摩托车检修手册 PDF 或 Markdown 摘要。</span>
    </div>
  </section>
</template>
