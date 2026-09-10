import { lazy, Suspense } from "react"
import { createBrowserRouter, RouterProvider } from "react-router-dom"

import { Toaster } from "@/components/ui/sonner"
import { ConfirmHost } from "@/lib/confirm"
import { useNotificationPreferences } from "@/lib/use-notification-preferences"
import { RootLayout } from "@/routes/root-layout"
import { ComponentsGallery } from "@/routes/components-gallery"
import { MenuShowcase } from "@/routes/menu-showcase"
import { AppShell } from "@/routes/app-shell"

// Lazy — pulls in three.js / 3d-force-graph (~600 kB gzip). Kept out of the
// shared chunk so only /nebula (and, later, the shell's ambient layer) pays it.
const NebulaShowcase = lazy(() =>
  import("@/routes/nebula-showcase").then((m) => ({ default: m.NebulaShowcase }))
)

const router = createBrowserRouter([
  {
    // Pathless layout route — wraps /components and /menu in the dev-nav
    // chrome without owning "/" itself, so it can't collide with the
    // full-viewport AppShell route below.
    element: <RootLayout />,
    children: [
      { path: "components", element: <ComponentsGallery /> },
      { path: "menu", element: <MenuShowcase /> },
    ],
  },
  // Full-viewport, no RootLayout top nav — the shell has its own chrome.
  // "/shell" kept as an alias to the product root.
  { path: "/", element: <AppShell /> },
  { path: "/shell", element: <AppShell /> },
  {
    path: "/nebula",
    element: (
      <Suspense fallback={<div className="h-svh w-full bg-[#0b0d12]" />}>
        <NebulaShowcase />
      </Suspense>
    ),
  },
])

export function App() {
  const [notify] = useNotificationPreferences()
  return (
    <>
      <RouterProvider router={router} />
      <Toaster position={notify.position} />
      <ConfirmHost />
    </>
  )
}

export default App
