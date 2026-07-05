import { AxiosError } from "axios";

export function getErrorMessage(err: unknown, fallback = "Something went wrong"): string {
  if (err instanceof AxiosError) {
    const data = err.response?.data as { error?: string; details?: { msg?: string }[] } | undefined;
    if (data?.details?.length) return data.details.map((d) => d.msg).filter(Boolean).join(", ");
    if (data?.error) return data.error;
  }
  if (err instanceof Error) return err.message;
  return fallback;
}
