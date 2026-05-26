<script setup lang="ts">
import { Search, Upload } from "@lucide/vue";
import type { UploadPayload } from "../api";

defineProps<{
  deviceModel: string;
  faultText: string;
  loading: boolean;
  resultCount: number;
  stepCount: number;
  uploadResult: UploadPayload | null;
  uploading: boolean;
}>();

const emit = defineEmits<{
  "update:deviceModel": [value: string];
  "update:faultText": [value: string];
  search: [];
  upload: [file: File];
}>();

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file) {
    emit("upload", file);
  }
  input.value = "";
}
</script>

<template>
  <aside class="query-panel panel-accent">
    <div class="section-title">
      <Search :size="18" />
      <span>故障输入</span>
    </div>
    <p class="panel-note">输入设备型号与现场现象，系统会检索手册、案例和已入库资料，并给出可解释证据。</p>

    <el-form label-position="top">
      <el-form-item label="设备型号">
        <el-input
          :model-value="deviceModel"
          placeholder="例如：发动机-示例型号 A"
          @update:model-value="emit('update:deviceModel', String($event))"
        />
      </el-form-item>
      <el-form-item label="故障现象">
        <el-input
          :model-value="faultText"
          type="textarea"
          :rows="5"
          placeholder="例如：启动困难，怠速不稳，排气异常"
          @update:model-value="emit('update:faultText', String($event))"
        />
      </el-form-item>
      <div class="action-row">
        <el-button type="primary" :loading="loading" @click="emit('search')">
          <Search :size="16" />
          开始检索
        </el-button>
        <label class="upload-button" :class="{ disabled: uploading }">
          <Upload :size="16" />
          <span>{{ uploading ? "上传中" : "上传现场材料" }}</span>
          <input type="file" accept="image/*,.pdf" :disabled="uploading" @change="handleFileChange" />
        </label>
      </div>
    </el-form>

    <div v-if="uploadResult" class="upload-result">
      <strong>{{ uploadResult.fileName }}</strong>
      <span>{{ uploadResult.id }} / {{ uploadResult.url }}</span>
    </div>

    <div class="metric-grid">
      <div>
        <strong>{{ resultCount }}</strong>
        <span>证据结果</span>
      </div>
      <div>
        <strong>{{ stepCount }}</strong>
        <span>流程步骤</span>
      </div>
    </div>
  </aside>
</template>
