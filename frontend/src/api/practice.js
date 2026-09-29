import http from './http'

/**
 * 针对性训练 API
 * 1. weakPoints —— 我的薄弱题型与维度分析
 * 2. startCategorySession —— 针对薄弱题型开练一场
 * 3. lastSessionWeak —— 某场次里答得不好的题（一键再练）
 */
export const practiceApi = {
  weakPoints: () => http.get('/practice/weak-points'),
  startCategory: (payload) => http.post('/practice/start', payload),
  lastWeak: (sessionId, threshold = 70) =>
    http.get(`/practice/weak-questions/${sessionId}`, { params: { threshold } }),
}
