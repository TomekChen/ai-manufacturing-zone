/* ===== 数据请求封装（全站唯一实现，R1 去重） =====
   此前 readError 在 11 个组件里各复制一份；现统一从这里 import。
   API 形状与原 main.jsx 版本一致（含 HTML 错误页兜底）。 */
export const API_BASE = '/api';

export async function readError(res) {
  const text = await res.text();
  // 优先尝试解析 JSON 错误
  try {
    const json = JSON.parse(text);
    if (json.error) return json.error;
    if (json.message) return json.message;
  } catch {}
  // 如果返回的是 HTML，提取 <title> 或前段文本，避免显示整个 HTML
  if (text.trim().startsWith('<')) {
    const title = text.match(/<title>([^<]*)<\/title>/i);
    if (title) return title[1].trim();
    return `请求失败（HTTP ${res.status}）`;
  }
  return text || `请求失败（HTTP ${res.status}）`;
}

export async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function apiPost(path, body, token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { method: 'POST', headers, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function apiDelete(path, token) {
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { method: 'DELETE', headers });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function apiUpload(file, token) {
  const formData = new FormData();
  formData.append('file', file);
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}/admin/upload`, { method: 'POST', headers, body: formData });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}
