/**
 * API 调用封装。
 * 统一管理后端接口调用，处理错误和状态码。
 */

const BASE = ''  // Vite proxy 处理跨域

export async function generateScript(params) {
  /** 首次调用：发起脚本生成 */
  const res = await fetch(`${BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || '请求失败')
  }
  return res.json()
}

export async function confirmAction(confirmReq) {
  /** 确认调用：继续/重新策划/修改大纲 */
  const res = await fetch(`${BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(confirmReq),
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || '请求失败')
  }
  return res.json()
}

export async function healthCheck() {
  const res = await fetch(`${BASE}/health`)
  return res.json()
}
