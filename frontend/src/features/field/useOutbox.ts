import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/auth/AuthContext";

import { discard, flushOutbox, listOutbox, onOutboxChange, type OutboxItem } from "./outbox";

export function useOnline() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener("online", up);
    window.addEventListener("offline", down);
    return () => {
      window.removeEventListener("online", up);
      window.removeEventListener("offline", down);
    };
  }, []);
  return online;
}

/** The waiting items, plus automatic sending when the signal comes back (and every 30 s while items wait). */
export function useOutbox({ autoFlush = false } = {}) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const online = useOnline();
  const [items, setItems] = useState<OutboxItem[]>([]);
  const [sending, setSending] = useState(false);

  const reload = useCallback(() => {
    void listOutbox().then(setItems);
  }, []);
  useEffect(() => {
    reload();
    return onOutboxChange(reload);
  }, [reload]);

  const flush = useCallback(async () => {
    if (!user) return;
    setSending(true);
    try {
      const sent = await flushOutbox(user.id);
      if (sent) qc.invalidateQueries({ queryKey: ["staff"] });
    } finally {
      setSending(false);
    }
  }, [user, qc]);

  const pending = items.filter((i) => user && i.userId === user.id && !i.error).length;
  useEffect(() => {
    if (!autoFlush || !online || !pending) return;
    void flush();
    const t = setInterval(() => void flush(), 30_000);
    return () => clearInterval(t);
  }, [autoFlush, online, pending, flush]);

  return { items, pending, online, sending, flush, discard };
}
