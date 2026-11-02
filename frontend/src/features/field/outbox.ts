/**
 * Field outbox: work saved on the phone when there is no signal, sent in order when the connection returns.
 *
 * Stored in IndexedDB (photos are kept as Blobs). Items belong to the account that saved them and are only
 * sent while that account is logged in. A server rejection (e.g. the case was re-routed meanwhile) is kept
 * with its message so the worker can see it and discard it; it is never silently dropped.
 */
import axios from "axios";

import { api, apiErrorMessage, OfflineError } from "@/api/client";

export type FieldAction = "arrive" | "inspect" | "complete" | "blocker";

type FormEntry = { key: string; value: string } | { key: string; blob: Blob; filename: string };

export type OutboxItem = {
  id: string;
  userId: number;
  concernId: number;
  ref: string;
  action: FieldAction;
  label: string;
  json?: Record<string, unknown>;
  form?: FormEntry[];
  createdAt: string;
  error?: string;
};

const DB = "ccadss-field";
const STORE = "outbox";
const EVENT = "ccadss-outbox-changed";

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "id" });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T> | void): Promise<T | undefined> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, mode);
    const req = fn(t.objectStore(STORE));
    t.oncomplete = () => {
      db.close();
      resolve(req ? req.result : undefined);
    };
    t.onerror = () => reject(t.error);
  });
}

function changed() {
  window.dispatchEvent(new Event(EVENT));
}

export function onOutboxChange(fn: () => void) {
  window.addEventListener(EVENT, fn);
  return () => window.removeEventListener(EVENT, fn);
}

export async function listOutbox(): Promise<OutboxItem[]> {
  try {
    const all = ((await tx("readonly", (s) => s.getAll())) ?? []) as OutboxItem[];
    return all.sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  } catch {
    return []; // IndexedDB blocked (private mode): nothing queued
  }
}

export async function discard(id: string) {
  await tx("readwrite", (s) => s.delete(id));
  changed();
}

/** Everything a request needs, as plain data so it can wait in IndexedDB. */
export function formEntries(fields: Record<string, string | File[] | undefined | null>): FormEntry[] {
  const out: FormEntry[] = [];
  for (const [key, v] of Object.entries(fields)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((f) => out.push({ key, blob: f, filename: f.name || "photo.jpg" }));
    else out.push({ key, value: v });
  }
  return out;
}

function body(item: OutboxItem) {
  if (item.json) return item.json;
  const fd = new FormData();
  for (const e of item.form ?? []) {
    if ("blob" in e) fd.append(e.key, e.blob, e.filename);
    else fd.append(e.key, e.value);
  }
  return fd;
}

function isNetworkError(err: unknown) {
  return err instanceof OfflineError || (axios.isAxiosError(err) && !err.response);
}

async function send(item: OutboxItem) {
  return (await api.post(`/staff/concerns/${item.concernId}/${item.action}/`, body(item))).data;
}

export type SubmitResult = { queued: boolean };

/** Send now; without signal, save it on the phone. Server errors are thrown to the form as usual. */
export async function submitOrQueue(item: Omit<OutboxItem, "id" | "createdAt">): Promise<SubmitResult> {
  const full: OutboxItem = { ...item, id: crypto.randomUUID(), createdAt: new Date().toISOString() };
  if (navigator.onLine) {
    try {
      await send(full);
      return { queued: false };
    } catch (err) {
      if (!isNetworkError(err)) throw err;
    }
  }
  try {
    await tx("readwrite", (s) => s.put(full));
  } catch {
    throw new Error("Walang signal at hindi ma-save sa cellphone (naka-private mode ba ang browser?).");
  }
  changed();
  return { queued: true };
}

let flushing: Promise<number> | null = null;

/** Sends waiting items in the order they were saved. Returns how many were sent. */
export function flushOutbox(userId: number): Promise<number> {
  if (flushing) return flushing;
  flushing = (async () => {
    let sent = 0;
    for (const item of await listOutbox()) {
      if (item.userId !== userId || item.error) continue;
      try {
        await send(item);
        await tx("readwrite", (s) => s.delete(item.id));
        sent += 1;
      } catch (err) {
        if (isNetworkError(err)) break; // still no signal: try again later
        await tx("readwrite", (s) => s.put({ ...item, error: apiErrorMessage(err) }));
      }
    }
    changed();
    return sent;
  })().finally(() => {
    flushing = null;
  });
  return flushing;
}
