import { Link } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Logo } from "@/components/logo"

export function DashboardPlaceholder() {
  return (
    <div className="flex min-h-full items-center p-6">
      <div className="flex max-w-md min-w-0 flex-col gap-4 text-sm leading-loose">
        <Logo className="size-8" />
        <div>
          <h1 className="font-medium">Dashboard shell — not built yet.</h1>
          <p>
            The three-column dashboard (vault · chat · nebula) lands on top of
            the component library.
          </p>
          <p className="text-muted-foreground">
            Meanwhile, the building blocks live on the components page.
          </p>
        </div>
        <Button render={<Link to="/components" />}>Browse components</Button>
      </div>
    </div>
  )
}
