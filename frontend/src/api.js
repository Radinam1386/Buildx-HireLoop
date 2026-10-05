const BASE = import.meta.env.VITE_API_URL || ''
export const getToken = () => localStorage.getItem('hl_token')
export const setSession = (token, user) => {
  localStorage.setItem('hl_token', token)
  localStorage.setItem('hl_user', JSON.stringify(user))
}
export const clearSession = () => {
  localStorage.removeItem('hl_token')
  localStorage.removeItem('hl_user')
}
export const getUser = () => {
  try { return JSON.parse(localStorage.getItem('hl_user')) } catch { return null }
}

export async function api(path, { method = 'GET', body } = {}) {
  let res
  try {
    res = await fetch(BASE + path, {
      method,
      headers: { 'Content-Type': 'application/json', ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw Object.assign(new Error('اتصال به سرور برقرار نشد. اینترنت را بررسی کن و دوباره امتحان کن.'), { status: 0 })
  }
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    if (res.status === 401 && getToken()) { clearSession(); location.href = '/auth' }
    const detail = typeof data?.detail === 'string' ? data.detail : 'مشکلی پیش آمد. دوباره امتحان کن.'
    throw Object.assign(new Error(detail), { status: res.status })
  }
  return data
}

export const fa = (n) => Number(n || 0).toLocaleString('fa-IR')
