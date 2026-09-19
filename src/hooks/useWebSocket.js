import { useEffect, useRef } from 'react'
import { useSystemStore } from '../store/useSystemStore.js'
import { useConjunctionStore } from '../store/useConjunctionStore.js'
import { useManeuverStore } from '../store/useManeuverStore.js'

export function useWebSocket() {
  const socketRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const reconnectDelay = useRef(1000)
  const setWsConnected = useSystemStore(s => s.setWsConnected)
  
  function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`)
    socketRef.current = ws
    
    ws.onopen = () => { 
      setWsConnected(true)
      reconnectDelay.current = 1000 
    }
    
    ws.onclose = () => {
      setWsConnected(false)
      reconnectTimeoutRef.current = setTimeout(connect, reconnectDelay.current)
      reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000)
    }
    
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        
        // Dispatch global window event for modular component reactive receivers
        window.dispatchEvent(new CustomEvent('ws_message', { detail: msg }));
        
        if (msg.type === 'conjunction_update') {
          if (msg.newly_added > 0) {
            useConjunctionStore.getState().setConjunctions(msg.conjunctions)
          }
          if (msg.sweep_duration_s !== undefined) {
            useSystemStore.getState().setLastSweep(msg.sweep_duration_s, msg.satellites_scanned || 0)
          }
        }
        
        if (msg.type === 'maneuver_computed') { 
          useManeuverStore.getState().addManeuver(msg.maneuver) 
          if (msg.conjunction_event_id) {
            useConjunctionStore.getState().updateConjunction({
              event_id: msg.conjunction_event_id,
              resolved: true,
              maneuvered: true,
              maneuver_id: msg.maneuver.maneuver_id
            })
          }
        }
        
        if (msg.type === 'maneuver_verified') {
          const { activeManeuver } = useManeuverStore.getState()
          if (activeManeuver && activeManeuver.maneuver_id === msg.maneuver_id) {
            useManeuverStore.getState().setVerificationResult(msg.verification)
          }
        }
        
        if (msg.type === 'conjunction_resolved') {
          useConjunctionStore.getState().updateConjunction({
            event_id: msg.event_id,
            resolved: true,
            maneuver_id: msg.maneuver_id
          })
        }
        
        if (msg.type === 'system_stats') {
          useSystemStore.getState().setTotalObjects(msg.total_objects)
          useSystemStore.getState().setKesslerIndex(msg.kessler_index)
          if (msg.last_sweep_duration_s !== undefined) {
            useSystemStore.getState().setLastSweep(msg.last_sweep_duration_s, msg.last_sweep_satellite_count || 0)
          }
        }
        
        if (msg.type === 'initial_state') { 
          useConjunctionStore.getState().setConjunctions(msg.conjunctions) 
          if (msg.total !== undefined) {
            useSystemStore.getState().setActiveConjunctionCount(msg.total)
          }
        }
      } catch (err) {
        console.error('Failed to parse websocket message payload:', err)
      }
    }
    
    ws.onerror = () => ws.close()
    
    // Keepalive ping every 30s
    const pingInterval = setInterval(() => { 
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' })) 
      }
    }, 30000)
    ws._pingInterval = pingInterval
  }
  
  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimeoutRef.current)
      if (socketRef.current?._pingInterval) {
        clearInterval(socketRef.current._pingInterval)
      }
      if (socketRef.current) {
        socketRef.current.close()
      }
    }
  }, [])
}
