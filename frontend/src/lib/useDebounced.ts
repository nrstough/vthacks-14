import { useEffect, useState } from 'react'

// Holds a value still for `ms` after it stops changing. Used on the whole
// solve request: a single drag of the balance slider steps through dozens of
// values, and each one would otherwise be its own round trip.
//
// The slider's own displayed number is NOT debounced, so the thumb still
// tracks the pointer. Only the network call waits.
export function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setSettled(value), ms)
    return () => clearTimeout(id)
  }, [value, ms])
  return settled
}
