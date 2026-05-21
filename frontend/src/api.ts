export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message: string;
}

export interface SearchResult {
  id: string;
  title: string;
  sourceType: "manual" | "case" | "document";
  sourceName: string;
  confidence: number;
  snippet: string;
  workflowId?: string;
  chapter?: string;
  page?: number;
  documentId?: string;
  chunkId?: string;
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
}

export interface KnowledgeDocument {
  id: string;
  fileName: string;
  fileType: string;
  suffix: string;
  sourceName: string;
  status: "indexed" | "needs_parser" | "needs_ocr" | "empty" | string;
  chunkCount: number;
  parser: string;
  uploadedAt: string;
  url: string;
  chunks?: KnowledgeChunkPreview[];
}

export interface KnowledgeDocumentListPayload {
  items: KnowledgeDocument[];
  total: number;
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

export interface RagCitation {
  id: string;
  title: string;
  sourceType: "manual" | "case" | "document";
  sourceName: string;
  snippet: string;
  confidence: number;
  page?: number | null;
  chapter?: string | null;
  documentId?: string;
  chunkId?: string;
  reason?: string;
  scoreBreakdown?: SearchScoreBreakdown;
}

export interface RagAnswerPayload {
  queryId: string;
  summary: string;
  answer: string;
  recommendedActions: string[];
  citations: RagCitation[];
  provider: string;
  requestedProvider: string;
  fallback: boolean;
  fallbackReason?: string;
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
