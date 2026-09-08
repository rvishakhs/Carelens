import type { AxiosError } from "axios";

import { createCareEvent } from "@/utils/helper";
import type { CareEvent, CareEventCreate } from "@/types";

const STORAGE_KEY = "carelens.pendingCareEvents";

export interface PendingCareEvent {
  localId: string;
  payload: CareEventCreate;
  queuedAt: string;
  attempts: number;
}

function readAll(): PendingCareEvent[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as PendingCareEvent[]) : [];
  } catch {
    return [];
  }
}

function writeAll(items: PendingCareEvent[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
}

export function getPending(): PendingCareEvent[] {
  return readAll();
}

export function getPendingCount(): number {
  return readAll().length;
}

/** Queues a care event that already has its idempotency_key set (generated once,
 * before the first send attempt -- see saveCareEventDurable in helper.ts) so every
 * retry, whether from this tab or another, resends the exact same key. */
export function enqueue(payload: CareEventCreate): void {
  const items = readAll();
  items.push({
    localId: crypto.randomUUID(),
    payload,
    queuedAt: new Date().toISOString(),
    attempts: 0,
  });
  writeAll(items);
}

function removePending(localId: string): void {
  writeAll(readAll().filter((item) => item.localId !== localId));
}

/** True for failures worth retrying later: no response at all (offline/DNS/timeout),
 * an expired-session 401 (the token-refresh interceptor may recover by the next
 * attempt), a request timeout (408), rate limiting (429), or a server-side error
 * (5xx). False for everything else (400/403/404/422/...) -- those are genuine
 * problems with the request itself that retrying won't fix, so they should surface
 * to the user immediately instead of queuing forever. */
export function isRetryable(err: unknown): boolean {
  const axiosErr = err as AxiosError;
  if (!axiosErr?.response) return true;
  const status = axiosErr.response.status;
  return status === 401 || status === 408 || status === 429 || status >= 500;
}

/** True when the server has already processed this exact idempotency_key --
 * safe to treat as success and drop from the queue. */
function isAlreadySynced(err: unknown): boolean {
  return (err as AxiosError)?.response?.status === 409;
}

/** Drains the queue oldest-first. Stops at the first still-retryable failure (rather
 * than skipping ahead) so a downed server doesn't get hammered once per queued item;
 * whatever's left stays queued for the next trigger (online event, interval, retry
 * button). */
export async function syncPending(): Promise<{ succeeded: number; remaining: number }> {
  const items = readAll();
  let succeeded = 0;

  for (const item of items) {
    try {
      await createCareEvent(item.payload);
      removePending(item.localId);
      succeeded++;
    } catch (err) {
      if (isAlreadySynced(err)) {
        removePending(item.localId);
        succeeded++;
        continue;
      }
      if (isRetryable(err)) {
        const remainingItems = readAll();
        const current = remainingItems.find((i) => i.localId === item.localId);
        if (current) {
          current.attempts += 1;
          writeAll(remainingItems);
        }
        break;
      }
      // Non-retryable (e.g. validation error baked into a queued payload) --
      // drop it rather than retry forever; there's nothing a future attempt
      // could do differently.
      removePending(item.localId);
    }
  }

  return { succeeded, remaining: getPendingCount() };
}

export type DurableSaveResult = { queued: false; event: CareEvent } | { queued: true };

/** The save path the recording UI should call instead of createCareEvent directly.
 * Attaches a fresh idempotency_key, tries the request once immediately, and on a
 * retryable failure durably queues it (with that same key) instead of throwing --
 * from the caller's perspective the entry is safely captured either way. Genuine
 * non-retryable failures (validation, permissions) still throw, since retrying
 * those could never succeed. */
export async function saveCareEventDurable(payload: CareEventCreate): Promise<DurableSaveResult> {
  const withKey: CareEventCreate = { ...payload, idempotency_key: payload.idempotency_key ?? crypto.randomUUID() };
  try {
    const event = await createCareEvent(withKey);
    return { queued: false, event };
  } catch (err) {
    if (isRetryable(err)) {
      enqueue(withKey);
      return { queued: true };
    }
    throw err;
  }
}
