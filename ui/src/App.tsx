import { lazy, Suspense } from "react"
import { createBrowserRouter, RouterProvider } from "react-router-dom"

import { Toaster } from "@/components/ui/sonner"
import { RootLayout } from "@/routes/root-layout"
import { DashboardPlaceholder } from "@/routes/dashboard-placeholder"
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
    path: "/",
    element: <RootLayout />,
    children: [
      { index: true, element: <DashboardPlaceholder /> },
      { path: "components", element: <ComponentsGallery /> },
      { path: "menu", element: <MenuShowcase /> },
    ],
  },
  // Full-viewport demos — rendered without the RootLayout top nav.
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
  return (
    <>
      <RouterProvider router={router} />
      <Toaster />
    </>
  )
}

export default App
