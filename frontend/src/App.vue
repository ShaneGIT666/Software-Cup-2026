<script setup lang="ts">
import { computed, ref } from "vue";
import { ClipboardCheck, FileText, Search, Send, ShieldCheck, Wrench } from "@lucide/vue";
import { ElMessage } from "element-plus";
import { fetchWorkflow, searchKnowledge, submitCase, type SearchPayload, type SearchResult, type WorkflowPayload } from "./api";

const deviceModel = ref("发动机-示例型号 A");
const faultText = ref("启动困难，怠速不稳，排气异常");
const loading = ref(false);
const submitting = ref(false);
const searchPayload = ref<SearchPayload | null>(null);
const selectedWorkflow = ref<WorkflowPayload | null>(null);
const selectedResult = ref<SearchResult | null>(null);

const caseForm = ref({
  cause: "火花塞积碳",
  solution: "清理并更换火花塞，复查燃油滤清器。",
  result: "启动恢复正常，怠速稳定。",
  tags: "启动困难, 点火系统, 火花塞"
});

const resultCount = computed(() => searchPayload.value?.results.length ?? 0);

async function runSearch() {
  loading.value = true;
  selectedWorkflow.value = null;
  selectedResult.value = null;
  try {
    searchPayload.value = await searchKnowledge(deviceModel.value, faultText.value);
    const firstWorkflowId = searchPayload.value.results.find((item) => item.workflowId)?.workflowId;
    if (firstWorkflowId) {
      await openWorkflow(searchPayload.value.results[0]);
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "检索失败");
  } finally {
    loading.value = false;
  }
}

async function openWorkflow(result: SearchResult) {
  if (!result.workflowId) {
    ElMessage.warning("该结果暂未关联作业流程");
    return;
  }
  selectedResult.value = result;
  selectedWorkflow.value = await fetchWorkflow(result.workflowId);
}

async function createCase() {
  submitting.value = true;
  try {
    const result = await submitCase({
      deviceModel: deviceModel.value,
      faultText: faultText.value,
      cause: caseForm.value.cause,
      solution: caseForm.value.solution,
      result: caseForm.value.result,
      tags: caseForm.value.tags.split(",").map((tag) => tag.trim()).filter(Boolean)
    });
    ElMessage.success(`案例已提交：${result.id}`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "提交失败");
  } finally {
    submitting.value = false;
  }
}

runSearch();
</script>

<template>
  <main class="shell">
    <section class="hero">
      <div>
        <p class="eyebrow">Software Cup 2026 MVP</p>
        <h1>设备检修知识检索与作业辅助系统</h1>
        <p class="subtle">围绕检索、作业指导、经验沉淀三个环节搭建最小可运行闭环。</p>
      </div>
      <div class="status-strip">
        <span>Mock 模型</span>
        <span>关键词检索</span>
        <span>本地样例数据</span>
      </div>
    </section>

    <section class="workspace">
      <aside class="query-panel">
        <div class="section-title">
          <Search :size="18" />
          <span>检索输入</span>
        </div>
        <el-form label-position="top">
          <el-form-item label="设备型号">
            <el-input v-model="deviceModel" />
          </el-form-item>
          <el-form-item label="故障现象">
            <el-input v-model="faultText" type="textarea" :rows="5" />
          </el-form-item>
          <el-button type="primary" :loading="loading" @click="runSearch">
            <Search :size="16" />
            开始检索
          </el-button>
        </el-form>

        <div class="metric-grid">
          <div>
            <strong>{{ resultCount }}</strong>
            <span>条结果</span>
          </div>
          <div>
            <strong>{{ selectedWorkflow?.steps.length ?? 0 }}</strong>
            <span>个步骤</span>
          </div>
        </div>
      </aside>

      <section class="results-panel">
        <div class="section-title">
          <FileText :size="18" />
          <span>知识结果</span>
        </div>
        <p class="summary">{{ searchPayload?.summary }}</p>
        <div class="result-list">
          <button
            v-for="item in searchPayload?.results"
            :key="item.id"
            class="result-item"
            :class="{ active: selectedResult?.id === item.id }"
            @click="openWorkflow(item)"
          >
            <div>
              <strong>{{ item.title }}</strong>
              <span>{{ item.sourceName }} {{ item.chapter ? ` / ${item.chapter}` : "" }}</span>
            </div>
            <p>{{ item.snippet }}</p>
            <small>置信度 {{ Math.round(item.confidence * 100) }}%</small>
          </button>
        </div>
      </section>

      <section class="workflow-panel">
        <div class="section-title">
          <Wrench :size="18" />
          <span>作业指导</span>
        </div>
        <template v-if="selectedWorkflow">
          <h2>{{ selectedWorkflow.title }}</h2>
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
      </section>

      <section class="case-panel">
        <div class="section-title">
          <ClipboardCheck :size="18" />
          <span>经验案例提交</span>
        </div>
        <el-form label-position="top">
          <el-form-item label="可能原因">
            <el-input v-model="caseForm.cause" />
          </el-form-item>
          <el-form-item label="处理方案">
            <el-input v-model="caseForm.solution" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item label="处理结果">
            <el-input v-model="caseForm.result" />
          </el-form-item>
          <el-form-item label="标签">
            <el-input v-model="caseForm.tags" />
          </el-form-item>
          <el-button type="success" :loading="submitting" @click="createCase">
            <Send :size="16" />
            提交审核
          </el-button>
        </el-form>
      </section>
    </section>
  </main>
</template>
