/**
 * 日期时间工具函数（纯前端）
 *
 * 设计原则：
 * - 不引入第三方日期库，避免体积膨胀；
 * - 只提供本项目页面用得到的最小集合；
 * - 输入尽量“宽容”，输出尽量“统一”（便于列表展示与 CSV 导出）。
 */

export function 补零两位(n: number): string {
  return String(n).padStart(2, "0");
}

export function 本地日期(输入?: Date): string {
  const d = 输入 ?? new Date();
  return `${d.getFullYear()}-${补零两位(d.getMonth() + 1)}-${补零两位(d.getDate())}`;
}

export function 本地日期时间(输入?: Date): string {
  const d = 输入 ?? new Date();
  return `${本地日期(d)} ${补零两位(d.getHours())}:${补零两位(d.getMinutes())}:${补零两位(d.getSeconds())}`;
}

/**
 * 将“可能来自后端/旧页面”的时间字符串格式化为标准展示格式。
 *
 * 支持的常见输入：
 * - "2025-11-12 14:30:00"
 * - "2025-11-12T14:30:00"
 * - "20251112143000"（旧页面批量删除使用的压缩格式）
 */
export function 格式化时间文本(v: unknown): string {
  if (v === null || v === undefined) return "";
  const s = String(v).trim();
  if (!s) return "";

  if (/^\d{14}$/.test(s)) {
    return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)} ${s.slice(8, 10)}:${s.slice(10, 12)}:${s.slice(12, 14)}`;
  }

  if (s.includes("T") && /^\d{4}-\d{2}-\d{2}T/.test(s)) {
    return s.replace("T", " ").split(".")[0];
  }

  return s;
}

/**
 * 将 date input（YYYY-MM-DD）转换为后端 records 的查询时间戳边界。
 */
export function 日期起始时间(ymd: string): string {
  const s = (ymd || "").trim();
  if (!s) return "";
  return `${s} 00:00:00`;
}

export function 日期结束时间(ymd: string): string {
  const s = (ymd || "").trim();
  if (!s) return "";
  return `${s} 23:59:59`;
}

