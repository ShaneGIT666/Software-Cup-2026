<script setup lang="ts">
import { Network } from "@lucide/vue";
import type { KnowledgeGraphPayload } from "../api";

defineProps<{
  graph: KnowledgeGraphPayload | null;
  loading: boolean;
}>();

const emit = defineEmits<{
  refresh: [];
}>();

function typeLabel(type: string) {
  const labels: Record<string, string> = {
    device: "设备",
    fault: "故障",
    manual: "手册",
    case: "案例",
    document: "资料",
    workflow: "流程",
    source: "来源",
    term: "术语",
    provider: "模型"
  };
  return labels[type] ?? type;
}
</script>

<template>
  <section class="knowledge-graph-panel">
    <div class="section-title">
      <Network :size="18" />
      <span>知识关系</span>
    </div>
    <p class="panel-note">基于当前检索结果生成轻量关系网络，展示设备、故障、资料、案例和作业流程之间的可追溯连接。</p>

    <div class="action-row">
      <el-button type="primary" plain :loading="loading" @click="emit('refresh')">
        <Network :size="16" />
        生成关系网络
      </el-button>
      <el-tag v-if="graph" type="info">{{ graph.nodes.length }} 节点 / {{ graph.edges.length }} 关系</el-tag>
    </div>

    <div v-if="loading" class="loading-hint processing-card">
      <span>正在组织知识关系...</span>
    </div>
    <article v-else-if="graph" class="graph-content">
      <p>{{ graph.summary }}</p>
      <div class="graph-node-list">
        <span v-for="node in graph.nodes.slice(0, 12)" :key="node.id" class="graph-node" :data-type="node.type">
          <small>{{ typeLabel(node.type) }}</small>
          {{ node.label }}
        </span>
      </div>
      <div class="graph-edge-list">
        <div v-for="edge in graph.edges.slice(0, 10)" :key="edge.id" class="graph-edge">
          <strong>{{ edge.relation }}</strong>
          <span>{{ graph.nodes.find((node) => node.id === edge.source)?.label ?? edge.source }} -> {{ graph.nodes.find((node) => node.id === edge.target)?.label ?? edge.target }}</span>
          <small v-if="edge.evidence">{{ edge.evidence }}</small>
        </div>
      </div>
    </article>
    <div v-else class="empty-hint">
      <span>完成检索后生成关系网络，用于展示知识沉淀和证据链。</span>
    </div>
  </section>
</template>
