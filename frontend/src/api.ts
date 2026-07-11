export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message: string;
}

export interface SearchResult {
  id: string;
  title: string;
  sourceId?: string;
  sourceType: "manual" | "case" | "document" | "document_asset";
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
  faultCode?: string;
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
  multimodalSignals?: string[];
  crossModalMatchedFields?: string[];
  crossModalMatchMode?: string;
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

export interface StatusCountMap {
  [status: string]: number;
}

export interface SystemChromaStatus {
  enabled: boolean;
  available: boolean;
  healthy: boolean;
  status: string;
  path: string;
  collectionCount?: number | null;
  reason?: string;
}

export interface SystemStatusPayload {
  generatedAt: string;
  knowledge: {
    deviceCount: number;
    manualCount: number;
    workflowCount: number;
    caseCount: number;
    documentCount: number;
    chunkCount: number;
    approvedChunkCount: number;
    retrievableSourceCount: number;
    pendingReviewCount: number;
    chunkStatusCounts: StatusCountMap;
    caseStatusCounts: StatusCountMap;
    documentStatusCounts: StatusCountMap;
    revisionCount: number;
    reviewEventCount?: number;
  };
  indexing: {
    latestIndexTime?: string | null;
    latestKnownIndexActivityAt?: string | null;
    unavailableReason?: string;
    chroma: SystemChromaStatus;
  };
  parsing: {
    mineru: {
      enabled: boolean;
      available: boolean;
      status: string;
      timeoutSeconds: number;
      fallbackEnabled: boolean;
    };
    latestTask?: {
      documentId: string;
      fileName: string;
      status: string;
      parser: string;
      parserFallback: boolean;
      parserFallbackReason?: string;
      uploadedAt?: string;
      analyzedAt?: string;
      chunkCount: number;
      pendingReviewCount: number;
    } | null;
    latestAsyncTask?: {
      taskId: string;
      type: string;
      status: string;
      fileName: string;
      sourceName: string;
      documentId?: string | null;
      createdAt?: string;
      startedAt?: string;
      completedAt?: string;
      error?: string;
    } | null;
    asyncTaskCount?: number;
    asyncTaskStatusCounts?: StatusCountMap;
    parserFallbackCount: number;
  };
  fallback: {
    enabled: boolean;
    parserFallbackCount: number;
    chromaFallbackEnabled: boolean;
    llmFallbackEnabled: boolean;
    ocrFallbackEnabled: boolean;
  };
  auth?: {
    mode: string;
    enabled: boolean;
    operatorConfigured: boolean;
    reviewerConfigured: boolean;
    adminConfigured: boolean;
  };
  warnings: string[];
}

export interface ProviderStatusPayload {
  remoteApiMode: "auto" | "off" | string;
  offlineFallback: boolean;
  llm: ProviderChannelStatus;
  multimodal: ProviderChannelStatus;
  embedding?: ProviderChannelStatus;
  ocr?: ProviderChannelStatus;
  reranker?: ProviderChannelStatus & {
    supported?: boolean;
    enabled?: boolean;
    fallbackProvider?: string;
  };
  system?: SystemStatusPayload;
}

function authHeaders(): Record<string, string> {
  const storageToken =
    typeof window !== "undefined" ? window.localStorage.getItem("softwareCupAuthToken")?.trim() : "";
  const envToken = (import.meta.env.VITE_API_AUTH_TOKEN as string | undefined)?.trim();
  const token = storageToken || envToken || "";
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const isFormData = options?.body instanceof FormData;
  const response = await fetch(path, {
    headers: isFormData
      ? {
          ...authHeaders(),
          ...options?.headers
        }
      : {
          "Content-Type": "application/json",
          ...authHeaders(),
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

export function searchKnowledge(deviceModel: string, faultText: string, maintenanceLevel?: string) {
  return request<SearchPayload>("/api/search", {
    method: "POST",
    body: JSON.stringify({
      deviceModel,
      faultText,
      maintenanceLevel: maintenanceLevel ?? "normal_repair",
      inputType: "text",
      topK: 5
    })
  });
}

export interface MultimodalDiagnosisPayload {
  multimodalSignals: MultimodalSignals;
  queryContext: {
    deviceModel: string;
    deviceType: string;
    faultText: string;
    maintenanceLevel: string;
    riskLevel: string;
    imageClues: string[];
    ocrText: string;
    fallbackUsed: boolean;
    clueType: "inputClue" | string;
    expandedFaultText: string;
    multimodalSignals?: MultimodalSignals;
  };
  imageAnalysis: {
    provider: string;
    summary: string;
    observations: string[];
    fallback: boolean;
    fallbackReason?: string;
    ocrProvider?: string;
    ocrFallback?: boolean;
  };
  results: RagCitation[];
  evidencePack: EvidencePack;
  answer: string;
  structuredAnswer?: StructuredRagOutput;
  citations: RagCitation[];
  provider: string;
  fallback: boolean;
  fallbackReason?: string;
  raw?: RagAnswerPayload;
}

export interface MultimodalSignals {
  ocrText: string;
  imageClues: string[];
  detectedComponents: string[];
  visualSymptoms: string[];
  matchedQueryTerms: string[];
  signalSource: string;
  fallback: boolean;
  matchMode: string;
  description: string;
}

export function requestMultimodalDiagnosis(payload: {
  deviceModel: string;
  deviceType?: string;
  faultText?: string;
  maintenanceLevel?: string;
  riskLevel?: string;
  topK?: number;
  image?: File | null;
}) {
  const formData = new FormData();
  formData.append("deviceModel", payload.deviceModel);
  formData.append("deviceType", payload.deviceType ?? "");
  formData.append("faultText", payload.faultText ?? "");
  formData.append("maintenanceLevel", payload.maintenanceLevel ?? "normal_repair");
  formData.append("riskLevel", payload.riskLevel ?? "medium");
  formData.append("topK", String(payload.topK ?? 5));
  if (payload.image) {
    formData.append("image", payload.image);
  }
  return request<MultimodalDiagnosisPayload>("/api/multimodal/diagnosis", {
    method: "POST",
    body: formData
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
  deviceType?: string;
  component?: string;
  faultCode?: string;
  faultText: string;
  cause: string;
  solution: string;
  result: string;
  riskLevel?: string;
  experienceSummary?: string;
  lessonsLearned?: string;
  maintenanceLevel?: string;
  workflowId?: string | null;
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
  deviceType?: string;
  component?: string;
  faultCode?: string;
  workflowId?: string | null;
  workflowSelectionReason?: string;
}

export interface CaseListPayload {
  items: CaseItem[];
  total: number;
}

export function fetchCases(status?: string) {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return request<CaseListPayload>(`/api/cases${query}`);
}

export function reviewCase(caseId: string, action: "approve" | "reject", reviewNote?: string, reviewer = "operator") {
  return request<{ id: string; status: string }>(`/api/cases/${caseId}/review`, {
    method: "PATCH",
    body: JSON.stringify({ action, reviewNote: reviewNote ?? "", reviewer })
  });
}

export interface ReviewItem {
  id: string;
  objectType: "case" | "knowledge_chunk" | string;
  objectId: string;
  status: string;
  title: string;
  sourceName: string;
  deviceModel?: string;
  content: string;
  summary?: string;
  createdAt?: string;
  reviewer?: string;
  reviewTime?: string;
  tags?: string[];
  caseId?: string;
  documentId?: string;
  chunkId?: string;
  fileName?: string;
  page?: number | null;
  section?: string;
}

export interface ReviewItemListPayload {
  items: ReviewItem[];
  total: number;
}

export function fetchReviewItems(status = "pending_review") {
  return request<ReviewItemListPayload>(`/api/review/items?status=${encodeURIComponent(status)}`);
}

export interface KnowledgeChunkPreview {
  id: string;
  chunk_id?: string;
  title: string;
  sourceName: string;
  sourceType?: string;
  source_type?: string;
  knowledge_type?: string;
  origin?: string;
  page?: number | null;
  section?: string | null;
  evidence_location?: {
    page?: number | null;
    section?: string | null;
    assetName?: string;
    assetPath?: string;
  };
  assetName?: string;
  assetPath?: string;
  snippet: string;
  content?: string;
  keywords?: string[];
  review_status?: "draft" | "pending_review" | "approved" | "rejected" | "deprecated" | "replaced" | string;
  reviewer?: string;
  review_time?: string;
  review_action?: string;
  review_reason?: string;
  replaced_by?: string;
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
  assetAnalysisStatus?: "queued" | "running" | "completed" | "failed" | "skipped" | string;
  assetAnalysisCount?: number;
  assetAnalysisFallbackCount?: number;
  assetAnalysisError?: string;
  assetAnalysisUpdatedAt?: string;
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

export interface KnowledgeParseTask {
  id: string;
  type: string;
  status: "queued" | "running" | "completed" | "failed" | string;
  fileName: string;
  fileType: string;
  suffix: string;
  sourceName: string;
  createdAt: string;
  updatedAt: string;
  documentId?: string | null;
  documentStatus?: string;
  chunkCount?: number;
  parser?: string;
  parserFallback?: boolean;
  parserFallbackReason?: string;
  startedAt?: string;
  completedAt?: string;
  error?: string;
  assetAnalysisStatus?: string;
  assetAnalysisCount?: number;
  assetAnalysisFallbackCount?: number;
  assetAnalysisError?: string;
}

export interface KnowledgeParseTaskListPayload {
  items: KnowledgeParseTask[];
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

export interface KnowledgeReviewEvent {
  id: string;
  objectType: string;
  objectId: string;
  documentId?: string;
  chunkId?: string;
  revisionId?: string;
  action: "approve" | "reject" | string;
  beforeStatus: string;
  afterStatus: string;
  reason: string;
  reviewer: string;
  reviewTime: string;
  before?: Record<string, unknown>;
  after?: Record<string, unknown>;
}

export interface KnowledgeChunkReviewPayload {
  document: KnowledgeDocument;
  chunk: KnowledgeChunkPreview;
  reviewEvent: KnowledgeReviewEvent;
}

export interface ReviewEventListPayload {
  items: KnowledgeReviewEvent[];
  total: number;
  limit: number;
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

export function uploadKnowledgeDocumentAsync(file: File, sourceName?: string) {
  const formData = new FormData();
  formData.append("file", file);
  if (sourceName?.trim()) {
    formData.append("source_name", sourceName.trim());
  }
  return request<KnowledgeParseTask>("/api/knowledge/documents/async", {
    method: "POST",
    body: formData
  });
}

export function fetchKnowledgeDocuments() {
  return request<KnowledgeDocumentListPayload>("/api/knowledge/documents");
}

export function fetchKnowledgeParseTasks(status?: string) {
  const search = status ? `?status=${encodeURIComponent(status)}` : "";
  return request<KnowledgeParseTaskListPayload>(`/api/knowledge/parse-tasks${search}`);
}

export function fetchKnowledgeParseTask(taskId: string) {
  return request<KnowledgeParseTask>(`/api/knowledge/parse-tasks/${taskId}`);
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

export function reviewKnowledgeChunk(
  documentId: string,
  chunkId: string,
  payload: {
    action: "approve" | "reject";
    reason?: string;
    reviewer?: string;
  }
) {
  return request<KnowledgeChunkReviewPayload>(`/api/knowledge/documents/${documentId}/chunks/${chunkId}/review`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function updateKnowledgeChunkStatus(
  documentId: string,
  chunkId: string,
  payload: {
    status: "draft" | "pending_review" | "approved" | "rejected" | "deprecated" | "replaced";
    reason?: string;
    reviewer?: string;
    replacementChunkId?: string | null;
  }
) {
  return request<KnowledgeChunkReviewPayload>(`/api/knowledge/documents/${documentId}/chunks/${chunkId}/status`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function fetchReviewEvents(filters: {
  objectType?: string;
  objectId?: string;
  action?: string;
  limit?: number;
} = {}) {
  const params = new URLSearchParams();
  if (filters.objectType) {
    params.set("object_type", filters.objectType);
  }
  if (filters.objectId) {
    params.set("object_id", filters.objectId);
  }
  if (filters.action) {
    params.set("action", filters.action);
  }
  if (filters.limit) {
    params.set("limit", String(filters.limit));
  }
  const query = params.toString();
  return request<ReviewEventListPayload>(`/api/review/events${query ? `?${query}` : ""}`);
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
  maintenanceLevel?: string;
  maintenanceLevelDescription?: string;
  preWorkPreparation?: string[];
  inspectionSteps: string[];
  repairSteps: string[];
  riskControls?: string[];
  complianceChecks?: string[];
  safetyWarnings: string[];
  acceptanceCriteria: string[];
  citations: EvidenceTrace[];
  uncertainInformation: string[];
  riskReviewRequired: boolean;
}

export interface CorrectiveRagDecision {
  enabled: boolean;
  action: "answer" | "answer_with_caution" | "needs_more_evidence" | string;
  qualityScore: number;
  evidenceCount: number;
  reasons: string[];
  missingFields: string[];
  suggestedQueries: string[];
  retryRecommended: boolean;
  manualReviewRequired: boolean;
}

export interface SafetyRuleFinding {
  ruleId: string;
  severity: "info" | "warning" | "high" | "critical" | string;
  title: string;
  message: string;
  matchedTerms: string[];
  requiredActions: string[];
  evidenceIds: string[];
}

export interface SafetyRuleReport {
  enabled: boolean;
  highestSeverity: "info" | "warning" | "high" | "critical" | string;
  manualReviewRequired: boolean;
  blocking: boolean;
  findings: SafetyRuleFinding[];
  checklist: string[];
}

export interface RagAnswerPayload {
  queryId: string;
  summary: string;
  answer: string;
  rawAnswer?: string;
  structuredAnswer?: StructuredRagOutput;
  evidencePack?: EvidencePack;
  correctiveRag?: CorrectiveRagDecision;
  safetyRules?: SafetyRuleReport;
  riskReviewRequired?: boolean;
  recommendedActions: string[];
  citations: RagCitation[];
  provider: string;
  requestedProvider: string;
  fallback: boolean;
  fallbackReason?: string;
  llmAnswerUsed?: boolean;
  llmAnswerMode?: string;
  llmAnswerPreservedAfterRules?: boolean;
  contextCount?: number;
  contextChars?: number;
  model?: string;
  apiStyle?: string;
  graphContext?: GraphContextPayload;
}

export function requestRagAnswer(deviceModel: string, faultText: string, provider?: string, maintenanceLevel?: string) {
  return request<RagAnswerPayload>("/api/rag/answer", {
    method: "POST",
    body: JSON.stringify({
      deviceModel,
      faultText,
      maintenanceLevel: maintenanceLevel ?? "normal_repair",
      topK: 5,
      ...(provider ? { provider } : {})
    })
  });
}

export interface RagFeedbackItem {
  id: string;
  deviceModel: string;
  faultText: string;
  maintenanceLevel: string;
  originalAnswer: string;
  correctedAnswer: string;
  labels: string[];
  reason: string;
  status: "pending_review" | "approved" | "rejected" | string;
  reviewer: string;
  reviewNote: string;
  createdAt: string;
  updatedAt: string;
  approvedAt: string;
}

export interface RagFeedbackListPayload {
  items: RagFeedbackItem[];
  total: number;
}

export function submitRagFeedback(payload: {
  deviceModel: string;
  faultText: string;
  maintenanceLevel: string;
  originalAnswer: string;
  correctedAnswer?: string;
  labels?: string[];
  reason?: string;
  reviewer?: string;
}) {
  return request<RagFeedbackItem>("/api/rag/feedback", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function fetchRagFeedback(status?: string) {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return request<RagFeedbackListPayload>(`/api/rag/feedback${query}`);
}

export function reviewRagFeedback(feedbackId: string, action: "approve" | "reject", reviewer = "operator", reviewNote = "") {
  return request<RagFeedbackItem>(`/api/rag/feedback/${feedbackId}/review`, {
    method: "PATCH",
    body: JSON.stringify({ action, reviewer, reviewNote })
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
  approvedOnly?: boolean;
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
