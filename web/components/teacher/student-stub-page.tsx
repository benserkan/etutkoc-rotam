import Link from "next/link";
import { Construction } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Paket 3.5b'de açılan stub sayfa şablonu. Öğrenci detay header'ından
 * Sınıf Yükselt / Hedefler / Tekrar / DNA / Odak linklerine basıldığında
 * 404 yerine kullanıcıya bilgi veren bir karşılama sayfası gösterir.
 *
 * Tam içerik Paket 3.5d kapsamında inşa edilecek.
 */
export function StubPage({
  studentId,
  title,
  description,
}: {
  studentId: number;
  title: string;
  description: string;
}) {
  return (
    <div className="space-y-6 max-w-2xl">
      <header>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          <Link
            href={`/teacher/students/${studentId}`}
            className="hover:underline"
          >
            ← Öğrenci detayı
          </Link>
        </p>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-1">
          {title}
        </h1>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="text-base inline-flex items-center gap-2">
            <Construction className="size-4 text-muted-foreground" aria-hidden />
            Yakında
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground leading-relaxed">
            {description}
          </p>
          <p className="text-xs text-muted-foreground">
            Bu pakette (3.5b) yalnızca öğrenci detay header&apos;ı, koçluk takvimi
            anchor düzenlemesi ve sinema-koltuğu modalı aktif edildi. Detay
            sayfaların tam aktarımı sıraya alındı.
          </p>
          <Link
            href={`/teacher/students/${studentId}`}
            className="inline-block text-sm underline-offset-4 hover:underline text-foreground"
          >
            ← Öğrenci detayına geri dön
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
