import { api } from './axios.js'

export const getRecentManeuvers = (limit = 20) => api.get('/maneuvers/recent', { params: { limit } })
export const getManeuverDetail = (id) => api.get(`/maneuvers/${id}`)
export const getWebhookPayload = (id) => api.get(`/maneuvers/${id}/webhook_payload`)
export const getVerificationResult = (id) => api.get(`/maneuvers/${id}/verification`)
