<script setup lang="ts">
import { ShieldCheck, Wrench } from "@lucide/vue";
import type { WorkflowPayload } from "../api";

defineProps<{
  selectedWorkflow: WorkflowPayload | null;
}>();
</script>

<template>
  <section class="workflow-panel">
    <div class="section-title">
      <Wrench :size="18" />
      <span>标准作业 / Procedure Core</span>
    </div>
    <template v-if="selectedWorkflow">
      <h2>{{ selectedWorkflow.title }}</h2>
      <div class="workflow-meta">
        <span>{{ selectedWorkflow.deviceType }}</span>
        <span>{{ selectedWorkflow.faultType }}</span>
        <span>{{ selectedWorkflow.level }}</span>
      </div>
      <div class="tag-row">
        <el-tag v-for="tool in selectedWorkflow.tools" :key="tool" effect="plain">{{ tool }}</el-tag>
      </div>
      <el-steps direction="vertical" :active="selectedWorkflow.steps.length">
        <el-step
          v-for="step in selectedWorkflow.steps"
          :key="step.order"
          :title="`${step.order}. ${step.title}`"
          :description="step.description"
        />
      </el-steps>
      <div class="notice">
        <ShieldCheck :size="18" />
        <span>{{ selectedWorkflow.safetyNotes.join(" / ") }}</span>
      </div>
    </template>
    <div v-else class="empty-hint">
      <span>点击检索证据，查看对应的标准作业流程。</span>
    </div>
  </section>
</template>
