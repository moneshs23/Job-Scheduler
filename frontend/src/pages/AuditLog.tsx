import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { useProject } from "../context/ProjectContext";
import { relativeTime } from "../lib/format";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import type { Page as PageT } from "../lib/types";

interface AuditEntry {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  ip_address: string | null;
  created_at: string;
}

const ACTION_COLORS: Record<string, string> = {
  created: "bg-nb-lime",
  updated: "bg-nb-cyan",
  paused: "bg-nb-orange",
  resumed: "bg-nb-lime",
  cancelled: "bg-nb-red",
  replayed: "bg-nb-violet",
  shutdown_requested: "bg-nb-orange",
};

export function AuditLogPage() {
  const { organization } = useProject();
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["audit-log", organization?.id, page],
    queryFn: async () =>
      (
        await api.get<PageT<AuditEntry>>(`/organizations/${organization!.id}/audit-logs`, {
          params: { page, page_size: 25 },
        })
      ).data,
    enabled: !!organization,
    refetchInterval: 8000,
  });

  if (!organization) return null;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-black uppercase">Audit Log</h1>
        <p className="text-sm text-nb-ink/60">Who did what, across every project in {organization.name}</p>
      </div>

      <Card className="p-0 overflow-x-auto">
        <table className="w-full text-sm min-w-[600px]">
          <thead>
            <tr className="border-b-[3px] border-nb-ink text-left uppercase text-xs">
              <th className="p-3">Action</th>
              <th className="p-3">Resource</th>
              <th className="p-3">IP</th>
              <th className="p-3">When</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={4} className="p-6 text-center text-nb-ink/50">
                  Loading…
                </td>
              </tr>
            )}
            {data?.items.map((entry) => {
              const suffix = entry.action.split(".")[1] ?? "";
              return (
                <tr key={entry.id} className="border-b border-nb-ink/15">
                  <td className="p-3">
                    <span
                      className={`nb-border px-2 py-0.5 text-[11px] font-bold uppercase ${
                        ACTION_COLORS[suffix] ?? "bg-nb-paper-2"
                      }`}
                    >
                      {entry.action}
                    </span>
                  </td>
                  <td className="p-3 text-xs font-mono">
                    {entry.resource_type}
                    {entry.resource_id && <span className="text-nb-ink/50">/{entry.resource_id.slice(0, 8)}</span>}
                  </td>
                  <td className="p-3 text-xs text-nb-ink/60">{entry.ip_address ?? "—"}</td>
                  <td className="p-3 text-xs text-nb-ink/60" title={new Date(entry.created_at).toLocaleString()}>
                    {relativeTime(entry.created_at)}
                  </td>
                </tr>
              );
            })}
            {data?.items.length === 0 && !isLoading && (
              <tr>
                <td colSpan={4} className="p-6 text-center text-nb-ink/60">
                  No activity recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>

      {data && data.pages > 1 && (
        <div className="flex items-center gap-2">
          <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            ← Prev
          </Button>
          <span className="text-sm font-bold">
            Page {data.page} / {data.pages}
          </span>
          <Button variant="secondary" disabled={page >= data.pages} onClick={() => setPage((p) => p + 1)}>
            Next →
          </Button>
        </div>
      )}
    </div>
  );
}
