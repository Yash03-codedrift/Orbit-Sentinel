import { useEffect, useState } from 'react'
import { getActiveConjunctions, getConjunctionStats } from '../api/conjunctionApi.js'
import { useConjunctionStore } from '../store/useConjunctionStore.js'
import { useSystemStore } from '../store/useSystemStore.js'

export function useConjunctionFeed() {
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    // Access store actions directly (stable references, no selector churn)
    const setConjunctions = useConjunctionStore.getState().setConjunctions;
    const setActiveConjunctionCount = useSystemStore.getState().setActiveConjunctionCount;

    const fetchFeedAndStats = async () => {
      try {
        const [conjunctions, stats] = await Promise.all([
          getActiveConjunctions(),
          getConjunctionStats()
        ])
        
        if (active) {
          setConjunctions(conjunctions)
          if (stats) {
            if (stats.unresolved_total !== undefined) {
              setActiveConjunctionCount(stats.unresolved_total)
            } else if (conjunctions) {
              setActiveConjunctionCount(conjunctions.length)
            }
          } else if (conjunctions) {
            setActiveConjunctionCount(conjunctions.length)
          }
          setLoading(false)
        }
      } catch (err) {
        console.error('Failed to update conjunction feed data stream:', err)
        if (active) {
          setLoading(false)
        }
      }
    }

    fetchFeedAndStats()

    const intervalId = setInterval(fetchFeedAndStats, 60000)

    return () => {
      active = false
      clearInterval(intervalId)
    }
  }, [])

  return { loading }
}
