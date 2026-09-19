import { api } from './axios.js'

export const getAuditLog = (limit = 50, offset = 0) => api.get('/audit/log', { params: { limit, offset } })
