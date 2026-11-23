import { useCallback, useEffect, useState } from "react"

export type Theme = "light" | "dark"

// Keep in sync with the inline script in index.html.
const STORAGE_KEY = "theme"

function getInitialTheme(): Theme {
  // index.html applies the class before React mounts, so it is the source of truth.
  return document.documentElement.classList.contains("dark") ? "dark" : "light"
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme)

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark")
    document.documentElement.style.colorScheme = theme
  }, [theme])

  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === "dark" ? "light" : "dark"
      try {
        localStorage.setItem(STORAGE_KEY, next)
      } catch {
        // Storage unavailable (e.g. private mode); theme still applies for this visit.
      }
      return next
    })
  }, [])

  return { theme, toggleTheme }
}
