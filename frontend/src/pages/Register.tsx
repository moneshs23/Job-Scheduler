import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Zap } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { getErrorMessage } from "../lib/errors";
import { Button } from "../components/ui/Button";
import { Input, Label } from "../components/ui/Input";
import { Card } from "../components/ui/Card";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ fullName: "", orgName: "", email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(form.email, form.password, form.fullName, form.orgName);
      navigate("/");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Registration failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <div className="nb-border nb-shadow-sm bg-nb-pink h-12 w-12 flex items-center justify-center mb-4">
          <Zap size={24} strokeWidth={2.5} />
        </div>
        <h1 className="text-2xl font-black uppercase mb-1">Create account</h1>
        <p className="text-sm text-nb-ink/60 mb-6">Spin up your organization</p>

        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label>Full name</Label>
            <Input
              required
              value={form.fullName}
              onChange={(e) => setForm({ ...form, fullName: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label>Organization name</Label>
            <Input
              required
              value={form.orgName}
              onChange={(e) => setForm({ ...form, orgName: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label>Email</Label>
            <Input
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label>Password</Label>
            <Input
              type="password"
              required
              minLength={8}
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </div>
          {error && (
            <div className="nb-border bg-nb-red px-3 py-2 text-sm font-bold">{error}</div>
          )}
          <Button type="submit" disabled={loading} className="mt-2">
            {loading ? "Creating…" : "Create account"}
          </Button>
        </form>

        <p className="text-sm mt-4">
          Have an account?{" "}
          <Link to="/login" className="font-bold underline">
            Log in
          </Link>
        </p>
      </Card>
    </div>
  );
}
