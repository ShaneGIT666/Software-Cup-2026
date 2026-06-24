export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message: string;
}

export interface SearchResult {
  id: string;
  title: string;
  sourceId?: string;
  sourceType: "manual" | "case" | "document";
  sourceName: string;
  confidence: number;
  snippet: string;
  workflowId?: string;
  chapter?: string;
  section?: string | null;
  page?: number;
  documentId?: string;
  chunkId?: string;
  reviewStatus?: string;
  deviceType?: string;
  deviceModel?: string;
  component?: string;
  faultType?: string;
  matchedTerms?: string[];
  reason?: string;
  scoreBreakdown?: SearchScoreBreakdown;
}

export interface SearchFieldMatch {
  field: string;
  terms: string[];
  weight: number;
  score: number;
}

export interface SearchScoreBreakdown {
  score: number;
  sourceType: SearchResult["sourceType"];
  sourceWeight: number;
  phraseBonus: number;
  fieldMatches: SearchFieldMatch[];
  vectorDistance?: number;
  embeddingProvider?: "hash" | "openai" | string;
  version?: string | number | null;
  riskLevel?: "low" | "medium" | "high" | "critical" | string;
}

export interface SearchPayload {
  queryId: string;
  summary: string;
  results: SearchResult[];
}

export interface WorkflowStep {
  order: number;
  title: string;
  description: string;
  checkRequired: boolean;
  warning: string;
}

export interface WorkflowPayload {
  id: string;
  title: string;
  deviceType: string;
  faultType: string;
  level: string;
  tools: string[];
  safetyNotes: string[];
  steps: WorkflowStep[];
  acceptanceCriteria: string[];
}

export interface ProviderChannelStatus {
  provider: string;
  remoteCapable: boolean;
  keyConfigured: boolean;
  effectiveProvider: string;
  lastFallbackReason: string;
  available?: boolean;
  localCapable?: boolean;
  vectorStore?: string;
  model?: string;
  apiStyle?: string;
}

export interface ProviderStatusPayload {
  remoteApiMode: "auto" | "off" | string;
  offlineFallback: boolean;
  llm: ProviderChannelStatus;
  multimodal: ProviderChannelStatus;
  embedding?: ProviderChannelStatus;
  ocr?: ProviderChannelStatus;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const isFormData = options?.body instanceof FormData;
  const response = await fetch(path, {
    headers: isFormData
      ? options?.headers
      : {
          "Content-Type": "application/json",
          ...options?.headers
        },
    ...options
  });
  const payload = (await response.json()) as ApiResponse<T>;
  if (!response.ok || !payload.success) {
    throw new Error(payload.message || "请求失败");
  }
  return payload.data;
}

export function searchKnowledge(deviceModel: string, faultText: string) {
  return request<SearchPayload>("/api/search", {
    method: "POST",
    body: JSON.stringify({
      deviceModel,
      faultText,
      inputType: "text",
      topK: 5
    })
  });
}

export function fetchWorkflow(workflowId: string) {
  return request<WorkflowPayload>(`/api/workflows/${workflowId}`);
}

export function fetchProviderStatus() {
  return request<ProviderStatusPayload>("/api/providers/status");
}

