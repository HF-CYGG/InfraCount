/**
 * CSV 生成与解析（轻量版）
 *
 * 说明：
 * - 为了避免引入第三方库，这里实现最常用的 CSV 导出；
 * - 仅处理 UTF-8 文本，导出时自动加 BOM（Excel 打开中文不乱码）；
 * - 解析（导入）由后端处理，因此这里只做导出。
 */

function 转义CSV字段(v: unknown): string {
  if (v === null || v === undefined) return "";
  const s = String(v);
  const mustQuote = /[",\n\r]/.test(s);
  const escaped = s.replace(/"/g, '""');
  return mustQuote ? `"${escaped}"` : escaped;
}

export function 生成CSV文本(opts: { headers: string[]; rows: Array<Array<unknown>>; withBom?: boolean }): string {
  const lines: string[] = [];
  lines.push(opts.headers.map(转义CSV字段).join(","));
  for (const row of opts.rows) {
    lines.push(row.map(转义CSV字段).join(","));
  }

  const text = lines.join("\r\n");
  if (opts.withBom === false) return text;
  return "\ufeff" + text;
}

