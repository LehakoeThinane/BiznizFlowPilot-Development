"use client";

import { useEffect, useRef, useState } from "react";

export function CameraCaptureModal({ onSend, onClose }: { onSend: (file: File) => void; onClose: () => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [capturedUrl, setCapturedUrl] = useState<string | null>(null);
  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);

  useEffect(() => {
    let cancelled = false;
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "user" } })
      .then((stream) => {
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
      })
      .catch(() => setError("Couldn't access your camera. Check your browser permissions and try again."));

    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  function capture() {
    const video = videoRef.current;
    if (!video) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (!blob) return;
      setCapturedBlob(blob);
      setCapturedUrl(URL.createObjectURL(blob));
    }, "image/jpeg", 0.9);
  }

  function retake() {
    if (capturedUrl) URL.revokeObjectURL(capturedUrl);
    setCapturedUrl(null);
    setCapturedBlob(null);
  }

  function send() {
    if (!capturedBlob) return;
    onSend(new File([capturedBlob], `photo-${Date.now()}.jpg`, { type: "image/jpeg" }));
    if (capturedUrl) URL.revokeObjectURL(capturedUrl);
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-md overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
        <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
          <h2 className="text-base font-semibold text-white">Camera</h2>
          <button type="button" aria-label="Close" onClick={onClose} className="text-slate-400 hover:text-white">×</button>
        </div>
        <div className="flex aspect-video items-center justify-center bg-black">
          {error ? (
            <p className="p-6 text-center text-sm text-slate-400">{error}</p>
          ) : capturedUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={capturedUrl} alt="Captured photo" className="h-full w-full object-contain" />
          ) : (
            <video ref={videoRef} autoPlay playsInline muted className="h-full w-full object-contain" />
          )}
        </div>
        <div className="flex items-center justify-center gap-3 px-6 py-4">
          {error ? null : capturedUrl ? (
            <>
              <button type="button" onClick={retake} className="rounded-md bg-white/10 px-4 py-2 text-sm font-medium text-white hover:bg-white/20">
                Retake
              </button>
              <button type="button" onClick={send} className="erp-button-primary px-4 py-2 text-sm font-medium">
                Send
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={capture}
              aria-label="Capture photo"
              className="flex h-14 w-14 items-center justify-center rounded-full border-4 border-white/30 bg-white transition-colors hover:bg-white/80"
            />
          )}
        </div>
      </div>
    </div>
  );
}
