import { NavLink, Outlet } from "react-router-dom"

import { cn } from "@/lib/utils"
import { Logo } from "@/components/logo"
import { QuietToggle } from "@/components/sympose"
import { useTheme } from "@/components/theme-provider"

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/components", label: "Components", end: false },
  { to: "/menu", label: "Main menu", end: false },
  { to: "/shell", label: "Shell", end: false },
]

export function RootLayout() {
  const { theme, setTheme } = useTheme()

  return (
    <div className="flex min-h-svh flex-col bg-background text-foreground">
      <header className="flex items-center justify-between gap-4 border-b border-border px-4 py-2.5">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-2 font-semibold">
            <Logo className="size-5" />
            Sympose
          </span>
          <nav className="flex items-center gap-1 text-sm">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "px-2 py-1 transition-colors",
                    isActive
                      ? "text-brand"
                      : "text-muted-foreground hover:text-foreground"
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <QuietToggle
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label="Toggle theme"
        >
          {theme === "dark" ? "🌙 dark" : "☀ light"}
        </QuietToggle>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  )
}
