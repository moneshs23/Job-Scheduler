import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { Organization, Project } from "../lib/types";
import { useAuth } from "./AuthContext";

interface ProjectContextValue {
  organization: Organization | null;
  project: Project | null;
  projects: Project[];
  setProjectId: (id: string) => void;
  refetchProjects: () => void;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [projectId, setProjectId] = useState<string | null>(
    () => localStorage.getItem("djs_project_id"),
  );

  const { data: organizations } = useQuery({
    queryKey: ["organizations"],
    queryFn: async () => (await api.get<Organization[]>("/organizations")).data,
    enabled: !!user,
  });
  const organization = organizations?.[0] ?? null;

  const { data: projects, refetch } = useQuery({
    queryKey: ["projects", organization?.id],
    queryFn: async () =>
      (await api.get<Project[]>(`/organizations/${organization!.id}/projects`)).data,
    enabled: !!organization,
  });

  useEffect(() => {
    if (projects && projects.length > 0 && !projects.some((p) => p.id === projectId)) {
      setProjectId(projects[0].id);
    }
  }, [projects, projectId]);

  useEffect(() => {
    if (projectId) localStorage.setItem("djs_project_id", projectId);
  }, [projectId]);

  const project = projects?.find((p) => p.id === projectId) ?? null;

  return (
    <ProjectContext.Provider
      value={{
        organization,
        project,
        projects: projects ?? [],
        setProjectId,
        refetchProjects: refetch,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject() {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error("useProject must be used within ProjectProvider");
  return ctx;
}
