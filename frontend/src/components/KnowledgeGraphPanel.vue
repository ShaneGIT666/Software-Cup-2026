<script setup lang="ts">
import { computed, ref } from "vue";
import { Network } from "@lucide/vue";
import type { KnowledgeGraphEdge, KnowledgeGraphNode, KnowledgeGraphPayload } from "../api";

const props = defineProps<{
  graph: KnowledgeGraphPayload | null;
  loading: boolean;
}>();

const emit = defineEmits<{
  refresh: [];
  overview: [];
  rebuild: [];
}>();

const selectedNodeId = ref("");

const nodeLookup = computed(() => {
  const lookup = new Map<string, KnowledgeGraphNode>();
  for (const node of props.graph?.nodes ?? []) {
    lookup.set(node.id, node);
  }
  return lookup;
});

const typeLabels: Record<string, string> = {
  device: "设备",
  fault: "故障",
  manual: "手册",
  document: "资料",
  chunk: "资料片段",
  case: "案例",
  workflow: "流程",
  source: "模型分析来源",
  term: "术语",
  provider: "模型分析来源",
  rag_feedback: "回答修正"
};

const legendItems = [
  { type: "device", label: "设备" },
  { type: "fault", label: "故障" },
  { type: "manual", label: "手册" },
  { type: "document", label: "资料" },
  { type: "case", label: "案例" },
  { type: "workflow", label: "流程" },
  { type: "rag_feedback", label: "回答修正" },
  { type: "term", label: "术语" },
  { type: "provider", label: "模型分析来源" }
];

function typeLabel(type: string) {
  return typeLabels[type] ?? type;
}

function typeCount(type: string) {
  const stats = props.graph?.stats?.nodeTypes;
  if (stats && typeof stats[type] === "number") {
    return stats[type];
  }
  return (props.graph?.nodes ?? []).filter((node) => node.type === type).length;
}

function relationCount() {
  return props.graph?.stats?.edgeCount ?? props.graph?.edges.length ?? 0;
}

const summaryItems = computed(() => [
  { label: "节点总数", value: props.graph?.stats?.nodeCount ?? props.graph?.nodes.length ?? 0 },
  { label: "关系总数", value: relationCount() },
  { label: "设备数", value: typeCount("device") },
  { label: "故障数", value: typeCount("fault") },
  { label: "资料数", value: typeCount("document") + typeCount("manual") + typeCount("chunk") },
  { label: "案例数", value: typeCount("case") },
  { label: "流程数", value: typeCount("workflow") },
  { label: "回答修正数", value: typeCount("rag_feedback") }
]);

function groupForType(type: string) {
  if (type === "device" || type === "fault") {
    return "left";
  }
  if (["manual", "document", "chunk", "case", "rag_feedback"].includes(type)) {
    return "middle";
  }
  return "right";
}

const displayNodes = computed(() => {
  const nodes = [...(props.graph?.nodes ?? [])]
    .sort((a, b) => (b.weight ?? 0) - (a.weight ?? 0))
    .slice(0, 24);
  const groups = {
    left: nodes.filter((node) => groupForType(node.type) === "left"),
    middle: nodes.filter((node) => groupForType(node.type) === "middle"),
    right: nodes.filter((node) => groupForType(node.type) === "right")
  };
  const xMap = { left: 150, middle: 480, right: 810 };
  const placed = new Map<string, KnowledgeGraphNode & { x: number; y: number }>();
  (Object.keys(groups) as Array<keyof typeof groups>).forEach((groupKey) => {
    const groupNodes = groups[groupKey];
    const gap = groupNodes.length > 1 ? 270 / (groupNodes.length - 1) : 0;
    groupNodes.forEach((node, index) => {
      placed.set(node.id, {
        ...node,
        x: xMap[groupKey],
        y: groupNodes.length === 1 ? 180 : 45 + gap * index
      });
    });
  });
  return [...placed.values()];
});

const displayNodeIds = computed(() => new Set(displayNodes.value.map((node) => node.id)));

const displayEdges = computed(() =>
  (props.graph?.edges ?? [])
    .filter((edge) => displayNodeIds.value.has(edge.source) && displayNodeIds.value.has(edge.target))
    .slice(0, 40)
);

const selectedNode = computed(() => {
  const id = selectedNodeId.value || displayNodes.value[0]?.id || "";
  return displayNodes.value.find((node) => node.id === id) ?? null;
});

const relatedEdges = computed(() => {
  const node = selectedNode.value;
  if (!node) {
    return [];
  }
  return (props.graph?.edges ?? []).filter((edge) => edge.source === node.id || edge.target === node.id).slice(0, 12);
});

const typicalPaths = [
  "设备 → 故障 → 参考资料 → 检修建议",
  "故障 → 案例经验 → 处理方法",
  "回答修正 → 审核通过 → 知识关系图",
  "资料片段 → 审核通过 → 参考依据"
];

function relationLine(edge: KnowledgeGraphEdge) {
  const source = nodeLookup.value.get(edge.source)?.label ?? edge.source;
  const target = nodeLookup.value.get(edge.target)?.label ?? edge.target;
  return `${source} → ${target}`;
}

