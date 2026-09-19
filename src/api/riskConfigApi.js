import { api } from './axios.js'

export const getRiskThresholds = () => api.get('/risk-config')
export const updateRiskBands = (bands) => api.put('/risk-config', { bands })