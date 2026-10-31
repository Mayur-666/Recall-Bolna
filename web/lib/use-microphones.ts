"use client";

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "recall.micDeviceId";

function readStored(): string {
  try {
    return window.localStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

/**
 * Audio input devices plus the user's chosen one (remembered per browser).
 * Labels are only filled in by the browser after mic permission has been granted once.
 */
export function useMicrophones() {
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceId, setDeviceIdState] = useState("");

  const refresh = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    try {
      const all = await navigator.mediaDevices.enumerateDevices();
      setDevices(all.filter((d) => d.kind === "audioinput" && d.deviceId));
    } catch {
      // enumerateDevices can reject in insecure contexts; the picker just stays hidden.
    }
  }, []);

  useEffect(() => {
    setDeviceIdState(readStored());
    void refresh();
    navigator.mediaDevices?.addEventListener?.("devicechange", refresh);
    return () => navigator.mediaDevices?.removeEventListener?.("devicechange", refresh);
  }, [refresh]);

  const setDeviceId = useCallback((id: string) => {
    setDeviceIdState(id);
    try {
      window.localStorage.setItem(STORAGE_KEY, id);
    } catch {
      // private mode: the choice just isn't remembered
    }
  }, []);

  // A stored id for a device that's since been unplugged is ignored.
  const known = devices.some((d) => d.deviceId === deviceId);
  return { devices, deviceId: known || devices.length === 0 ? deviceId : "", setDeviceId, refresh };
}

export const MIC_CONSTRAINTS: MediaTrackConstraints = {
  echoCancellation: true,
  noiseSuppression: true,
  autoGainControl: true,
};

export function micConstraints(deviceId: string): MediaTrackConstraints {
  return deviceId ? { ...MIC_CONSTRAINTS, deviceId: { exact: deviceId } } : MIC_CONSTRAINTS;
}
