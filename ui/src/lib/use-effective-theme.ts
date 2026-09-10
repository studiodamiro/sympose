import * as React from "react"

/**
 * The light/dark mode actually in effect, read from the `dark` / `light` class
 * the `ThemeProvider` writes on `<html>`. Unlike `useTheme().theme` this
 * resolves `system` to a concrete value and follows an OS appearance change
 * live (via a `MutationObserver` on the root class list) without needing a
 * context re-render.
 *
 * Shared by the Settings light/dark pill and the ambient Knowledge Nebula
 * layer, both of which need the concrete mode to pick colours.
 */
export function useEffectiveTheme(): "dark" | "light" {
  const read = React.useCallback(
    () =>
      document.documentElement.classList.contains("dark") ? "dark" : "light",
    []
  )
  const [effective, setEffective] = React.useState<"dark" | "light">(read)

  React.useEffect(() => {
    const sync = () => setEffective(read())
    sync()
    const observer = new MutationObserver(sync)
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    })
    return () => observer.disconnect()
  }, [read])

  return effective
}