function edgePath(edge: KnowledgeGraphEdge) {
  const source = displayNodes.value.find((node) => node.id === edge.source);
  const target = displayNodes.value.find((node) => node.id === edge.target);
  if (!source || !target) {
    return "";
  }
  const midX = (source.x + target.x) / 2;
  return `M ${source.x} ${source.y} C ${midX} ${source.y}, ${midX} ${target.y}, ${target.x} ${target.y}`;
}

function isRelated(nodeId: string) {
  const selected = selectedNode.value;
  if (!selected) {
    return false;
  }
  return (
    selected.id === nodeId ||
    relatedEdges.value.some((edge) => edge.source === nodeId || edge.target === nodeId)
  );
}

function propertyEntries(node: KnowledgeGraphNode | null) {
  return Object.entries(node?.properties ?? {}).slice(0, 8);
}

function formatProperty(value: unknown) {
  if (Array.isArray(value)) {
    return value.join("、");
  }
  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value ?? "");
}
</script>

<template>
  <section class="knowledge-graph-panel">
    <div class="section-title">
      <Network :size="18" />
      <span>知识关系图</span>
    </div>
    <p class="panel-note">
      当前知识关系图仅展示已审核通过的资料、案例和回答修正；待审核和拒绝内容不会进入正式知识关系图。
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
      <span>正在组织知识关系图...</span>
    </div>

    <article v-else-if="graph" class="graph-content">
      <p>{{ graph.summary }}</p>

      <div class="graph-summary-grid">
        <div v-for="item in summaryItems" :key="item.label">
          <strong>{{ item.value }}</strong>
          <span>{{ item.label }}</span>
        </div>
      </div>

      <div class="graph-legend" aria-label="知识关系图图例">
        <span v-for="item in legendItems" :key="item.type">
          <i :class="`node-dot type-${item.type}`"></i>
          {{ item.label }}
        </span>
      </div>

      <p v-if="graph.nodes.length > displayNodes.length" class="graph-limit-note">
        当前仅展示重要节点，完整关系见下方列表。
      </p>

      <div class="graph-visual-shell">
        <svg class="graph-visual" viewBox="0 0 960 360" role="img" aria-label="轻量知识关系图">
          <path
            v-for="edge in displayEdges"
            :key="edge.id"
            class="graph-visual-edge"
            :class="{ active: relatedEdges.some((item) => item.id === edge.id) }"
            :d="edgePath(edge)"
          />
          <g
            v-for="node in displayNodes"
            :key="node.id"
            class="graph-visual-node"
            :class="[`type-${node.type}`, { active: selectedNode?.id === node.id, related: isRelated(node.id) }]"
            tabindex="0"
            @click="selectedNodeId = node.id"
            @keyup.enter="selectedNodeId = node.id"
          >
            <rect :x="node.x - 84" :y="node.y - 18" width="168" height="36" rx="8" />
            <circle :cx="node.x - 68" :cy="node.y" r="5" />
            <text :x="node.x - 56" :y="node.y + 4">{{ node.label.slice(0, 12) }}</text>
          </g>
        </svg>

        <aside class="graph-detail-panel">
          <template v-if="selectedNode">
            <span>{{ typeLabel(selectedNode.type) }}</span>
            <strong>{{ selectedNode.label }}</strong>
            <small>权重：{{ selectedNode.weight ?? 0 }}</small>
            <dl v-if="propertyEntries(selectedNode).length">
              <template v-for="[key, value] in propertyEntries(selectedNode)" :key="key">
                <dt>{{ key }}</dt>
                <dd>{{ formatProperty(value) }}</dd>
              </template>
            </dl>
            <div v-if="relatedEdges.length" class="graph-related-list">
              <b>相关关系</b>
              <small v-for="edge in relatedEdges" :key="edge.id">{{ edge.relation }}：{{ relationLine(edge) }}</small>
            </div>
          </template>
          <div v-else class="empty-hint">
            <span>点击图中的节点查看详情。</span>
          </div>
        </aside>
      </div>

      <section class="graph-paths">
        <strong>典型关系路径</strong>
        <div>
          <span v-for="path in typicalPaths" :key="path">{{ path }}</span>
        </div>
      </section>

      <div v-if="graph.recommendations?.length" class="knowledge-analysis-summary">
        <strong>图谱完善建议</strong>
        <p v-for="item in graph.recommendations" :key="item">{{ item }}</p>
      </div>

      <details class="graph-details">
        <summary>查看详细节点和关系</summary>
        <div class="graph-node-list">
          <span v-for="node in graph.nodes" :key="node.id" class="graph-node" :data-type="node.type">
            <small>{{ typeLabel(node.type) }}</small>
            {{ node.label }}
          </span>
        </div>
        <div class="graph-edge-list">
          <div v-for="edge in graph.edges" :key="edge.id" class="graph-edge">
            <strong>{{ edge.relation }}</strong>
            <span>{{ relationLine(edge) }}</span>
            <small v-if="edge.evidence">{{ edge.evidence }}</small>
          </div>
        </div>
      </details>
    </article>

    <div v-else class="empty-hint">
      <span>暂无知识关系图。请先在管理中心上传资料、审核案例或生成回答修正。</span>
    </div>
  </section>
</template>
