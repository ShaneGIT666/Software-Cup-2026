export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message: string;
}

export interface SearchResult {
  id: string;
  title: string;
  sourceType: "manual" | "case";
  sourceName: string;
  confidence: number;
  snippet: string;
  workflowId?: string;
  chapter?: string;
  page?: number;
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
  const response = await fetch(path, {
    headers: {
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
