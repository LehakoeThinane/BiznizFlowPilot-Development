import AgoraRTC, {
  type ICameraVideoTrack,
  type IMicrophoneAudioTrack,
  type ILocalVideoTrack,
  type IAgoraRTCClient,
  type IAgoraRTCRemoteUser,
} from "agora-rtc-sdk-ng";

export type { IAgoraRTCClient, IAgoraRTCRemoteUser };

export function createAgoraClient(): IAgoraRTCClient {
  return AgoraRTC.createClient({ mode: "rtc", codec: "vp8" });
}

export async function joinChannel(
  client: IAgoraRTCClient,
  appId: string,
  channel: string,
  token: string,
  uid: number,
): Promise<void> {
  await client.join(appId, channel, token, uid);
}

export async function publishLocalTracks(
  client: IAgoraRTCClient,
  { audio, video }: { audio: boolean; video: boolean },
): Promise<{ audioTrack: IMicrophoneAudioTrack | null; videoTrack: ICameraVideoTrack | null }> {
  const audioTrack = audio ? await AgoraRTC.createMicrophoneAudioTrack() : null;
  const videoTrack = video ? await AgoraRTC.createCameraVideoTrack() : null;
  const tracks = [audioTrack, videoTrack].filter((t): t is ICameraVideoTrack | IMicrophoneAudioTrack => t !== null);
  if (tracks.length > 0) await client.publish(tracks);
  return { audioTrack, videoTrack };
}

export async function startScreenShare(client: IAgoraRTCClient): Promise<ILocalVideoTrack> {
  const screenTrack = await AgoraRTC.createScreenVideoTrack({ encoderConfig: "1080p_1" }, "disable");
  const track = Array.isArray(screenTrack) ? screenTrack[0] : screenTrack;
  await client.publish(track);
  return track;
}

export async function stopScreenShare(client: IAgoraRTCClient, screenTrack: ILocalVideoTrack): Promise<void> {
  await client.unpublish(screenTrack);
  screenTrack.close();
}

export async function leaveChannel(
  client: IAgoraRTCClient,
  localTracks: (IMicrophoneAudioTrack | ICameraVideoTrack | ILocalVideoTrack | null)[],
): Promise<void> {
  for (const track of localTracks) {
    if (!track) continue;
    track.stop();
    track.close();
  }
  await client.leave();
}

/** Deterministic Agora uid from a user's UUID — mirrors app/services/meeting.py:derive_agora_uid. */
export function deriveAgoraUid(userId: string): number {
  const hex = userId.replace(/-/g, "").slice(0, 8);
  return (parseInt(hex, 16) % 2_147_483_646) + 1;
}
