<script setup lang="ts">
import { ImagePlus, Search, Upload } from "@lucide/vue";
import type { UploadPayload } from "../api";

defineProps<{
  deviceModel: string;
  faultText: string;
  maintenanceLevel: string;
  loading: boolean;
  diagnosisLoading: boolean;
  resultCount: number;
  stepCount: number;
  uploadResult: UploadPayload | null;
  uploading: boolean;
  diagnosisSummary?: string;
  diagnosisFallback?: boolean;
}>();

const emit = defineEmits<{
  "update:deviceModel": [value: string];
  "update:faultText": [value: string];
  "update:maintenanceLevel": [value: string];
  search: [];
  upload: [file: File];
  diagnose: [file: File | null];
}>();

function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file) {
    emit("upload", file);
  }
  input.value = "";
}

function handleDiagnosisFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  emit("diagnose", input.files?.[0] ?? null);
  input.value = "";
}
</script>

<template>
  <aside class="query-panel panel-accent">
    <div class="section-title">
      <Search :size="18" />
      <span>检索诊断</span>
    </div>
    <p class="panel-note">
      输入设备型号、故障现象和检修等级。可上传现场图片触发 OCR/多模态分析，图片线索只用于扩展诊断上下文，审核前不会直接进入正式知识库。
    </p>

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
      <el-form-item label="检修等级">
        <el-select
          :model-value="maintenanceLevel"
          placeholder="选择检修等级"
          @update:model-value="emit('update:maintenanceLevel', String($event))"
        >
          <el-option label="日常检查" value="daily_check" />
          <el-option label="一般检修" value="normal_repair" />
          <el-option label="重大检修" value="major_repair" />
          <el-option label="紧急处置" value="emergency" />
        </el-select>
      </el-form-item>
      <div class="action-row">
        <el-button type="primary" :loading="loading" @click="emit('search')">
          <Search :size="16" />
          开始检索
        </el-button>
        <label class="upload-button" :class="{ disabled: uploading }">
          <Upload :size="16" />
          <span>{{ uploading ? "上传中" : "上传资料" }}</span>
          <input type="file" accept="image/*,.pdf" :disabled="uploading" @change="handleFileChange" />
        </label>
        <label class="upload-button diagnosis" :class="{ disabled: diagnosisLoading }">
          <ImagePlus :size="16" />
          <span>{{ diagnosisLoading ? "诊断中" : "图片诊断" }}</span>
          <input type="file" accept="image/*" :disabled="diagnosisLoading" @change="handleDiagnosisFileChange" />
        </label>
      </div>
    </el-form>

    <div v-if="uploadResult" class="upload-result">
      <strong>{{ uploadResult.fileName }}</strong>
      <span>{{ uploadResult.id }} / {{ uploadResult.url }}</span>
    </div>

    <div v-if="diagnosisSummary" class="diagnosis-result" :class="{ fallback: diagnosisFallback }">
      <strong>{{ diagnosisFallback ? "图片诊断已降级" : "图片诊断线索" }}</strong>
      <span>{{ diagnosisSummary }}</span>
    </div>

    <div class="metric-grid">
      <div>
        <strong>{{ resultCount }}</strong>
        <span>证据结果</span>
      </div>
      <div>
        <strong>{{ stepCount }}</strong>
        <span>作业步骤</span>
      </div>
    </div>
  </aside>
</template>
