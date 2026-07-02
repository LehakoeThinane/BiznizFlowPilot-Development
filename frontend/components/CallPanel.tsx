"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiRequest } from "@/lib/api";
import { getStoredToken } from "@/lib/auth";
import type { AgoraJoinResponse, MeetingCallType, MeetingParticipant } from "@/types/api";
import {
  createAgoraClient,
  deriveAgoraUid,
  joinChannel,
  leaveChannel,
  publishLocalTracks,
  startScreenShare,
  stopScreenShare,
  type IAgoraRTCClient,
  type IAgoraRTCRemoteUser,
} from "@/lib/agora";
import type { ICameraVideoTrack, ILocalVideoTrack, IMicrophoneAudioTrack } from "agora-rtc-sdk-ng";

interface CallPanelProps {
  meetingId: string;
  callType: MeetingCallType;
  participants: MeetingParticipant[];
  isOrganizer: boolean;
  onClose: () => void;
}

type Status = "connecting" | "connected" | "error";

export function CallPanel({ meetingId, callType, participants, isOrganizer, onClose }: CallPanelProps) {
  const token = getStoredToken();
  const [status, setStatus] = useState<Status>("connecting");
  const [errorMsg, setErrorMsg] = useState("");
  const [muted, setMuted] = useState(false);
  const [cameraOff, setCameraOff] = useState(false);
  const [sharingScreen, setSharingScreen] = useState(false);
  const [remoteUsers, setRemoteUsers] = useState<IAgoraRTCRemoteUser[]>([]);

  const clientRef = useRef<IAgoraRTCClient | null>(null);
  const audioTrackRef = useRef<IMicrophoneAudioTrack | null>(null);
  const videoTrackRef = useRef<ICameraVideoTrack | null>(null);
  const screenTrackRef = useRef<ILocalVideoTrack | null>(null);
  const localContainerRef = useRef<HTMLDivElement | null>(null);
  const tileRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  const nameForUid = useCallback(
    (uid: number) => participants.find((p) => deriveAgoraUid(p.user_id) === uid)?.full_name ?? `User ${uid}`,
    [participants],
  );

  useEffect(() => {
    let cancelled = false;
    const client = createAgoraClient();
    clientRef.current = client;

    client.on("user-published", async (user, mediaType) => {
      await client.subscribe(user, mediaType);
      if (mediaType === "audio") user.audioTrack?.play();
      if (!cancelled) setRemoteUsers([...client.remoteUsers]);
    });
    client.on("user-unpublished", () => { if (!cancelled) setRemoteUsers([...client.remoteUsers]); });
    client.on("user-left", () => { if (!cancelled) setRemoteUsers([...client.remoteUsers]); });

    (async () => {
      try {
        const join = await apiRequest<AgoraJoinResponse>(`/api/v1/meetings/${meetingId}/join`, {
          method: "POST",
          authToken: token,
        });
        if (cancelled) return;
        await joinChannel(client, join.agora_app_id, join.channel_name, join.token, join.uid);
        const { audioTrack, videoTrack } = await publishLocalTracks(client, {
          audio: true,
          video: callType === "video",
        });
        if (cancelled) return;
        audioTrackRef.current = audioTrack;
        videoTrackRef.current = videoTrack;
        if (videoTrack && localContainerRef.current) videoTrack.play(localContainerRef.current);
        setStatus("connected");
      } catch (err) {
        if (cancelled) return;
        setErrorMsg(err instanceof Error ? err.message : "Failed to join the call.");
        setStatus("error");
      }
    })();

    return () => {
      cancelled = true;
      client.removeAllListeners();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meetingId, callType]);

  // Play each remote video track into its tile whenever the remote user list changes
  useEffect(() => {
    for (const user of remoteUsers) {
      const el = tileRefs.current.get(user.uid as number);
      if (user.videoTrack && el) user.videoTrack.play(el);
    }
  }, [remoteUsers]);

  async function handleLeave() {
    const client = clientRef.current;
    if (client) {
      await leaveChannel(client, [audioTrackRef.current, videoTrackRef.current, screenTrackRef.current]);
    }
    if (isOrganizer) {
      apiRequest(`/api/v1/meetings/${meetingId}/end`, { method: "POST", authToken: token }).catch(() => {});
    }
    onClose();
  }

  function toggleMute() {
    const track = audioTrackRef.current;
    if (!track) return;
    const next = !muted;
    track.setEnabled(!next);
    setMuted(next);
  }

  function toggleCamera() {
    const track = videoTrackRef.current;
    if (!track) return;
    const next = !cameraOff;
    track.setEnabled(!next);
    setCameraOff(next);
  }

  async function toggleScreenShare() {
    const client = clientRef.current;
    if (!client) return;
    try {
      if (sharingScreen) {
        if (screenTrackRef.current) await stopScreenShare(client, screenTrackRef.current);
        screenTrackRef.current = null;
        if (videoTrackRef.current) {
          await client.publish(videoTrackRef.current);
          if (localContainerRef.current) videoTrackRef.current.play(localContainerRef.current);
        }
        setSharingScreen(false);
      } else {
        if (videoTrackRef.current) await client.unpublish(videoTrackRef.current);
        const screenTrack = await startScreenShare(client);
        screenTrackRef.current = screenTrack;
        if (localContainerRef.current) screenTrack.play(localContainerRef.current);
        setSharingScreen(true);
      }
    } catch {
      // User cancelled the screen picker, or the platform blocked capture — leave state as-is.
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4">
      <div className="flex h-[85vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
        <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
          <h2 className="text-base font-semibold text-white">
            {callType === "video" ? "Video Call" : "Voice Call"}
          </h2>
          {status === "connecting" && <span className="text-xs text-slate-400">Connecting…</span>}
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {status === "error" ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
              <p className="max-w-sm text-sm text-rose-400">{errorMsg}</p>
              <button type="button" onClick={onClose} className="erp-button-primary px-4 py-2 text-sm">
                Close
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div className="relative aspect-video overflow-hidden rounded-xl bg-black/40">
                <div ref={localContainerRef} className="h-full w-full" />
                {(callType === "voice" || (cameraOff && !sharingScreen)) && (
                  <div className="absolute inset-0 flex items-center justify-center bg-[#0a1528] text-sm text-slate-400">
                    You{muted ? " (muted)" : ""}
                  </div>
                )}
                <span className="absolute bottom-1.5 left-1.5 rounded bg-black/60 px-1.5 py-0.5 text-[11px] text-white">
                  You{sharingScreen ? " (sharing)" : ""}
                </span>
              </div>
              {remoteUsers.map((user) => (
                <div key={user.uid} className="relative aspect-video overflow-hidden rounded-xl bg-black/40">
                  <div
                    ref={(el) => { if (el) tileRefs.current.set(user.uid as number, el); }}
                    className="h-full w-full"
                  />
                  {!user.videoTrack && (
                    <div className="absolute inset-0 flex items-center justify-center bg-[#0a1528] text-sm text-slate-400">
                      {nameForUid(user.uid as number)}
                    </div>
                  )}
                  <span className="absolute bottom-1.5 left-1.5 rounded bg-black/60 px-1.5 py-0.5 text-[11px] text-white">
                    {nameForUid(user.uid as number)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {status === "connected" && (
          <div className="flex justify-center gap-3 border-t border-white/8 px-6 py-4">
            <button
              type="button"
              onClick={toggleMute}
              className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                muted ? "bg-rose-600 text-white" : "bg-white/10 text-slate-300 hover:bg-white/20"
              }`}
            >
              {muted ? "Unmute" : "Mute"}
            </button>
            {callType === "video" && (
              <>
                <button
                  type="button"
                  onClick={toggleCamera}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                    cameraOff ? "bg-rose-600 text-white" : "bg-white/10 text-slate-300 hover:bg-white/20"
                  }`}
                >
                  {cameraOff ? "Start Video" : "Stop Video"}
                </button>
                <button
                  type="button"
                  onClick={toggleScreenShare}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
                    sharingScreen ? "bg-blue-600 text-white" : "bg-white/10 text-slate-300 hover:bg-white/20"
                  }`}
                >
                  {sharingScreen ? "Stop Sharing" : "Share Screen"}
                </button>
              </>
            )}
            <button
              type="button"
              onClick={handleLeave}
              className="rounded-full bg-rose-600 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-rose-500"
            >
              Leave
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
