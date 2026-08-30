import { createBrowserRouter, RouterProvider } from "react-router-dom"

import { Toaster } from "@/components/ui/sonner"
import { RootLayout } from "@/routes/root-layout"
import { DashboardPlaceholder } from "@/routes/dashboard-placeholder"
import { ComponentsGallery } from "@/routes/components-gallery"
import { MenuShowcase } from "@/routes/menu-showcase"
import { AppShell } from "@/routes/app-shell"

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
  // Full-viewport shell demo — rendered without the RootLayout top nav.
  { path: "/shell", element: <AppShell /> },
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
