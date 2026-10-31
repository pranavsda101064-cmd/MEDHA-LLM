async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || JSON.stringify(body)
    } catch {
      /* keep statusText */
    }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  health: () => request('/api/health'),

  generate: (body) =>
    request('/api/lessons/generate', { method: 'POST', body: JSON.stringify(body) }),

  open: (body = {}) =>
    request('/api/lessons/open', { method: 'POST', body: JSON.stringify(body) }),

  session: (id) => request(`/api/sessions/${id}`),

  frame: (id, t) => request(`/api/sessions/${id}/frame?t=${Math.max(0, Math.round(t))}`),

  checkpoint: (id, t) =>
    request(`/api/sessions/${id}/checkpoint?t=${Math.max(0, Math.round(t))}`),

  resetCheckpoints: (id) =>
    request(`/api/sessions/${id}/reset-checkpoints`, { method: 'POST' }),

  seek: (id, t) =>
    request(`/api/sessions/${id}/seek?t=${Math.max(0, Math.round(t))}`, {
      method: 'POST',
    }),

  library: (params = {}) => {
    const qs = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
    })
    const suffix = qs.toString() ? `?${qs}` : ''
    return request(`/api/lessons${suffix}`)
  },

  favorite: (id, favorite = true) =>
    request(`/api/lessons/${id}/favorite?favorite=${favorite}`, { method: 'POST' }),
}
