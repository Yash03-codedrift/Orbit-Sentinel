import { api } from './axios.js'

export const getTleStatus = () => api.get('/tle/status')
export const getCurrentPositions = () => api.get('/tle/positions/current')
export const getSatelliteOrbit = (noradId) => api.get(`/tle/object/${noradId}/orbit`)
export const triggerTleRefresh = () => api.post('/tle/refresh')
export const getTleObjects = (params) => api.get('/tle/objects', { params })