export function submitCase(payload: {
  deviceModel: string;
  faultText: string;
  cause: string;
  solution: string;
  result: string;
  tags: string[];
}) {
  return request<{ id: string; status: string }>("/api/cases", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export interface UploadPayload {
  id: string;
  fileName: string;
  fileType: string;
  url: string;
}

export function uploadFaultFile(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return request<UploadPayload>("/api/uploads", {
    method: "POST",
    body: formData
  });
}

export interface CaseItem {
  id: string;
  deviceModel: string;
  faultTitle: string;
  faultText: string;
  status: string;
  tags: string[];
  createdAt: string;
  solution?: string;
  cause?: string;
  result?: string;
}

export interface CaseListPayload {
  items: CaseItem[];
  total: number;
}

export function fetchCases(status?: string) {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return request<CaseListPayload>(`/api/cases${query}`);
}

export function reviewCase(caseId: string, action: "approve" | "reject", reviewNote?: string) {
  return request<{ id: string; status: string }>(`/api/cases/${caseId}/review`, {
    method: "PATCH",
    body: JSON.stringify({ action, reviewNote: reviewNote ?? "" })
  });
}

export interface KnowledgeChunkPreview {
  id: string;
  title: string;
  sourceName: string;
  page?: number | null;
  snippet: string;
  content?: string;
  keywords?: string[];
  manuallyCorrected?: boolean;
  updatedAt?: string;
  revisionTags?: string[];
}

export interface KnowledgeRevision {
  id: string;
  documentId: string;
  chunkId: string;
  source: string;
  status: string;
  reason: string;
  reviewer: string;
  createdAt: string;
  before: {
    title: string;
    sourceName: string;
    page?: number | null;
    content: string;
    keywords?: string[];
  };
  after: {
    title: string;
    sourceName: string;
    page?: number | null;
    content: string;
    keywords?: string[];
    tags?: string[];
  };
}

export interface KnowledgeDocument {
  id: string;
  fileName: string;
  fileType: string;
  suffix: string;
  sourceName: string;
  status:
    | "indexed"
    | "pending_review"
    | "needs_parser"
    | "needs_ocr"
    | "needs_multimodal_analysis"
    | "analyzing"
    | "analyzed"
    | "empty"
    | string;
  chunkCount: number;
  pendingReviewCount?: number;
  parser: string;
  parserFallback?: boolean;
  parserFallbackReason?: string;
  parseArtifacts?: {
    rawParseResult: string;
    parsedMarkdown: string;
    assetsDir: string;
  };
  uploadedAt: string;
  url: string;
  revisionCount?: number;
  latestRevisionAt?: string;
  latestRevision?: KnowledgeRevision | null;
  chunks?: KnowledgeChunkPreview[];
  analysis?: {
    summary: string;
    keyComponents: string[];
    faultSymptoms: string[];
    inspectionSteps: string[];
    safetyNotes: string[];
    provider: string;
    requestedProvider: string;
    fallback: boolean;
    fallbackReason?: string;
    ocr?: {
      provider?: string;
      requestedProvider?: string;
      fallback?: boolean;
      fallbackReason?: string;
      text?: string;
      confidence?: number | null;
    };
    analyzedAt?: string;
  };
}

export interface KnowledgeDocumentListPayload {
  items: KnowledgeDocument[];
  total: number;
}

export interface KnowledgeChunkListPayload {
  items: KnowledgeChunkPreview[];
  total: number;
}

export interface KnowledgeRevisionListPayload {
  items: KnowledgeRevision[];
  total: number;
}

export interface KnowledgeRevisionPayload {
  document: KnowledgeDocument;
  chunk: KnowledgeChunkPreview;
  revision: KnowledgeRevision;
}

export function uploadKnowledgeDocument(file: File, sourceName?: string) {
  const formData = new FormData();
  formData.append("file", file);
  if (sourceName?.trim()) {
    formData.append("source_name", sourceName.trim());
  }
  return request<KnowledgeDocument>("/api/knowledge/documents", {
    method: "POST",
    body: formData
  });
}

export function fetchKnowledgeDocuments() {
  return request<KnowledgeDocumentListPayload>("/api/knowledge/documents");
}

export function fetchKnowledgeDocumentChunks(documentId: string) {
  return request<KnowledgeChunkListPayload>(`/api/knowledge/documents/${documentId}/chunks`);
}

export function fetchKnowledgeDocumentRevisions(documentId: string) {
  return request<KnowledgeRevisionListPayload>(`/api/knowledge/documents/${documentId}/revisions`);
}

export function reviseKnowledgeChunk(
  documentId: string,
  chunkId: string,
  payload: {
    content: string;
    title?: string;
    sourceName?: string;
    page?: number | null;
    tags?: string[];
    reason?: string;
    reviewer?: string;
  }
) {
  return request<KnowledgeRevisionPayload>(`/api/knowledge/documents/${documentId}/chunks/${chunkId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function analyzeKnowledgeDocument(documentId: string, provider?: "mock" | "openai" | "anthropic" | "local") {
  return request<KnowledgeDocument>(`/api/knowledge/documents/${documentId}/analyze`, {
    method: "POST",
    body: JSON.stringify(provider ? { provider } : {})
  });
}

export interface RagCitation {
  id: string;
  title: string;
  sourceId?: string;
  sourceDocId?: string;
  sourceType: "manual" | "case" | "document";
  sourceName: string;
  snippet: string;
  confidence: number;
  page?: number | null;
  section?: string | null;
  chapter?: string | null;
  documentId?: string;
  chunkId?: string;
  reviewStatus?: string;
  riskLevel?: string | null;
  reason?: string;
  scoreBreakdown?: SearchScoreBreakdown;
}

export interface EvidenceTrace {
  evidenceId: string;
  chunkId?: string | null;
  sourceDocId?: string | null;
  page?: number | null;
  section?: string | null;
}

export interface EvidenceItem {
  evidenceId: string;
  resultId: string;
  title: string;
  sourceType: "manual" | "case" | "document" | string;
  sourceName: string;
  sourceDocId?: string | null;
  documentId?: string | null;
  chunkId?: string | null;
  version?: string | number | null;
  page?: number | null;
  section?: string | null;
  chapter?: string | null;
  snippet: string;
  reason: string;
  confidence: number;
  reviewStatus: string;
  riskLevel: string;
  score?: number | null;
  trace: EvidenceTrace;
}

export interface EvidencePack {
  evidenceCount: number;
  items: EvidenceItem[];
  citationTrace: EvidenceTrace[];
  sourceDocIds: string[];
  approvedOnly: boolean;
  riskReviewRequired: boolean;
  uncertaintyReasons: string[];
}

export interface StructuredRagOutput {
  preliminaryJudgment: string;
  inspectionSteps: string[];
  repairSteps: string[];
  safetyWarnings: string[];
  acceptanceCriteria: string[];
  citations: EvidenceTrace[];
  uncertainInformation: string[];
  riskReviewRequired: boolean;
}

export interface RagAnswerPayload {
  queryId: string;
  summary: string;
  answer: string;
  rawAnswer?: string;
  structuredAnswer?: StructuredRagOutput;
  evidencePack?: EvidencePack;
  riskReviewRequired?: boolean;
  recommendedActions: string[];
  citations: RagCitation[];
  provider: string;
  requestedProvider: string;
  fallback: boolean;
  fallbackReason?: string;
  contextCount?: number;
  contextChars?: number;
  model?: string;
  apiStyle?: string;
  graphContext?: GraphContextPayload;
}

export function requestRagAnswer(deviceModel: string, faultText: string, provider?: string) {
  return request<RagAnswerPayload>("/api/rag/answer", {
    method: "POST",
    body: JSON.stringify({
      deviceModel,
      faultText,
      topK: 5,
      ...(provider ? { provider } : {})
    })
  });
}

export interface KnowledgeGraphNode {
  id: string;
  label: string;
  type: "device" | "fault" | "manual" | "case" | "document" | "workflow" | "source" | "term" | "provider" | "chunk" | string;
  weight: number;
  properties?: Record<string, unknown>;
}

export interface KnowledgeGraphEdge {
  id: string;
  source: string;
  target: string;
  relation: string;
  evidence: string;
  confidence?: number;
}

export interface GraphContextPath {
  source: string;
  sourceType: string;
  relation: string;
  target: string;
  targetType: string;
  evidence: string;
  confidence: number;
}

export interface GraphContextPayload {
  enabled: boolean;
  summary: string;
  nodeCount: number;
  edgeCount: number;
  paths: GraphContextPath[];
}

export interface KnowledgeGraphPayload {
  mode?: "query" | "global" | string;
  queryId: string;
  summary: string;
  generatedAt?: string;
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
  stats?: {
    nodeCount: number;
    edgeCount: number;
    nodeTypes: Record<string, number>;
    relationTypes: Record<string, number>;
  };
  focusNodeIds?: string[];
  recommendations?: string[];
  cacheHit?: boolean;
}

export function fetchKnowledgeGraph(deviceModel: string, faultText: string) {
  return request<KnowledgeGraphPayload>("/api/knowledge/graph", {
    method: "POST",
    body: JSON.stringify({
      deviceModel,
      faultText,
      inputType: "text",
      topK: 6
    })
  });
}

export function fetchKnowledgeGraphOverview() {
  return request<KnowledgeGraphPayload>("/api/knowledge/graph");
}

export function rebuildKnowledgeGraph() {
  return request<KnowledgeGraphPayload>("/api/knowledge/graph/rebuild", {
    method: "POST",
    body: JSON.stringify({})
  });
}
