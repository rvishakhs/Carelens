import { AxiosError } from "axios";

/** Backend error body shape -- app/shared/exceptions.py's CareLensError, serialised by
 * main.py's handle_carelens_error handler as {"code": ..., "message": ...}. */
interface ApiErrorBody {
  code?: string;
  message?: string;
}

export function extractErrorMessage(error: unknown, fallback = "Something went wrong. Please try again."): string {
  if (error instanceof AxiosError) {
    const body = error.response?.data as ApiErrorBody | undefined;
    if (body?.message) return body.message;
  }
  return fallback;
}
