import { useState } from 'react'
import { useProjects } from './api/projects'
import { useSessions } from './api/sessions'
import { Header } from './components/layout/Header'
import { ProjectList } from './components/projects/ProjectList'
import { SessionList } from './components/sessions/SessionList'
import { SessionViewer } from './components/viewer/SessionViewer'
import type { Source } from './types'

export default function App() {
  const [source, setSource] = useState<Source>('')
  const [selectedProject, setSelectedProject] = useState<string | null>(null)
  const [selectedSession, setSelectedSession] = useState<string | null>(null)

  const { data: projects = [], isLoading: projectsLoading } = useProjects(source)
  const { data: sessions = [], isLoading: sessionsLoading } = useSessions(selectedProject, source)

  function handleSourceChange(s: Source) {
    setSource(s)
    setSelectedProject(null)
    setSelectedSession(null)
  }

  function handleProjectSelect(path: string) {
    setSelectedProject(path)
    setSelectedSession(null)
  }

  const selectedProjectName = selectedProject?.split('/').pop() ?? ''

  return (
    <>
      <Header source={source} onSource={handleSourceChange} projects={projects} />

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar: Projects */}
        <aside className="w-72 border-r border-vault-border flex flex-col shrink-0 overflow-hidden">
          <div className="flex items-center justify-between px-3 py-2.5 border-b border-vault-border">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-vault-muted">
              Projects
            </span>
            {!projectsLoading && (
              <span className="text-[11px] text-vault-muted">{projects.length}</span>
            )}
          </div>
          <ProjectList
            projects={projects}
            loading={projectsLoading}
            selected={selectedProject}
            onSelect={handleProjectSelect}
          />
        </aside>

        {/* Session list (only when a project is selected) */}
        {selectedProject && (
          <SessionList
            sessions={sessions}
            loading={sessionsLoading}
            selected={selectedSession}
            projectName={selectedProjectName}
            onSelect={setSelectedSession}
          />
        )}

        {/* Session viewer */}
        <SessionViewer sessionId={selectedSession} projectPath={selectedProject} />
      </div>
    </>
  )
}
