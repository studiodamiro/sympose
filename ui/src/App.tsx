import { createBrowserRouter, RouterProvider } from "react-router-dom"

import { Toaster } from "@/components/ui/sonner"
import { RootLayout } from "@/routes/root-layout"
import { DashboardPlaceholder } from "@/routes/dashboard-placeholder"
import { ComponentsGallery } from "@/routes/components-gallery"

const router = createBrowserRouter([
  {
    path: "/",
    element: <RootLayout />,
    children: [
      { index: true, element: <DashboardPlaceholder /> },
      { path: "components", element: <ComponentsGallery /> },
    ],
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
