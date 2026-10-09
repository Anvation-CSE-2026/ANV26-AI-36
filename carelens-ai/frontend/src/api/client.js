export class ApiError extends Error {
  constructor(status, code, message, fields = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

let onUnauthorized = () => {};
export const setUnauthorizedHandler = (fn) => {
  onUnauthorized = fn;
};

async function request(method, path, body, { quiet401 = false } = {}) {
  let res;
  try {
    const isForm = body instanceof FormData; // browser sets the multipart boundary itself
    res = await fetch(`/api${path}`, {
      method,
      credentials: 'same-origin',
      headers: isForm ? { Accept: 'application/json' } : { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, 'network', "We couldn't reach the server. Check your connection and try again.");
  }
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON response */
  }
  if (!res.ok) {
    const e = data?.error;
    const err = new ApiError(
      res.status,
      e?.code ?? 'error',
      e?.message ?? 'Something went wrong. Please try again.',
      e?.fields ?? {},
    );
    if (res.status === 401 && !quiet401) onUnauthorized();
    throw err;
  }
  return data;
}

const j = (method, path, body) => request(method, path, body);

export const api = {
  me: () => request('GET', '/auth/me', undefined, { quiet401: true }),
  login: (login_identifier, password) =>
    request('POST', '/auth/login', { login_identifier, password }, { quiet401: true }),
  logout: () => request('POST', '/auth/logout', {}, { quiet401: true }),
  createFamily: (payload) => request('POST', '/families', payload, { quiet401: true }),
  family: () => j('GET', '/family'),
  member: (id) => j('GET', `/family/members/${id}`),
  addMember: (member) => j('POST', '/family/members', member),
  updateMember: (id, relationship) => j('PATCH', `/family/members/${id}`, { relationship }),
  updateProfile: (patch) => j('PATCH', '/me', patch),
  changePassword: (current_password, new_password) => j('POST', '/me/password', { current_password, new_password }),
  security: () => j('GET', '/me/security'),
  signOutEverywhere: () => j('POST', '/me/security/sign-out-everywhere', {}),
  dashboard: () => j('GET', '/me/dashboard'),
  // documents
  documents: () => j('GET', '/me/documents'),
  uploadDocument: (file) => {
    const form = new FormData();
    form.append('file', file);
    return request('POST', '/me/documents', form);
  },
  deleteDocument: (id) => j('DELETE', `/me/documents/${id}`),
  documentDetails: (id, language) => j('GET', `/me/documents/${id}/details${language ? `?language=${language}` : ''}`),
  documentText: (id) => j('GET', `/me/documents/${id}/text`),
  reprocessDocument: (id) => j('POST', `/me/documents/${id}/process`, {}),
  analyzeDocument: (id, language) => j('POST', `/me/documents/${id}/analyze`, { language }),
  documentFileUrl: (id) => `/api/me/documents/${id}/file`,
  sharedDocument: (id) => j('GET', `/shared/documents/${id}`),
  analyzeSharedDocument: (id) => j('POST', `/shared/documents/${id}/analyze`, {}),
  sharedDocumentFileUrl: (id) => `/api/shared/documents/${id}/file`,
  knowledge: () => j('GET', '/me/knowledge'),
  // health / emergency / diet
  health: () => j('GET', '/me/health'),
  saveHealth: (p) => j('PUT', '/me/health', p),
  addRecord: (r) => j('POST', '/me/health/records', r),
  deleteRecord: (id) => j('DELETE', `/me/health/records/${id}`),
  emergency: () => j('GET', '/me/emergency'),
  saveEmergencyNotes: (notes) => j('PUT', '/me/emergency', { notes }),
  addContact: (c) => j('POST', '/me/emergency/contacts', c),
  deleteContact: (id) => j('DELETE', `/me/emergency/contacts/${id}`),
  diet: () => j('GET', '/me/diet'),
  saveDietPrefs: (p) => j('PUT', '/me/diet/preferences', p),
  dietGuidance: () => j('POST', '/me/diet/guidance', {}),
  // medicines / reminders / timeline
  medicines: () => j('GET', '/me/medicines'),
  medicine: (id) => j('GET', `/me/medicines/${id}`),
  addMedicine: (m) => j('POST', '/me/medicines', m),
  updateMedicine: (id, patch) => j('PATCH', `/me/medicines/${id}`, patch),
  deleteMedicine: (id) => j('DELETE', `/me/medicines/${id}`),
  wellness: () => j('GET', '/me/wellness'),
  saveWellnessGoals: (goals) => j('PUT', '/me/wellness/goals', { goals }),
  generateWellness: () => j('POST', '/me/wellness/generate', {}),
  saveWellnessPlan: (plan) => j('PUT', '/me/wellness/plan', { plan }),
  deleteWellnessPlan: () => j('DELETE', '/me/wellness/plan'),
  reminders: () => j('GET', '/me/reminders'),
  addReminder: (r) => j('POST', '/me/reminders', r),
  updateReminder: (id, patch) => j('PATCH', `/me/reminders/${id}`, patch),
  deleteReminder: (id) => j('DELETE', `/me/reminders/${id}`),
  timeline: () => j('GET', '/me/timeline'),
  addEvent: (e) => j('POST', '/me/timeline/events', e),
  deleteEvent: (id) => j('DELETE', `/me/timeline/events/${id}`),
  // sharing
  sharing: () => j('GET', '/sharing'),
  share: (body) => j('POST', '/sharing', body),
  revoke: (id) => j('DELETE', `/sharing/${id}`),
  sharedHealth: (ownerId) => j('GET', `/shared/people/${ownerId}/health`),
  sharedEmergency: (ownerId) => j('GET', `/shared/people/${ownerId}/emergency`),
  sharedMedicines: (ownerId) => j('GET', `/shared/people/${ownerId}/medicines`),
  // assistant / search
  aiStatus: () => j('GET', '/ai/status'),
  aiSettings: () => j('GET', '/ai/settings'),
  saveAiSettings: (body) => j('PUT', '/ai/settings', body),
  removeAiSettings: () => j('DELETE', '/ai/settings'),
  testAi: () => j('POST', '/ai/test', {}),
  conversations: () => j('GET', '/ai/conversations'),
  conversation: (id) => j('GET', `/ai/conversations/${id}`),
  deleteConversation: (id) => j('DELETE', `/ai/conversations/${id}`),
  chat: (body) => j('POST', '/ai/chat', body),
  voiceReport: (body) => j('POST', '/ai/voice/report', body),
  search: (q, type) => j('GET', `/search?q=${encodeURIComponent(q)}${type ? `&type=${type}` : ''}`),
};
