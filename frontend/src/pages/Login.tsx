import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Zap } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { getErrorMessage } from "../lib/errors";
import { Button } from "../components/ui/Button";
import { Input, Label } from "../components/ui/Input";
import { Card } from "../components/ui/Card";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(getErrorMessage(err, "Invalid email or password"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <div className="nb-border nb-shadow-sm bg-nb-yellow h-12 w-12 flex items-center justify-center mb-4">
          <Zap size={24} strokeWidth={2.5} />
        </div>
        <h1 className="text-2xl font-black uppercase mb-1">Log in</h1>
        <p className="text-sm text-nb-ink/60 mb-6">Distributed Job Scheduler</p>

        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label>Email</Label>
            <Input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label>Password</Label>
            <Input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>
          {error && (
            <div className="nb-border bg-nb-red px-3 py-2 text-sm font-bold">{error}</div>
          )}
          <Button type="submit" disabled={loading} className="mt-2">
            {loading ? "Logging in…" : "Log in"}
          </Button>
        </form>

        <p className="text-sm mt-4">
          No account?{" "}
          <Link to="/register" className="font-bold underline">
            Register
          </Link>
        </p>
      </Card>
    </div>
  );
}
