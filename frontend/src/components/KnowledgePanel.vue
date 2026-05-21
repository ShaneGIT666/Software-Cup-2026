<script setup lang="ts">
import { onMounted, ref } from "vue";
import { Database, UploadCloud } from "@lucide/vue";
import { ElMessage } from "element-plus";
import { fetchKnowledgeDocuments, uploadKnowledgeDocument, type KnowledgeDocument } from "../api";

const documents = ref<KnowledgeDocument[]>([]);
const loading = ref(false);
const uploading = ref(false);
const sourceName = ref("摩托车检修手册");
const lastUploaded = ref<KnowledgeDocument | null>(null);

function statusText(status: string) {
  const statusMap: Record<string, string> = {
    indexed: "已入库",
    needs_parser: "待安装解析器",
    needs_ocr: "待 OCR",
    empty: "无可解析文本"
  };
  return statusMap[status] ?? status;
}

function statusType(status: string) {
  if (status === "indexed") {
    return "success";
  }
  if (status === "needs_parser" || status === "needs_ocr") {
    return "warning";
  }
  return "info";
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

onMounted(loadDocuments);

defineExpose({ loadDocuments });
</script>

<template>
  <section class="knowledge-panel">
    <div class="section-title">
      <Database :size="18" />
      <span>资料入库</span>
    </div>
    <p class="panel-note">上传 PDF、TXT 或 Markdown 资料，系统会先解析为本地知识片段，后续 RAG 和 OCR 能直接复用。</p>

    <div class="knowledge-upload">
      <el-input v-model="sourceName" placeholder="资料来源名称，例如：摩托车检修手册" />
      <label class="upload-button knowledge-upload-button" :class="{ disabled: uploading }">
        <UploadCloud :size="16" />
        <span>{{ uploading ? "入库中" : "上传资料" }}</span>
        <input type="file" accept=".pdf,.txt,.md,text/plain,text/markdown,application/pdf" :disabled="uploading" @change="handleFileChange" />
      </label>
    </div>

    <div v-if="lastUploaded" class="knowledge-status">
      <strong>{{ lastUploaded.fileName }}</strong>
      <span>{{ statusText(lastUploaded.status) }} · {{ lastUploaded.chunkCount }} 个片段 · {{ lastUploaded.parser }}</span>
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
      </article>
    </div>
    <div v-else class="empty-hint">
      <span>尚未入库资料。建议先上传一份摩托车检修手册 PDF 或 Markdown 摘要。</span>
    </div>
  </section>
</template>
