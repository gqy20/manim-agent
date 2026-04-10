"use client";

interface VideoPlayerProps {
  src: string;
}

export function VideoPlayer({ src }: VideoPlayerProps) {
  return (
    <div className="flex flex-col gap-3">
      <video
        src={src}
        controls
        className="w-full rounded-md border bg-black max-h-[500px]"
        preload="metadata"
      >
        Your browser does not support the video tag.
      </video>
      <a
        href={src}
        download
        className="text-sm text-blue-500 hover:text-blue-700 underline"
      >
        Download video
      </a>
    </div>
  );
}
