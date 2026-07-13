<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";
import { ImageOff, Maximize2 } from "@lucide/vue";
import { fetchProtectedBlob } from "../api";

const props = withDefaults(
  defineProps<{
    previewUrl: string;
    alt?: string;
  }>(),
  { alt: "维修手册视觉证据" }
);

const objectUrl = ref("");
const loading = ref(false);
const failed = ref(false);

function releaseObjectUrl() {
  if (objectUrl.value) {
    URL.revokeObjectURL(objectUrl.value);
    objectUrl.value = "";
  }
}

async function loadPreview() {
  releaseObjectUrl();
  failed.value = false;
  if (!props.previewUrl) {
    failed.value = true;
    return;
  }
  loading.value = true;
  try {
    const blob = await fetchProtectedBlob(props.previewUrl);
    objectUrl.value = URL.createObjectURL(blob);
  } catch {
    failed.value = true;
  } finally {
    loading.value = false;
  }
}

function openPreview() {
  if (objectUrl.value) {
    window.open(objectUrl.value, "_blank", "noopener,noreferrer");
  }
}

watch(() => props.previewUrl, loadPreview, { immediate: true });
onBeforeUnmount(releaseObjectUrl);
</script>

<template>
  <button
    v-if="objectUrl"
    type="button"
    class="visual-evidence-thumbnail"
    :aria-label="`放大查看：${alt}`"
    @click="openPreview"
  >
    <img :src="objectUrl" :alt="alt" />
    <span class="visual-evidence-zoom"><Maximize2 :size="15" /></span>
  </button>
  <div v-else class="visual-evidence-thumbnail visual-evidence-placeholder" role="status">
    <ImageOff :size="18" />
    <span>{{ loading ? "正在读取图片" : failed ? "图片预览不可用" : "等待图片预览" }}</span>
  </div>
</template>
