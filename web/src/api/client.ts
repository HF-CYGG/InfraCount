/**
 * 基础 API Client（基于 fetch）
 *
 * 目标：
 * - 封装统一的请求入口，减少重复代码；
 * - 默认开启 withCredentials（fetch 对应配置为 credentials: "include"），
 *   这样浏览器会自动携带后端写入的 session_token Cookie，实现登录态保持；
 * - 统一错误对象结构，便于页面做友好提示。
 *
 * 说明：
 * - 这里故意不引入 axios 等第三方库，保持依赖最小；
 * - 仅提供最常用的 JSON 请求能力：GET/POST/PUT/DELETE；
 * - 后续如果需要文件上传/下载，可在此基础上扩展。
 */

export type HttpMethod = "GET" | "POST" | "PUT" | "DELETE";

export type ApiRequestOptions = {
  method: HttpMethod;
  path: string;
  query?: Record<string, string | number | boolean | undefined | null>;
  body?: unknown;
  headers?: Record<string, string>;
};

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

function buildQueryString(query?: ApiRequestOptions["query"]): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null) continue;
    params.set(k, String(v));
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}

async function parseResponseBody(res: Response): Promise<unknown> {
  const contentType = (res.headers.get("content-type") || "").toLowerCase();
  if (contentType.includes("application/json")) {
    try {
      return await res.json();
    } catch {
      return null;
    }
  }
  try {
    return await res.text();
  } catch {
    return null;
  }
}

/**
 * 统一请求入口
 *
 * 实现逻辑：
 * 1) 拼接 query string；
 * 2) 以 JSON 形式发送 body（如果存在）；
 * 3) 强制携带 Cookie（credentials: "include"）；
 * 4) 统一解析响应内容；
 * 5) 非 2xx 时抛出 ApiError，调用方可据此展示中文错误信息。
 */
export async function apiRequest<T = unknown>(opts: ApiRequestOptions): Promise<T> {
  const url = `${opts.path}${buildQueryString(opts.query)}`;

  const headers: Record<string, string> = {
    Accept: "application/json",
    ...opts.headers
  };

  let body: BodyInit | undefined = undefined;
  if (opts.body !== undefined) {
    /**
     * body 处理规则（尽量让调用方“少想一点”）：
     * - FormData：用于文件上传，必须让浏览器自动生成 multipart boundary，
     *   因此不能手动设置 Content-Type。
     * - 其它：默认当作 JSON 发送，Content-Type=application/json。
     */
    if (opts.body instanceof FormData) {
      body = opts.body;
      delete headers["Content-Type"];
    } else {
      headers["Content-Type"] = headers["Content-Type"] || "application/json";
      body = headers["Content-Type"].includes("application/json") ? JSON.stringify(opts.body) : (opts.body as any);
    }
  }

  const res = await fetch(url, {
    method: opts.method,
    headers,
    body,
    credentials: "include"
  });

  const data = await parseResponseBody(res);

  if (!res.ok) {
    const msg = typeof data === "string" && data.trim() ? data : `请求失败（HTTP ${res.status}）`;
    throw new ApiError(msg, res.status, data);
  }

  return data as T;
}

/**
 * 业务 API 封装（按页面需要逐步补齐）
 *
 * 设计目标：
 * - 前端页面只关心“要什么数据、传什么参数”，不关心 fetch 细节；
 * - 所有路径与参数集中在一处，便于后续统一改动与查找；
 * - 返回值尽量带上类型标注，减少页面里到处写 any。
 */
