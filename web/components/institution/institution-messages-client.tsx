"use client";

/**
 * Kurum yöneticisi "Koçlara mesajlar" (2026-11-14): koçun öğrencilerinde görülen
 * durumlar (programsız öğrenci, düşük tamamlama, risk, programını yapmayan
 * öğrenci, yüksek tamamlama tebriği) için koça hazır WhatsApp mesajı.
 * Ölçüm Müdahale Merkezi / Program Uyumu ile aynı; düzen koç ekranıyla ortak.
 */

import { SuggestionInbox } from "@/components/shared/suggestion-inbox";
import {
  getInstMessageSuggestions,
  instMessageSuggestionKeys,
  sendInstMessageSuggestion,
  skipInstMessageSuggestion,
} from "@/lib/api/message-suggestions";

export function InstitutionMessagesClient() {
  return (
    <SuggestionInbox
      title="Koçlara mesajlar"
      description="Koçlarınızın öğrencilerinde görülen durumlar için koça hazır WhatsApp mesajları: programsız öğrenciler, düşük tamamlama, risk sinyali, programını yapmayan öğrenciler ve tebrik. Soldan koçu seç, metni düzelt, kendi WhatsApp'ından gönder."
      groupNoun="koç"
      queryKey={instMessageSuggestionKeys.all}
      invalidateKey={instMessageSuggestionKeys.all}
      fetcher={getInstMessageSuggestions}
      groupHref={(id) => `/institution/teachers/${id}`}
      groupLinkLabel="Koç sayfası"
      send={(it, text) => sendInstMessageSuggestion({ coach_id: it.group_id, key: it.key, text })}
      skip={(it) => skipInstMessageSuggestion({ coach_id: it.group_id, key: it.key })}
    />
  );
}
