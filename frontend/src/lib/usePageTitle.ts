import { useEffect } from 'react'

/**
 * Sets the browser tab title per page. A single-page app that never updates the title leaves
 * every tab, bookmark and back-button entry reading the same thing, which screen readers
 * announce on navigation too.
 */
export function usePageTitle(title: string): void {
  useEffect(() => {
    const previous = document.title
    document.title = `${title} · Civic Accountability`
    return () => {
      document.title = previous
    }
  }, [title])
}
