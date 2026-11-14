"use client";

/**
 * "Bugünün mesajları" (2026-11-14, koç kararları): sistemin öğrenci hakkında fark
 * ettiği sorunlar, gelişmeler, hatırlatmalar ve yeni raporlar için hazır WhatsApp
 * mesajı. Sınır yok — koç seçer; bugün kaç mesaj gönderdiği üstte görünür.
 * Veri güvenilirliği uyarıları (toplu işaretleme vb.) listeye girmez.
 * Düzen ortak `SuggestionInbox` (kurum yöneticisinin "Koçlara mesajlar" ekranıyla aynı).
 */

import { SuggestionInbox } from "@/components/shared/suggestion-inbox";
import {
  getMessageSuggestions,
  messageSuggestionKeys,
  sendMessageSuggestion,
  skipMessageSuggestion,
} from "@/lib/api/message-suggestions";

export function MessageSuggestionsClient({ studentId }: { studentId: number | null }) {
  return (
    <SuggestionInbox
      title="Bugünün mesajları"
      description="Sistemin fark ettiği sorunlar, gelişmeler ve yeni raporlar için hazır WhatsApp mesajları. Soldan öğrenciyi seç, metni düzelt, kendi WhatsApp'ından gönder; gönderdiğin ya da atladığın öneri listeden düşer."
      groupNoun="öğrenci"
      queryKey={messageSuggestionKeys.list(null)}
      invalidateKey={messageSuggestionKeys.all}
      fetcher={() => getMessageSuggestions(null)}
      initialGroupId={studentId}
      groupHref={(id) => `/teacher/students/${id}`}
      groupLinkLabel="Öğrenci sayfası"
      send={(it, text, target) =>
        sendMessageSuggestion({
          student_id: it.student_id,
          audience: it.audience as "parent" | "student",
          key: it.key,
          text,
          target_user_id: target,
        })
      }
      skip={(it) =>
        skipMessageSuggestion({ student_id: it.student_id, audience: it.audience as "parent" | "student", key: it.key })
      }
    />
  );
}
