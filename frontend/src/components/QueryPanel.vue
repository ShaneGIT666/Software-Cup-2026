<script setup lang="ts">
import { ImagePlus, Search, Upload } from "@lucide/vue";
import type { MultimodalSignals, UploadPayload } from "../api";

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
  multimodalSignals?: MultimodalSignals | null;
}>();

const emit = defineEmits<{
  "update:deviceModel": [value: string];
  "update:faultText": [value: string];
  "update:maintenanceLevel": [value: string];
  search: [];
  upload: [file: File];
  diagnose: [file: File | null];
  demo: [];
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
      <span>步骤 1：描述故障</span>
    </div>
    <p class="panel-note">
      输入设备型号、故障现象和检修等级；可上传现场故障图片，系统会提取图片识别线索辅助诊断。
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
          开始诊断
        </el-button>
        <el-button plain @click="emit('demo')">使用演示样例</el-button>
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
      <span>资料已上传，可在管理中心继续审核入库。</span>
    </div>

    <div v-if="diagnosisSummary" class="diagnosis-result" :class="{ fallback: diagnosisFallback }">
      <strong>{{ diagnosisFallback ? "图片诊断已降级完成" : "图片识别线索" }}</strong>
      <span>{{ diagnosisSummary }}</span>
    </div>

    <div v-if="multimodalSignals" class="cross-modal-box">
      <strong>图片识别线索</strong>
      <p v-if="multimodalSignals.ocrText">OCR：{{ multimodalSignals.ocrText }}</p>
      <p v-if="multimodalSignals.visualSymptoms.length">
        视觉现象：{{ multimodalSignals.visualSymptoms.join("、") }}
      </p>
      <p v-if="multimodalSignals.detectedComponents.length">
        识别部件：{{ multimodalSignals.detectedComponents.join("、") }}
      </p>
      <p>降级：{{ multimodalSignals.fallback ? "是" : "否" }} / 来源：{{ multimodalSignals.signalSource }}</p>
      <span>说明：图片线索只用于增强当前诊断上下文，正式建议仍基于已审核资料。</span>
    </div>

    <div class="metric-grid">
      <div>
        <strong>{{ resultCount }}</strong>
        <span>参考依据</span>
      </div>
      <div>
        <strong>{{ stepCount }}</strong>
        <span>作业步骤</span>
      </div>
    </div>
  </aside>
</template>
