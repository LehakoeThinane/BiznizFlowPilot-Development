"use client";

import { useEffect, useRef, useState } from "react";

export function AudioAttachModal({ onSend, onClose }: { onSend: (file: File) => void; onClose: () => void }) {
  const [tab, setTab] = useState<"record" | "file">("record");
  const [error, setError] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [recordedUrl, setRecordedUrl] = useState<string | null>(null);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  async function startRecording() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setRecordedBlob(blob);
        setRecordedUrl(URL.createObjectURL(blob));
        stream.getTracks().forEach((t) => t.stop());
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch {
      setError("Couldn't access your microphone. Check your browser permissions and try again.");
    }
  }

  function stopRecording() {
    recorderRef.current?.stop();
    setRecording(false);
  }

  function discard() {
    if (recordedUrl) URL.revokeObjectURL(recordedUrl);
    setRecordedUrl(null);
    setRecordedBlob(null);
  }

  function sendRecording() {
    if (!recordedBlob) return;
    onSend(new File([recordedBlob], `voice-note-${Date.now()}.webm`, { type: "audio/webm" }));
    if (recordedUrl) URL.revokeObjectURL(recordedUrl);
    onClose();
  }

  function handleFilePicked(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) onSend(file);
    onClose();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-sm overflow-hidden rounded-2xl border border-outline-variant bg-[#0f1c33] shadow-2xl">
        <div className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
          <h2 className="text-base font-semibold text-white">Audio</h2>
          <button type="button" aria-label="Close" onClick={onClose} className="text-slate-400 hover:text-white">×</button>
        </div>

        <div className="flex border-b border-outline-variant">
          <button
            type="button"
            onClick={() => setTab("record")}
            className={`flex-1 py-2.5 text-sm font-medium transition-colors ${tab === "record" ? "border-b-2 border-blue-500 text-white" : "text-slate-400 hover:text-white"}`}
          >
            Record
          </button>
          <button
            type="button"
            onClick={() => setTab("file")}
            className={`flex-1 py-2.5 text-sm font-medium transition-colors ${tab === "file" ? "border-b-2 border-blue-500 text-white" : "text-slate-400 hover:text-white"}`}
          >
            Choose file
          </button>
        </div>

        <div className="p-6">
          {tab === "record" ? (
            error ? (
              <p className="text-center text-sm text-slate-400">{error}</p>
            ) : recordedUrl ? (
              <div className="flex flex-col items-center gap-4">
                <audio controls src={recordedUrl} className="w-full" />
                <div className="flex gap-3">
                  <button type="button" onClick={discard} className="rounded-md bg-white/10 px-4 py-2 text-sm font-medium text-white hover:bg-white/20">
                    Discard
                  </button>
                  <button type="button" onClick={sendRecording} className="erp-button-primary px-4 py-2 text-sm font-medium">
                    Send
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-4 py-4">
                <button
                  type="button"
                  onClick={recording ? stopRecording : startRecording}
                  aria-label={recording ? "Stop recording" : "Start recording"}
                  className={`flex h-16 w-16 items-center justify-center rounded-full text-white transition-colors ${recording ? "bg-rose-600 hover:bg-rose-700" : "bg-blue-600 hover:bg-blue-700"}`}
                >
                  <span className="material-symbols-outlined text-3xl">{recording ? "stop" : "mic"}</span>
                </button>
                <p className="text-xs text-slate-500">{recording ? "Recording… tap to stop" : "Tap to start recording a voice note"}</p>
              </div>
            )
          ) : (
            <label className="flex cursor-pointer flex-col items-center gap-3 rounded-xl border border-dashed border-outline-variant py-8 text-sm text-slate-400 hover:border-blue-500 hover:text-white">
              <span className="material-symbols-outlined text-3xl opacity-60">upload_file</span>
              Choose an audio file
              <input type="file" accept="audio/*" className="hidden" onChange={handleFilePicked} />
            </label>
          )}
        </div>
      </div>
    </div>
  );
}
