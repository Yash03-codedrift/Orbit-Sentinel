import { api } from './axios.js'

export const getActiveConjunctions = () => api.get('/conjunctions/active')
export const getConjunctionStats = () => api.get('/conjunctions/stats')
export const getConjunctionDetail = (eventId) => api.get(`/conjunctions/${eventId}`)
export const getConjunctionHistory = (days = 7) => api.get('/conjunctions/history', { params: { days } })
export const triggerResponse = (eventId) => api.post(`/conjunctions/${eventId}/trigger_response`)
export const searchConjunctions = (q, dateFrom, dateTo) => api.get('/conjunctions/search', {
  params: {
    q,
    date_from: dateFrom,
    date_to: dateTo
  }
})
export const getConjunctionTrajectory = (eventId, windowMinutes = 20, steps = 41) =>
  api.get(`/conjunctions/${eventId}/trajectory`, { params: { window_minutes: windowMinutes, steps } })
