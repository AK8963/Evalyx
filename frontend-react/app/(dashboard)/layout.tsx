import { Shell } from '@/components/layout/Shell'
import { ProjectProvider } from '@/components/layout/ProjectSelector'

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProjectProvider>
      <Shell>{children}</Shell>
    </ProjectProvider>
  )
}
