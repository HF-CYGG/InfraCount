/**
 * 浏览器端下载工具
 *
 * 场景：
 * - CSV 导出：前端拼好文本后，直接触发下载；
 * - 未来如需导出 JSON/日志，也可复用。
 */

export function 触发文本下载(opts: { filename: string; text: string; mime?: string }): void {
  const mime = opts.mime || "text/plain;charset=utf-8";
  const blob = new Blob([opts.text], { type: mime });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = opts.filename;
  a.style.display = "none";
  document.body.appendChild(a);
  a.click();

  requestAnimationFrame(() => {
    URL.revokeObjectURL(url);
    a.remove();
  });
}