export const api = {
  /**
   * --- 认证 ---
   */
  authLogin: (username: string, password: string) =>
    apiRequest<{ status: string; user: { id: number; username: string; role: string } }>({
      method: "POST",
      path: "/api/v1/auth/login",
      body: { username, password }
    }),
  authLogout: () => apiRequest<{ status: string }>({ method: "POST", path: "/api/v1/auth/logout" }),
  authMe: () => apiRequest<{ user: { id: number; username: string; role: string } }>({ method: "GET", path: "/api/v1/auth/me" }),
  authChangePassword: (newPassword: string) =>
    apiRequest<{ status: string }>({ method: "POST", path: "/api/v1/auth/password", body: { new_password: newPassword } }),

  /**
   * --- 系统 ---
   */
  systemStatus: () => apiRequest<Record<string, unknown>>({ method: "GET", path: "/api/v1/system/status" }),

  /**
   * --- 看板统计 ---
   */
  statsSummary: (uuid?: string) =>
    apiRequest<{ in: number; out: number; last_time: string | null }>({
      method: "GET",
      path: "/api/v1/stats/summary",
      query: { uuid }
    }),
  statsDaily: (params: { uuid?: string; start?: string; end?: string }) =>
    apiRequest<Array<{ date: string; in: number; out: number }>>({
      method: "GET",
      path: "/api/v1/stats/daily",
      query: params
    }),
  statsHourly: (params: { uuid?: string; date?: string }) =>
    apiRequest<Array<{ hour: string; in: number; out: number }>>({
      method: "GET",
      path: "/api/v1/stats/hourly",
      query: params
    }),

  /**
   * --- 设备 ---
   */
  devicesList: () => apiRequest<Array<{ uuid: string }>>({ method: "GET", path: "/api/v1/devices" }),
  deviceMapping: () => apiRequest<{ mapping: Record<string, { name?: string; category?: string }> }>({ method: "GET", path: "/api/v1/devices/mapping" }),
  adminRegistryList: () => apiRequest<Array<Record<string, unknown>>>({ method: "GET", path: "/api/v1/admin/registry" }),
  adminRegistryUpsert: (payload: { uuid: string; name?: string; category?: string }) =>
    apiRequest<{ status: string }>({ method: "POST", path: "/api/v1/admin/registry", body: payload }),

  /**
   * --- 书院/分类 ---
   */
  academiesList: () => apiRequest<Array<{ id: number; name: string; sort_order?: number }>>({ method: "GET", path: "/api/v1/academies" }),
  academyAdd: (name: string) => apiRequest<{ status: string }>({ method: "POST", path: "/api/v1/academies", body: { name } }),
  academyDelete: (id: number) => apiRequest<{ status: string }>({ method: "DELETE", path: `/api/v1/academies/${id}` }),
  academiesOrderUpdate: (orderIds: number[]) => apiRequest<{ status: string }>({ method: "PUT", path: "/api/v1/academies/order", body: orderIds }),

  /**
   * --- 历史记录（管理视图：带分页/总数）---
   */
  adminRecordsList: (params: {
    page: number;
    size: number;
    uuid?: string;
    start?: string;
    end?: string;
    warn?: number;
    rec_type?: number;
    btx_min?: number;
    btx_max?: number;
    order?: "asc" | "desc";
    sort_by?: "time" | "created_at";
  }) =>
    apiRequest<{ items: Array<Record<string, unknown>>; total: number }>({
      method: "GET",
      path: "/api/v1/admin/records",
      query: params as any
    }),

  /**
   * --- 告警 ---
   */
  alertsList: (params: { uuid?: string; limit?: number }) =>
    apiRequest<Array<Record<string, unknown>>>({ method: "GET", path: "/api/v1/alerts", query: params as any }),
  alertsAck: (alertId: number) => apiRequest<{ ok: boolean }>({ method: "POST", path: `/api/v1/alerts/${alertId}/ack` }),

  /**
   * --- 活动 ---
   */
  activityOptions: () =>
    apiRequest<{ locations: string[]; types: string[]; academies: string[]; weekdays: string[]; times: string[] }>({
      method: "GET",
      path: "/api/v1/activity/options"
    }),
  activityEvents: (params: {
    start_date?: string;
    end_date?: string;
    locations?: string;
    types?: string;
    academies?: string;
    weekdays?: string;
    start_times?: string;
    page?: number;
    page_size?: number;
  }) =>
    apiRequest<{ total: number; items: Array<Record<string, unknown>> }>({
      method: "GET",
      path: "/api/v1/activity/events",
      query: params as any
    }),
  activityAggregations: (params: {
    start_date?: string;
    end_date?: string;
    locations?: string;
    types?: string;
    academies?: string;
    weekdays?: string;
    start_times?: string;
  }) =>
    apiRequest<Record<string, unknown>>({
      method: "GET",
      path: "/api/v1/activity/aggregations",
      query: params as any
    }),
  activityUploadCsv: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return apiRequest<{ imported: number }>({ method: "POST", path: "/api/v1/activity/upload", body: fd });
  },
  activityImportExcel: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return apiRequest<{ count: number }>({ method: "POST", path: "/api/v1/activity/import-excel", body: fd });
  },
  walkinDates: (params: { uuid?: string; devices?: string }) =>
    apiRequest<{ dates: string[]; min_date: string | null; max_date: string | null }>({
      method: "GET",
      path: "/api/v1/activity/walkin/dates",
      query: params as any
    }),
  walkinPreviewDates: (payload: { devices: string[]; dates: string[] }) =>
    apiRequest<{ items: Array<Record<string, unknown>> }>({ method: "POST", path: "/api/v1/activity/walkin/preview-dates", body: payload }),
  walkinSync: (payload: { items: Array<Record<string, unknown>>; mode: "skip" | "overwrite" }) =>
    apiRequest<Record<string, unknown>>({ method: "POST", path: "/api/v1/activity/walkin/sync", body: payload }),

  /**
   * --- 场地标准库/纠错 ---
   */
  locationsMapping: () => apiRequest<{ mapping: Record<string, string> }>({ method: "GET", path: "/api/v1/locations/mapping" }),
  locationsMappingUpsert: (payload: { location: string; academy: string }) =>
    apiRequest<{ status: string }>({ method: "POST", path: "/api/v1/locations/mapping", body: payload }),
  locationsMappingDelete: (location: string) =>
    apiRequest<{ status: string }>({ method: "DELETE", path: "/api/v1/locations/mapping", query: { location } }),
  locationsAll: () => apiRequest<string[]>({ method: "GET", path: "/api/v1/locations/all" }),
  locationsCorrectionCandidates: (location: string) =>
    apiRequest<string[]>({ method: "GET", path: "/api/v1/locations/correction-candidates", query: { location } }),
  locationsCorrect: (payload: { location: string; academy: string; merge_locations: string[] }) =>
    apiRequest<{ count: number }>({ method: "POST", path: "/api/v1/locations/correct", body: payload }),
  locationsAutoCorrectScan: () =>
    apiRequest<{ high_confidence: Array<Record<string, unknown>>; manual_review: Array<Record<string, unknown>> }>({
      method: "POST",
      path: "/api/v1/locations/auto-correct-scan"
    }),
  locationsBatchCorrect: (payload: { corrections: Array<{ target: string; academy: string; sources: string[] }> }) =>
    apiRequest<{ count: number }>({ method: "POST", path: "/api/v1/locations/batch-correct", body: payload }),

  /**
   * --- 账户/用户管理（Admin）---
   */
  usersList: () => apiRequest<{ users: Array<{ id: number; username: string; role: string }> }>({ method: "GET", path: "/api/v1/users" }),
  userCreate: (payload: { username: string; password: string; role: string }) =>
    apiRequest<{ status: string }>({ method: "POST", path: "/api/v1/users", body: payload }),
  userUpdate: (userId: number, payload: { username?: string; password?: string; role?: string }) =>
    apiRequest<{ status: string }>({ method: "PUT", path: `/api/v1/users/${userId}`, body: payload }),
  userDelete: (userId: number) => apiRequest<{ status: string }>({ method: "DELETE", path: `/api/v1/users/${userId}` }),

  /**
   * --- 数据库合并导入（Admin）---
   */
  dbMergeUpload: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return apiRequest<{ import_id: string; filename: string; size_bytes: number; created_at: string }>({
      method: "POST",
      path: "/api/v1/admin/db-merge/upload",
      body: fd
    });
  },
  dbMergePreview: (payload: { import_id: string; merge_mode: "skip_existing" | "update_existing"; conflict_preference: "prefer_current_non_empty" | "prefer_import" }) =>
    apiRequest<Record<string, unknown>>({
      method: "POST",
      path: "/api/v1/admin/db-merge/preview",
      body: payload
    }),
  dbMergeExecute: (payload: { import_id: string; merge_mode: "skip_existing" | "update_existing"; conflict_preference: "prefer_current_non_empty" | "prefer_import" }) =>
    apiRequest<{ job_id: string }>({
      method: "POST",
      path: "/api/v1/admin/db-merge/execute",
      body: payload
    }),
  dbMergeStatus: (jobId: string) =>
    apiRequest<{ job: Record<string, unknown> }>({
      method: "GET",
      path: "/api/v1/admin/db-merge/status",
      query: { job_id: jobId }
    }),

  /**
   * --- 日志导入 ---
   */
  deviceLogPreview: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return apiRequest<{
      import_id: string;
      filename: string | null;
      detected_format: string;
      total_records: number;
      devices: Array<Record<string, unknown>>;
      sample: Array<Record<string, unknown>>;
    }>({ method: "POST", path: "/api/v1/admin/device-log/preview", body: fd });
  },
  deviceLogImportChunk: (payload: { import_id: string; offset: number; limit: number }) =>
    apiRequest<{ imported: number; offset: number; next_offset: number; total: number; done: boolean }>({
      method: "POST",
      path: "/api/v1/admin/device-log/import",
      body: payload
    })
};

