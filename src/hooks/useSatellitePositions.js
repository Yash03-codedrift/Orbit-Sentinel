import { useEffect, useState, useRef } from 'react'
import { getCurrentPositions } from '../api/tleApi.js'
import { useGlobeStore } from '../store/useGlobeStore.js'

export function useSatellitePositions() {
  const [loading, setLoading] = useState(true)
  const loadingRef = useRef(true)

  useEffect(() => {
    let active = true

    const fetchPositions = async () => {
      try {
        const positions = await getCurrentPositions()
        if (active) {
          // Access store directly — avoids store reference in dependency array
          useGlobeStore.getState().setSatellitePositions(positions)
          if (loadingRef.current) {
            loadingRef.current = false
            setLoading(false)
          }
        }
      } catch (err) {
        console.error('Failed to pull current propagated positions:', err)
        if (active && loadingRef.current) {
          loadingRef.current = false
          setLoading(false)
        }
      }
    }

    fetchPositions()

    // 60s is enough — SGP4 positions change slowly, no need for 30s hammering
    const intervalId = setInterval(fetchPositions, 60000)

    return () => {
      active = false
      clearInterval(intervalId)
    }
  }, []) // empty deps — runs once, stable forever

  return { loading }
}
