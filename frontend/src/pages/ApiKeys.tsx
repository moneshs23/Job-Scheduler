import { type FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, KeyRound, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import { useProject } from "../context/ProjectContext";
import { useToast } from "../context/ToastContext";
import { getErrorMessage } from "../lib/errors";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input, Label } from "../components/ui/Input";
import { Modal } from "../components/ui/Modal";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";

interface ApiKey {
  id: string;
  project_id: string | null;
  name: string;
  key_prefix: string;
  scopes: string[] | null;
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export function ApiKeysPage() {
  const { project } = useProject();
  const { push } = useToast();
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<ApiKey | null>(null);
  const [name, setName] = useState("");

  const { data: keys, isLoading } = useQuery({
    queryKey: ["api-keys"],
    queryFn: async () => (await api.get<ApiKey[]>("/auth/api-keys")).data,
  });

  const createKey = useMutation({
    mutationFn: async () =>
      (await api.post("/auth/api-keys", { name, project_id: project?.id ?? null, scopes: [] })).data,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      setNewKey(data.key);
      setName("");
    },
    onError: (err) => push(getErrorMessage(err), "error"),
  });

  const revokeKey = useMutation({
    mutationFn: async (id: string) => (await api.delete(`/auth/api-keys/${id}`)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      push("API key revoked");
      setRevokeTarget(null);
    },
    onError: (err) => push(getErrorMessage(err), "error"),
  });

  const copyKey = async (key: string) => {
    await navigator.clipboard.writeText(key);
    push("Copied to clipboard", "info");
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-black uppercase">API Keys</h1>
          <p className="text-sm text-nb-ink/60">Scoped credentials for programmatic access</p>
        </div>
        <Button onClick={() => setModalOpen(true)}>+ New Key</Button>
      </div>

      <Card className="p-0 overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead>
            <tr className="border-b-[3px] border-nb-ink text-left uppercase text-xs">
              <th className="p-3">Name</th>
              <th className="p-3">Prefix</th>
              <th className="p-3">Status</th>
              <th className="p-3">Created</th>
              <th className="p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={5} className="p-6 text-center text-nb-ink/50">
                  Loading…
                </td>
              </tr>
            )}
            {keys?.map((key) => (
              <tr key={key.id} className="border-b border-nb-ink/15">
                <td className="p-3 font-bold">{key.name}</td>
                <td className="p-3 font-mono text-xs">djs_{key.key_prefix}…</td>
                <td className="p-3">
                  <span
                    className={`nb-border px-2 py-0.5 text-[11px] font-bold uppercase ${
                      key.revoked_at ? "bg-nb-red" : "bg-nb-lime"
                    }`}
                  >
                    {key.revoked_at ? "Revoked" : "Active"}
                  </span>
                </td>
                <td className="p-3 text-xs text-nb-ink/60">{new Date(key.created_at).toLocaleDateString()}</td>
                <td className="p-3">
                  {!key.revoked_at && (
                    <Button variant="danger" className="px-2 py-1 text-xs" onClick={() => setRevokeTarget(key)}>
                      <Trash2 size={14} className="inline mr-1 -mt-0.5" />
                      Revoke
                    </Button>
                  )}
                </td>
              </tr>
            ))}
            {keys?.length === 0 && !isLoading && (
              <tr>
                <td colSpan={5} className="p-6 text-center text-nb-ink/60">
                  No API keys yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Card>

      <Modal
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setNewKey(null);
        }}
        title="New API Key"
      >
        {newKey ? (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-nb-ink/70">
              Copy this key now — you won't be able to see it again.
            </p>
            <div className="nb-border bg-nb-bg p-3 flex items-center justify-between gap-2">
              <code className="text-xs break-all">{newKey}</code>
              <button onClick={() => copyKey(newKey)} className="shrink-0">
                <Copy size={16} />
              </button>
            </div>
            <Button
              onClick={() => {
                setModalOpen(false);
                setNewKey(null);
              }}
            >
              Done
            </Button>
          </div>
        ) : (
          <form
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              createKey.mutate();
            }}
            className="flex flex-col gap-3"
          >
            <div className="flex flex-col gap-1">
              <Label>Name</Label>
              <Input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. CI pipeline"
              />
            </div>
            {project && (
              <p className="text-xs text-nb-ink/60">
                Scoped to project <b>{project.name}</b>.
              </p>
            )}
            <Button type="submit" disabled={createKey.isPending}>
              <KeyRound size={16} className="inline mr-1 -mt-0.5" />
              {createKey.isPending ? "Creating…" : "Create key"}
            </Button>
          </form>
        )}
      </Modal>

      <ConfirmDialog
        open={!!revokeTarget}
        title="Revoke API key?"
        message={`"${revokeTarget?.name}" will stop working immediately for any service using it.`}
        confirmLabel="Revoke"
        onConfirm={() => revokeTarget && revokeKey.mutate(revokeTarget.id)}
        onCancel={() => setRevokeTarget(null)}
        loading={revokeKey.isPending}
      />
    </div>
  );
}
