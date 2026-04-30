export type LiveChannel = {
  name: string;
  id: string;
  liveVideoId?: string;
};

export type LiveChannelGroup = {
  label: string;
  channels: LiveChannel[];
};
