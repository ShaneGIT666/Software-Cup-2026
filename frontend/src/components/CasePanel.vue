<script setup lang="ts">
import { ClipboardCheck, Send } from "@lucide/vue";

defineProps<{
  cause: string;
  solution: string;
  result: string;
  tags: string;
  submitting: boolean;
}>();

const emit = defineEmits<{
  "update:cause": [value: string];
  "update:solution": [value: string];
  "update:result": [value: string];
  "update:tags": [value: string];
  submit: [];
}>();
</script>

<template>
  <section class="case-panel">
    <div class="section-title">
      <ClipboardCheck :size="18" />
      <span>经验案例提交</span>
    </div>
    <el-form label-position="top">
      <el-form-item label="可能原因">
        <el-input :model-value="cause" @update:model-value="emit('update:cause', String($event))" />
      </el-form-item>
      <el-form-item label="处理方案">
        <el-input
          :model-value="solution"
          type="textarea"
          :rows="3"
          @update:model-value="emit('update:solution', String($event))"
        />
      </el-form-item>
      <el-form-item label="处理结果">
        <el-input :model-value="result" @update:model-value="emit('update:result', String($event))" />
      </el-form-item>
      <el-form-item label="标签">
        <el-input :model-value="tags" @update:model-value="emit('update:tags', String($event))" />
      </el-form-item>
      <el-button type="success" :loading="submitting" @click="emit('submit')">
        <Send :size="16" />
        提交审核
      </el-button>
    </el-form>
  </section>
</template>
