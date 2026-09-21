import { createBrowserRouter, RouterProvider } from "react-router-dom"

import { Toaster } from "@/components/ui/sonner"
import { ConfirmHost } from "@/lib/confirm"
import { useNotificationPreferences } from "@/lib/use-notification-preferences"
import { AppShell } from "@/routes/app-shell"

const router = createBrowserRouter([
  // "/shell" kept as an alias to the product root.
  { path: "/", element: <AppShell /> },
  { path: "/shell", element: <AppShell /> },
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
