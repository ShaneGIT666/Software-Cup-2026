<script setup lang="ts">
import { computed } from "vue";
import { Network } from "@lucide/vue";
import type { KnowledgeGraphPayload } from "../api";

const props = defineProps<{
  graph: KnowledgeGraphPayload | null;
  loading: boolean;
}>();

const emit = defineEmits<{
  refresh: [];
  overview: [];
  rebuild: [];
}>();

const nodeLookup = computed(() => {
  const lookup = new Map<string, string>();
  for (const node of props.graph?.nodes ?? []) {
    lookup.set(node.id, node.label);
  }
  return lookup;
});

const topNodeTypes = computed(() => {
  const types = props.graph?.stats?.nodeTypes ?? {};
  return Object.entries(types)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);
});

function typeLabel(type: string) {
  const labels: Record<string, string> = {
    device: "设备",
    fault: "故障",
    manual: "手册",
    case: "案例",
    document: "资料",
    chunk: "片段",
    workflow: "流程",
    source: "来源",
    term: "术语",
    provider: "模型"
  };
  return labels[type] ?? type;
}

function relationLine(source: string, target: string) {
  return `${nodeLookup.value.get(source) ?? source} -> ${nodeLookup.value.get(target) ?? target}`;
}
</script>

<template>
  <section class="knowledge-graph-panel">
    <div class="section-title">
      <Network :size="18" />
      <span>知识图谱 / Graph RAG Evidence Chain</span>
    </div>
    <p class="panel-note">
      将设备、故障、资料、案例、流程和术语组织成轻量知识关系网络。RAG 回答可沿证据关系生成更可解释的检修建议。
    </p>

    <div class="action-row">
      <el-button type="primary" plain :loading="loading" @click="emit('refresh')">
        <Network :size="16" />
        当前查询子图
      </el-button>
      <el-button plain :loading="loading" @click="emit('overview')">全局图谱</el-button>
      <el-button plain :loading="loading" @click="emit('rebuild')">重建图谱</el-button>
      <el-tag v-if="graph" type="info">
        {{ graph.nodes.length }} 节点 / {{ graph.edges.length }} 关系
      </el-tag>
      <el-tag v-if="graph?.mode" type="success">{{ graph.mode === "global" ? "全局" : "查询" }}</el-tag>
    </div>

    <div v-if="loading" class="loading-hint processing-card">
      <span>正在组织知识图谱与 Graph RAG 证据链...</span>
    </div>

    <article v-else-if="graph" class="graph-content">
      <p>{{ graph.summary }}</p>

      <div v-if="topNodeTypes.length" class="knowledge-tags">
        <el-tag v-for="[type, count] in topNodeTypes" :key="type" effect="plain">
          {{ typeLabel(type) }} {{ count }}
        </el-tag>
      </div>

      <div class="graph-node-list">
        <span v-for="node in graph.nodes.slice(0, 16)" :key="node.id" class="graph-node" :data-type="node.type">
          <small>{{ typeLabel(node.type) }}</small>
          {{ node.label }}
        </span>
      </div>

      <div class="graph-edge-list">
        <div v-for="edge in graph.edges.slice(0, 14)" :key="edge.id" class="graph-edge">
          <strong>{{ edge.relation }}</strong>
          <span>{{ relationLine(edge.source, edge.target) }}</span>
          <small v-if="edge.evidence">{{ edge.evidence }}</small>
        </div>
      </div>

      <div v-if="graph.recommendations?.length" class="knowledge-analysis-summary">
        <strong>图谱完善建议</strong>
        <p v-for="item in graph.recommendations" :key="item">{{ item }}</p>
      </div>
    </article>

    <div v-else class="empty-hint">
      <span>完成检索后生成查询子图，或直接查看全局知识图谱，用于展示知识沉淀和 RAG 证据链。</span>
    </div>
  </section>
</template>
