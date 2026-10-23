import { useCallback, useEffect, useRef, useState } from "react";
import type { Replay, State } from "./types";

export function useSimulation() {
  const [live, setLive] = useState<State | null>(null),
    [replay, setReplay] = useState<Replay | null>(null),
    [index, setIndex] = useState(0);
  const [busy, setBusy] = useState(false),
    [playing, setPlaying] = useState(false),
    [speed, setSpeed] = useState("800"),
    [error, setError] = useState("");
  const lock = useRef(false);
  const state = replay ? replay.frames[index] : live;
  const ended = Boolean(
    replay ? index >= replay.frames.length - 1 : state?.finished,
  );
  const loadLive = useCallback(async () => {
    const r = await fetch("/api/state");
    if (!r.ok) throw Error("The local simulation is unavailable.");
    setLive(await r.json());
  }, []);
  useEffect(() => {
    void loadLive().catch((e) => setError(e.message));
  }, [loadLive]);
  const action = useCallback(
    async (path: string, body: Record<string, unknown> = {}) => {
      if (lock.current) return false;
      lock.current = true;
      setBusy(true);
      setError("");
      try {
        const r = await fetch(path, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Demo-Token":
              document.querySelector<HTMLMetaElement>('meta[name="demo-token"]')
                ?.content || "",
          },
          body: JSON.stringify(body),
        });
        const s = await r.json();
        if (!r.ok) throw Error(s.error || "The action could not be completed.");
        setLive(s);
        return true;
      } catch (e) {
        setError(
          e instanceof Error ? e.message : "The action could not be completed.",
        );
        setPlaying(false);
        return false;
      } finally {
        lock.current = false;
        setBusy(false);
      }
    },
    [],
  );
  useEffect(() => {
    if (!playing || busy || ended) return;
    const t = setTimeout(() => {
      if (replay) setIndex((i) => Math.min(i + 1, replay.frames.length - 1));
      else void action("/api/tick");
    }, Number(speed));
    return () => clearTimeout(t);
  }, [playing, busy, ended, replay, index, state?.version, speed, action]);
  useEffect(() => {
    if (ended) setPlaying(false);
  }, [ended]);
  function openReplay(data: Replay) {
    if (
      !data ||
      data.schema !== "drone-demo-v1" ||
      !Array.isArray(data.frames) ||
      !data.frames.length ||
      data.frames.some(
        (s) =>
          !s ||
          !s.stats ||
          !Number.isFinite(Date.parse(s.clock)) ||
          !Array.isArray(s.sites) ||
          !Array.isArray(s.requests) ||
          !Array.isArray(s.drones) ||
          !Array.isArray(s.missions) ||
          !Array.isArray(s.social) ||
          !Array.isArray(s.decisions) ||
          !Array.isArray(s.log) ||
          !Array.isArray(s.blocked_routes),
      )
    )
      throw Error("Choose a valid exported Paris drone replay.");
    setPlaying(false);
    setReplay(data);
    setIndex(0);
    setError("");
  }
  async function review() {
    if (lock.current) return;
    setPlaying(false);
    lock.current = true;
    setBusy(true);
    try {
      const r = await fetch("/api/export");
      if (!r.ok) throw Error("Could not load this replay.");
      openReplay(await r.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }
  async function returnLive() {
    setPlaying(false);
    try {
      await loadLive();
      setReplay(null);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function importReplay(file: File) {
    setPlaying(false);
    try {
      if (file.size > 250_000_000)
        throw Error("Replay must be smaller than 250 MB.");
      openReplay(JSON.parse(await file.text()));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  function step() {
    setPlaying(false);
    if (replay) setIndex((i) => Math.min(i + 1, replay.frames.length - 1));
    else void action("/api/step");
  }
  return {
    state,
    replay,
    index,
    busy,
    playing,
    speed,
    error,
    ended,
    setPlaying,
    setSpeed,
    setError,
    action,
    review,
    returnLive,
    importReplay,
    step,
    seek: (i: number) => {
      setPlaying(false);
      setIndex(
        Math.max(0, Math.min(Math.round(i), (replay?.frames.length || 1) - 1)),
      );
    },
  };
}
