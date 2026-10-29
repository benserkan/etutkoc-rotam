interface PrintVideo {
  id: number;
  title: string;
  duration_min: number | null;
  role: string;
}

/** Yazdırma çıktısı: video görevinin videoları (kâğıtta link tıklanamaz —
 *  öğrenci hangi videoyu izleyeceğini başlığından bulur). Tek videolu görevde
 *  başlık zaten yeterli; liste yalnız çok videoda basılır. */
export function PrintVideoList({ videos }: { videos: PrintVideo[] | null | undefined }) {
  if (!videos || videos.length < 2) return null;
  return (
    <ol className="mt-0.5 space-y-px pl-1 text-[8.5px] leading-tight text-stone-700">
      {videos.map((v, i) => (
        <li key={v.id} className="break-words">
          {i + 1}. {v.title}
          {v.duration_min ? <span className="text-stone-500"> · {v.duration_min} dk</span> : null}
          {v.role === "soru" ? <span className="font-semibold text-amber-800"> (soru çözümü)</span> : null}
        </li>
      ))}
    </ol>
  );
}
