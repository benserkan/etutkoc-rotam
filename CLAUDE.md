# CLAUDE.md — Proje Notu

Bu dosya Claude Code'un her sohbette okuduğu kalıcı proje notudur. Memory'ye
yazmak yerine **yapılan paketler + kararlar + sırada ne var** burada tutulur.
Sohbet bitince son durumu buraya yaz; bir sonraki sohbet buradan devam eder.

---

## Rezerv yaşam döngüsü + Kitaplık temizliği — Faz 0/1a/1b CANLI, Faz 2/3 sırada (2026-06-28, commit `977c175`)

**Bağlam (kullanıcı, Elif/student 34 Kitaplar ekranı):** (1) yaz dönemine girildi,
bazı kitaplar program-dışı çözülüp bitti ama sisteme işlenmedi; koç kitaplığı
temizlemek istiyor. (2) 10→11 sınıf geçişinde eski sınıf kitapları kitaplıkta
kalıyor → zamanla yönetilemez. (3) Elif hâlâ "Rezerv 2/3" gösteriyor; koç "düşmesi
gerekirdi" diyor → rezerv tutma/serbest bırakma algoritmasının her noktası kontrol
edilsin. Önce **ihtiyaç analizi** istendi.

**Analiz bulguları (kodla + prod read-only teşhisle kanıtlı):**
- Rezerv serbest bırakma **tamamen olay-güdümlü**: yalnız (a) `create_program`,
  (b) görev-ekle kenar çubuğu (`weekly_plan.sidebar_items`), (c) carryover GET/POST
  → `reconcile_past_reservations`. **Zaman/cron tabanlı serbest bırakma YOKtu.** cutoff
  = aktif program start (yoksa bu haftanın Pazartesi'si) → cari hafta korunur (doğru).
- **Muhasebe SAĞLAM**: `diagnose_elif_reserves.py --all` (release-aware; eski
  `diagnose_section_progress_drift.py` BAYAT — `reservation_released_at`'i saymıyor,
  yanlış-pozitif drift verir). Prod: **drift 0, taslak-kilit 0**. AMA 4 öğrencide
  **64 ÖLÜ rezerv** takılıydı (yaz boyunca hiç tetik çalışmadı). Elif'in 5'i ise
  **cari hafta (06-22) taskleri** = doğru tutuluyor (bug değil); 06-29'da düşerdi.
- **Yan etki:** kitap "Kaldır" ucu `reserved_count>0` olunca 409 bloke → takılı ölü
  rezerv kitaplık temizliğini de kilitliyordu.
- **Kitaplık modeli:** `StudentBook`'ta arşiv/sınıf/yıl etiketi YOK; sınıf yükseltme
  (`grade_advance.apply`) kitaplara dokunmaz → eski kitaplar kalır. "Kaldır" = sert
  silme (geri alınamaz, rezervle bloke). Yaz-tekrar nüansı → körü körüne silme YANLIŞ.

**Kullanıcı kararları (AskUserQuestion):** rezerv = **günlük cron + mola modu** ·
kitaplık temizleme = **arşiv (geri alınabilir)** · başlangıç = **önce Elif teşhisi**.

- **Faz 0 — teşhis (CANLI doğrulandı):** `scripts/diagnose_elif_reserves.py`
  (`--student-id` / `--name` detay + `--all` sistem-geneli release-aware tarama).
  Prod'da çalıştırıldı (docker exec lgs-web), yukarıdaki bulgular kanıtlandı.
- **Faz 1a — günlük ölü-rezerv cron'u (CANLI):** `task_service.reconcile_all_active_
  reservations(today)` (rezervli her öğrenciyi tarar; per-öğrenci cutoff = aktif
  program start / bu Pazartesi — `create_program` ile AYNI; idempotent + release-only)
  + `cron_jobs.release_dead_reservations` + JOB_REGISTRY. **Migration `t4u7x0y1x33t`**
  (← `s2t5v8w9v11s`): cron seed (günlük 04:10 UTC; `enabled` bind-param `:e=True` —
  Postgres bool dersi, literal 1 DatatypeMismatch verir). Prod: worker ilk tick'te
  catch-up çalıştırdı → **64 ölü rezerv serbest** (sistem 131→67 rezerv, ölü 64→0,
  drift 0). Ölü rezerv düşünce kitap "Kaldır" kilidi de otomatik açılır.
- **Faz 1b — Mola modu / yaz molası (CANLI, MIGRATION YOK):** mevcut `is_paused`
  altyapısı yeniden kullanıldı (`is_paused`/`paused_at`/`pause_reason`/`pause_user`/
  `resume_user` + `_all_parent_student_pairs` zaten paused veli cron'larını atlıyordu).
  - `pause.REASON_SUMMER_BREAK="summer_break"` (maybe_auto_resume yalnız `auto_*`
    resume eder → öğrenci giriş yapsa bile mola sürer).
  - `task_service.release_due_reservations_for_pause` (cutoff=bugün+1 → cari hafta
    DAHİL serbest; gelecek görevler korunur) — Elif'i anında temizler + Kaldır açar.
  - **`analytics.generate_warnings` paused→`[]` TEK chokepoint**: `student_snapshot`
    bunu kullandığından durum özeti + öğrenci listesi rengi + uyarı akışı + rozet
    hepsi susar. Dashboard fleet + liste risk drilldown ayrıca paused→"ok".
  - Endpoint'ler `POST /teacher/students/{id}/pause` + `/resume` (sahiplik 404;
    `StudentPauseResult` = brief + released_tests/items; `_invalidate_for_students`
    books dahil → Kaldır anında açılır). Mevcut Jinja `pause-alerts` AYRI (dead code).
  - **UI** (`student-tabs.tsx`): başlık "Yaz molası/Takibe devam" butonu (onaylı,
    rezerv serbest uyarısıyla) + "Yaz molasında" rozeti; Durum Özeti'nde mola bandı
    (verdict+uyarı+pozitif gizli); liste satırında "molada" rozeti. `is_paused`
    StudentBriefProfile + TeacherStudentListItem'a eklendi.
- **Test:** `test_summer_break_reserve_cron.py` **13/13** (cron past düşürür/cari
  korur/idempotent · mola cari haftayı da serbest · uyarı susar/geri gelir · resume
  rezervi geri yüklemez). Regresyon: carryover 20 · teacher_read 12 · teacher_students
  14 · warning_ack 11 · weekly_plan 14 · card_consistency 23 · alert_correctness 9 ·
  risk_grace 6 GREEN. tsc/eslint temiz. (run_gorev_checks'teki itemless_solved 0/0
  ÖNCEDEN bozuk — ilgisiz.)
- **CANLI doğrulama (2026-06-28):** prod head=`t4u7x0y1x33t` · cron seed enabled
  (success) · 64 ölü rezerv temizlendi · pause/resume 401 anon · site/login 200.
- **Elif notu:** 5 rezervi cari hafta → cron'la **06-29** düşer; **bugün** istenirse
  Elif'e "Yaz molası" anında temizler.
- **MOBİL:** Faz 1a backend → mobil otomatik faydalanır. Mola modu pause/resume
  uçları canlı; **mobil koç UI toggle'ı eklenmedi** (kolay follow-up, mobil-only, deploy yok).
- **SIRADA — Faz 2 (kitaplık arşiv) + Faz 3 (sınıf yükseltmede arşiv checklist'i):**
  `StudentBook.archived_at` (soft, geri alınabilir) + "Bitti/Arşivle" + "Arşivlenenler"
  filtresi; sınıf yükseltmede "eski sınıf kitaplarını arşivle?" tek-tek seçimli
  (yaz-tekrar nüansına saygı, körü körüne silme yok). [[feedback-holistic-change-propagation]]

---

## Kitap müfredat eşleştirme iyileştirme + TYT/AYT sınav omurgası — 2026-06-24, CANLI (commit `2a8fffb`)

**Bağlam (kullanıcı, Efe TYT Matematik kitabı):** 4K TYT Matematik kitabı eklendi
→ AI bölüm önerisi İYİ (gerçek 34 ünite doğru) ama **müfredat eşleştirme ~0**
(sadece "Olasılık" eşleşti). Kullanıcı "sistem sadece AYT'ye mi duyarlı?" sordu +
kitap-yükleme sürecini "kasko gibi tek akış"a bağlamak istedi. Önce SAĞLAM MANTIK
(analiz + simülasyon), sonra aşamalı kod (her aşama ayrı onay) kararı alındı.

**Kök neden (koddan + simülasyonla kanıtlı `scripts/sim_tyt_mapping.py`):**
- Eşleştirme adayları = `_accessible_topics(book.subject_id)` = kitabın bağlı
  olduğu **tek dersin** konuları. Efe 12.sınıf → KLASIK kohort → kitap "Klasik Lise
  Matematik"e bağlı → o derste **yalnız 11-12 (Trigonometri/Türev/İntegral = AYT)**
  konuları var; TYT 9-10 temelleri (Temel Kavramlar, problemler, Üslü/Köklü...)
  **sistemde HİÇ yok**. Okul-müfredatı (model+sınıf) ile sınav-taksonomisi (TYT/AYT,
  model-üstü) yapısal uyumsuz. + ikincil hata: auto-map "1. Ünite —" önekini
  temizlemiyordu → tam-adlı eşleşmeler bile AI'a düşüyordu.
- Simülasyon: Klasik Lise Mat 0/34 · TYT-kanonik+önek temizleme **30-32/34**.

**Kullanıcı kararları (AskUserQuestion):** bağlama modeli = **B (sınav omurgası)** ·
kapsam = **TYT + AYT Matematik** · kitap detayına **"Dersi değiştir"** ekle.

- **Aşama 1 — auto-map kalitesi (ücretsiz, kredisiz):** `curriculum_mapping.py`
  yeni eşleştirme-anahtarı katmanı: yayınevi/ünite öneki temizleme (`_label_key`:
  "1. Ünite —", "BS/TYT/AYT/Konu:") + bağlaç atma (ve/ile) + alias (OBEB OKEK=EBOB
  EKOK, üslü/köklü **ifadeler↔sayılar**). `normalize()` SAF kaldı (katman yalnız
  anahtar üretir). Resmi konu adına dokunulmaz (önek yalnız kitap etiketinden).
  `test_curriculum_mapping` **18/18**. NOT: tutucu — auto-map yalnız ÖNERİR,
  topic_id'yi koç "Uygula" ile set eder (madde 4 tutucu; library.py'ye dokunulmadı).
- **Aşama 2 — sınav-bazlı kanonik taksonomi:**
  - `curriculum_data.py` **`EXAM_CURRICULUM`**: "TYT Matematik" (34 konu) + "AYT
    Matematik" (12 konu), **model-bağımsız** (`curriculum_model=None`) + `exam_section`.
    Yaygın yayınevi adlarıyla yazıldı (auto-map uyumu yüksek). Okul müfredatı
    (Maarif/Klasik) SİLİNMEDİ — referans kalır.
  - `seed.py` **`seed_exam_curriculum`** (idempotent, düz topics, model=None);
    `main()`'e bağlandı → `start.sh` (`scripts.seed`) prod'da otomatik seed eder.
    **Migration GEREKMEDİ** (additive Subject/Topic satırları).
  - `curriculum_progress._applicable_subjects`: **YKS dedup** — lise/mezun
    öğrencide sınav dersi (TYT/AYT) tercih edilir, **okul karşılığı gizlenir**
    (Klasik/Maarif "Matematik" → "TYT/AYT Matematik" ile değişir); sınav karşılığı
    OLMAYAN okul dersi (Fizik vb.) aynen kalır → kademeli rollout güvenli.
    `_is_exam_subject`/`_exam_base_name` helper'ları. weekly_plan `all_subjects`'e
    DOKUNULMADI (exam dersleri orada da otomatik görünür; okul dersi de durur — düşük risk).
  - `SubjectRef.exam_section` (schema + library yanıtı) + frontend
    `subjects.ts groupSubjectsByCurriculum` → **"Sınav Müfredatı (TYT / AYT)"**
    ders grubu (book-create seçicide en üstte).
  - **Kitap detayı "Dersi değiştir"** (book-detail-client + page subjects fetch):
    PATCH `subject_id`; ders değişince eski müfredat eşleştirmeleri (topic_id)
    **sıfırlanır** (bölüm/ilerleme/rezerv KORUNUR), koç yeniden eşler. Mevcut
    kitapları (Efe'nin Klasik'e bağlı 4K) sınav omurgasına taşımanın yolu budur.
  - `test_curriculum_exam_taxonomy` **11/11** (seed idempotent + yapı + YKS dedup +
    gerçek TYT kitabı 30/34 auto-eşleşme).
- **Sonuç:** Efe TYT Matematik eşleşmesi **1/34 → 30/34** (AI'sız auto-map).
- **CANLI (commit `2a8fffb`):** push + `redeploy.sh` (git pull + DB yedek +
  `up -d --build`, web/worker/next). Prod doğrulandı: head=2a8fffb · seed çalıştı
  (TYT Matematik 34 konu · AYT Matematik 12 konu, model-bağımsız) · healthz 200.
  Regresyon: mapping 18 · progress 22 · units 10 · teacher_library 24/18 ·
  weekly_plan 14 · tsc/eslint temiz.
- **KULLANICI AKSİYONU (test):** (1) Efe'nin 4K kitabı → "Dersi değiştir" →
  **TYT Matematik** → "Müfredata eşleştir" (30/34 ön-dolu) → Uygula. (2) Yeni TYT/
  AYT kitapları artık "Sınav Müfredatı (TYT/AYT)" grubundan seçilir.
- **TÜM TYT/AYT DERSLERİ EKLENDİ — CANLI (commit `07d5801`, 2026-06-24):** kapsam
  Matematik'ten **20 sınav dersine** genişletildi (LGS/Maarif okul müfredatına
  DOKUNULMADI). TYT (10): Türkçe·Matematik·Geometri·Fizik·Kimya·Biyoloji·Tarih·
  Coğrafya·Felsefe·Din Kültürü. AYT (10, SAY: Mat·Geometri·Fiz·Kim·Biyo · SÖZ:
  Edebiyat·Tarih·Coğrafya·Felsefe Grubu·Din). ~261 konu, yaygın yayınevi/ÖSYM
  taksonomisi. Dedup eşanlam köprüsü `_SCHOOL_EXAM_SYNONYMS` (okul "Türk Dili ve
  Edebiyatı" ↔ sınav "Türkçe"/"Edebiyat"). `test_curriculum_exam_taxonomy` **13/13**
  (20 ders + her biri ≥5 konu). Prod doğrulandı (20 ders seedli, healthz 200).
  Migration YOK. **NOT:** konu listeleri standart ÖSYM/yayınevi taksonomisinden
  yazıldı (web doğrulaması rate-limit nedeniyle yapılmadı); bir ders sapmışsa
  Maarif iş akışındaki gibi `curriculum_data.py EXAM_CURRICULUM`'da tek tek düzeltilir.
- **Kütüphane liste filtresi fix — CANLI (commit `6e1a649`):** sınav dersleri
  (curriculum_model=null) liste sayfasında "Diğer"e düşüyordu → `library-list-client`
  `subjectCurriculumKey`/`bookCurriculum` "exam" kategorisi + müfredat çip-barına
  **"Sınav Müfredatı (TYT / AYT)"** çipi (Diğer'den önce). Frontend-only.
- **Aşama 3 — Kitap Ekleme Sihirbazı — CANLI (commit `05a944e`):** "Yeni kitap" artık
  adım-adım sihirbaz (`book-wizard-client.tsx`): **1 Bilgiler → 2 Üniteler → 3
  Eşleştirme → 4 Öğrenci → Özet**, üstte ilerleme çubuğu + her adımda sistem ne
  yaptığını anlatır. Adım 2 **akıllı varsayılan**: sınav dersinde (TYT/AYT) "Resmi
  konulardan ekle" önerilir (anında + otomatik eşli → adım 3 atlanır), diğerinde AI,
  ayrıca elle. Adım 3 katalogdan geldiyse "tümü eşli" atlar, AI/elle ise auto-map
  ön-dolu tablo. Mevcut uçların orkestrasyonu (yeni endpoint/migration YOK). Sekmeli
  kitap detayı (sonradan düzenleme) AYNEN durur. `BookCreateForm` `onCreated`/
  `submitLabel`/`hideCancel` ile sihirbazda yeniden kullanıldı. tsc/eslint temiz.
- **Tüm TYT/AYT dersleri — CANLI (commit `07d5801`):** 20 sınav dersi (TYT 10 + AYT 10),
  ~261 konu, model-bağımsız + exam_section. Kütüphane liste filtresine "Sınav
  Müfredatı (TYT/AYT)" kategorisi (commit `6e1a649`). Konu listeleri standart ÖSYM/
  yayınevi taksonomisinden (web-doğrulama rate-limit'le yapılamadı; sapan ders olursa
  `EXAM_CURRICULUM`'da tek tek düzeltilir).
- **AYT alan (track) filtresi — CANLI (commit `48952ea`):** `TRACK_AYT_SUBJECTS`
  (SAYISAL/EA/SÖZEL/DİL) + `exam_subject_visible_for_track`. TYT herkese; AYT yalnız
  alana uygun; alan yok (track None / 9-10) → gizleme yok. `_applicable_subjects`
  (müfredat paneli) + weekly_plan `all_subjects` (program ders seçici) ikisinde de.
  exam_taxonomy 20/20 (D1-D7) · progress 22/22 · weekly_plan 14/14.
- **Demo "Kitap Ekleme Sihirbazı" — CANLI (commit `f1b0c75`):** `book-add-coach`
  demosu (tek slug → ana sayfa + /teacher/library "Nasıl kullanılır" + /demos hepsini
  besler) yeni 4-adımlı sihirbaza göre yeniden üretildi (8 sahne + nav + meta +
  narration + 8 MP3 Gemini TTS "Kore" + demo_narrations.json snapshot). Akış: Bilgiler
  (Sınav Müfredatı ders grubu) → Üniteler (katalog önerilen/AI/elle) → Müfredat
  eşleştirme (otomatik) → Öğrenci + Özet → sonradan düzenleme.
- **MOBİL:** Sınav taksonomisi + track filtresi backend olduğu için mobil API'den
  OTOMATİK alır (mobil müfredat/ders yüzeyleri yeni dersleri görür, track sunucuda
  filtrelenir) → mobil kod değişikliği/yeni build GEREKMEDİ. Kitap ekleme sihirbazı +
  demo web-özel (mobil koç kütüphane yönetimi web'de — PARITY.md); mobilde karşılığı yok.
- **LGS + Maarif analizi + iyileştirmeler — CANLI (2026-06-25):** TYT/AYT'deki gibi
  gerçek auto-map ile performans ölçüldü (`scripts/sim_lgs_maarif_mapping.py`).
  **Bulgular:** LGS 8. sınıf (sınav) %100 (kusursuz); LGS 5-7 %8 (seed'de soyut
  Maarif "Tema:" adları, kitaplar geleneksel); Maarif lise resmi-adlı %100 /
  geleneksel-adlı %0 (o kitaplar TYT/AYT omurgasına ait — doğru tasarım).
  - **#1 Katalog sınıf filtresi (commit `2ea360c`):** TopicRef'e grade_level +
    sihirbaz "Resmi konulardan ekle"ye sınıf çipleri (sınıf-yayılan derslerde
    "hepsini ekle" taşması çözüldü).
  - **#3 Alias (commit `2ea360c`):** kareköklü↔köklü, 1./2. dereceden, ebob/obeb.
  - **#2 LGS 5-7 tema+alt-başlık (commit `83d6a57`):** LGS Matematik/Türkçe/Fen
    5-7 → öğrenme alanı (PARENT) + geleneksel konu (LEAF); 8. sınıf DÜZ topics
    **dokunulmadan korundu** (grade-8 eşleşmeleri sürer). seed.py artık bir derste
    hem topics hem units işler. `reseed_lgs_5_7.py` (idempotent, scoped: yalnız
    units'li LGS derslerinde stale 5-7 düz temaları siler) + start.sh. Prod
    doğrulandı (Mat g8-flat 12/leaf 39, Türkçe 12/23, Fen 7/20, stale 0; Sosyal
    dokunulmadı). LGS sim %78→%100 (6.sınıf 1/12→12/12). lgs_units 9/9.
    **Etki:** 5-7 kitap eşleşmeleri null'landı (yeniden eşlenir, auto-map artık
    çalışır); grade-8 korundu. Migration GEREKMEDİ (seed/reseed).
  - **DERS:** LGS karma taksonomi (5-7 Maarif tema / 8 geleneksel). Test kitapları
    geleneksel konu adı kullanır → leaf'ler geleneksel olmalı. 5-7 konu listeleri
    MEB öğrenme-alanı standardından yazıldı; kullanıcı spot-check edebilir
    (Maarif iş akışındaki gibi sapan ders `curriculum_data.py`'de düzeltilir).
- **Sosyal Bilgiler 5-7 (commit `048855e`, MEB-doğrulamalı):** sınıf (PARENT) +
  gerçek ünite (LEAF). MEB-doğrulanmış ünite adları (5: 7 öğrenme alanı; 6: Sosyal
  Bilgiler Öğreniyorum/Yeryüzünde Yaşam/İpek Yolunda Türkler/Ülkemizin Kaynakları/
  Ülkemiz ve Dünya/Demokrasinin Serüveni/Elektronik Yüzyıl; 7: İletişim ve İnsan
  İlişkileri/Ülkemizde Nüfus/Türk Tarihinde Yolculuk/Zaman İçinde Bilim/Ekonomi ve
  Sosyal Hayat/Yaşayan Demokrasi/Ülkeler Arası Köprüler). reseed otomatik kapsadı
  (prod: 20 eski tema silindi, 21 leaf, 0 stale). LGS sim %100 (64/64). **#2 artık
  Matematik+Türkçe+Fen+Sosyal'in tamamında bitti.**
- **Din + İngilizce 5-7 (commit `182bb5e`, MEB-doğrulamalı):** Din 5-7 → sınıf
  (PARENT) + ünite (LEAF, mevcut MEB-uyumlu konu). İngilizce 5-7 → sınıf + tema
  (LEAF); **5-7 önceden HİÇ YOKTU** (yalnız 8) → MEB ortaokul İngilizce temaları
  eklendi (6.sınıf web-doğrulandı; 5/7 2018 standart, 8 ile tutarlı). grade-8 KORUNDU.
  reseed otomatik kapsadı (prod: Din 15 eski tema silindi; İngilizce yoktu→eklendi).
  Prod: Din 15 leaf · İngilizce 30 leaf · stale 0. **#2 LGS 5-7 artık 6 dersin
  TAMAMINDA bitti** (Matematik/Türkçe/Fen/Sosyal/Din/İngilizce). 8. sınıf hepsinde flat+korundu.
- **MOBİL — kod değişikliği GEREKMEDİ (doğrulandı):** mobil ders listesi
  `/teacher/students/{id}/all-subjects` (track filtresi + exam sunucuda) + müfredat
  sekmesi `/curriculum` (unit_name + grade_level + leaf/parent, Maarif OTA'sından
  beri render ediliyor) → LGS yeni yapısı + track filtresi mobile API'den OTOMATİK
  yansır. Kitap sihirbazı/katalog/kütüphane web-özel. **Yeni EAS build/OTA gerekmez.**
- **KALAN (opsiyonel):** YDT (Yabancı Dil) eklenmedi. Maarif lise geleneksel-adlı
  kitap → TYT/AYT omurgası kullanılmalı (doğru tasarım).
- **DERS:** Test kitapları ÖSYM/yayınevi taksonomisiyle düzenlenir; okul müfredatı
  (Maarif tema/Klasik sınıf) omurgası TYT/AYT eşleştirmesi için yetersiz → sınav
  taksonomisi ayrı, model-bağımsız omurga olarak eklendi. Klasik sönümleniyor,
  sınav taksonomisi kalıcı. [[feedback-holistic-change-propagation]]

---

## Ödeme (iyzico) + Yasal sayfalar + ZeptoMail + İletişim Sağlığı — 2026-06-20

**Şirket kuruldu:** ETÜTKOÇ Akademi Kişisel Gelişim Özel Eğitim ve Öğretim
Hizmetleri Ltd. Şti. (Trabzon Tic. Sic. 26268 · MERSIS 0381113961000001 · Vergi
3811139610 Karadeniz V.D. · adres İskenderpaşa Mah. Gazipaşa Cad. Timurcıoğlu Apt.
No:12/6 Ortahisar/Trabzon · tel +90 505 673 85 61 · imza yetkilisi Avni Bektaş
münferiden, Serkan Aydın %33 ortak). **Tek kaynak `app/legal_info.py` COMPANY**.

- **Ödeme = iyzico** (analiz sonucu — mevcut entegrasyon hazır Ö1-Ö3, abonelik native,
  yeni şirkete kolay onay). Kurumsal üye işyeri başvurusu yapılıyor; CANLI key
  geldiğinde `.env`: IYZICO_API_KEY/SECRET + IYZICO_BASE_URL=https://api.iyzipay.com.
  **docker-compose web'e iyzico env BAĞLANDI** (eksikti). Faz 4 (otomatik yenileme/
  iyzico Abonelik) hâlâ kalan tek ödeme parçası.
- **Yasal sayfalar (iyzico + KVKK zorunlu) — CANLI** (commit `c16e98d`): yeni Jinja
  public sayfalar `/mesafeli-satis` · `/iade-iptal` · `/kullanim-sartlari` (+ `kvkk/
  _seller_box.html`); hepsi `legal_info.COMPANY`'den beslenir. `/kvkk` veri sorumlusu
  resmi ünvana güncellendi. Anasayfa footer: yasal linkler + şirket kimlik bloğu.
  Caddy DEFAULT FALLBACK FastAPI → yeni yollar otomatik Jinja (Caddyfile değişmedi).
- **E-posta = ZeptoMail (işlemsel) — CANLI** (Phase 1): Hotmail 451 IP-reputation
  sorunu = Zoho Mail paylaşımlı SMTP. Çözüm ZeptoMail (temiz IP, aynı domain,
  DKIM+bounce CNAME Cloudflare'de doğrulandı). Prod `.env`: SMTP_HOST=smtp.zeptomail.com
  PORT=587 USER=emailapikey PASSWORD=<token 144 char> FROM=rotam@etutkoc.com.
  Gönderim kodu generic SMTP → sadece config. Gmail gelen kutusu + prod uçtan uca
  doğrulandı. **rotam@etutkoc.com posta kutusu Zoho'da kalır** (insan-posta ≠ işlemsel).
  Google Workspace YANLIŞ araç (posta kutusu, işlemsel değil) — kullanılmadı.
- **İletişim Sağlığı Faz 2a — CANLI** (commit `e4d7ce7`, migration `p9q2t5u6t88o`):
  birleşik `communication_logs` (e-posta/push/whatsapp/sms TEK gözlem kaydı —
  ne/kime/ne zaman/durum). channel/status düz VARCHAR (enum migration'sız).
  `app/services/comm_log.py` merkezi best-effort logger (db verilirse SAVEPOINT,
  yoksa kendi SessionLocal → SQLite tek-yazar kilidi yok). 4 kanca: **send_email**
  (27 işlemsel mail dahil + Message-ID bounce eşleşmesi için) · **send_push_to_user**
  (sent/no_device/failed) · **send_sms** · **build_wa_dispatch** (spam-guard log'undan
  AYRI ayna). Mevcut NotificationLog + whatsapp_dispatch_logs'a DOKUNULMADI.
  `test_comm_log.py` **28/28** (4 kanal gerçek fonksiyon + izolasyon + maskeleme).
  Prod: head=p9q2t5u6t88o, gerçek email→zeptomail→comm_log status=sent doğrulandı.
- **İletişim Sağlığı Faz 2c — CANLI** (commit `bb8dfb3`, migration YOK): süper admin
  `/admin/communication-health` — 4 kanal tek ekran. `communication_health.py`
  (get_overview kanal başına 24s+N günlük durum kırılımı + başarı % · list_logs
  filtreli/sayfalı). 2 endpoint: `/admin/communication-health` + `/communication-log`
  (channel/status/days/q/category/page/limit). Frontend: kanal kartları (tıkla→filtrele)
  + filtreli tablo (zaman/kanal/tür/alıcı/konu/durum + durum dropdown + arama debounce
  + sayfalama, kontrast-güvenli). admin-shell "Güvenlik Kamarası → İletişim Sağlığı".
  `test_api_v2_admin_communication_health.py` **10/10**. Prod: endpoint 401 anon ·
  sayfa 307. (Mevcut `/security-monitor/notifications` matrisi ayrı duruyor.)
- **İletişim Sağlığı Faz 2b — CANLI** (commit `ddd7bed`, migration YOK): ZeptoMail
  bounce/teslimat webhook `POST /webhooks/zeptomail` → comm_log DELIVERED/BOUNCED.
  `comm_log.apply_email_event` (Message-ID veya alıcı+en yeni 'sent' eşleşmesi;
  delivered yalnız 'sent' iken, bounced'ı ezmez). Savunmacı parser (event_message/
  details biçim varyasyonları). Güvenlik: `ZEPTOMAIL_WEBHOOK_SECRET` → URL `?token=`.
  Caddy `/webhooks/*` zaten FastAPI. `test_zeptomail_webhook.py` **11/11**. Prod:
  GET ping 200, POST updated:0. **KULLANICI AKSİYONU:** ZeptoMail Mail Agent →
  "Web Kancaları" → URL `https://rotam.etutkoc.com/webhooks/zeptomail` (+ secret
  kullanılacaksa `?token=...` + .env'e ZEPTOMAIL_WEBHOOK_SECRET) + bounce/delivery
  olayları seç. **İletişim Sağlığı (2a+2b+2c) TAMAMLANDI.**
- **Spam şikayeti + açılma** (commit `12f92ac`, migration YOK): yeni
  `STATUS_COMPLAINED` "Şikayet (spam)" (FAILURE grubu → sağlık % düşer) +
  `STATUS_PRECEDENCE` (webhook yalnız daha kesin duruma yükseltir). Webhook
  feedback_loop/fbl/complaint → complained; email_open → delivered (ZeptoMail'de
  "Email open" + "E-posta İzleme" açılırsa). Kanal kartında "Şikayet" sayımı (turuncu).
- **Abuse alarmı yanlış-pozitif düzeltmesi** (commit `9e9f55a`, migration YOK):
  süper admine her gün gelen "Açık abuse sinyali" alarmı dev gürültüsüydü
  (multi_account_same_device, hepsi 'info'; kaynak: kendi test girişleri + curl
  smoke). `detect_multi_account_same_device` bot/test UA'ları dışlar (curl/python/
  httpx/wget/postman/testclient… ILIKE; super_admin+impersonation zaten dışlıydı).
  `_val_abuse_open` yalnız warn/critical sayar (info email atmaz, panelde görünür).
  Prod'da 4 mevcut false-positive çözüldü → abuse_open=0. **DERS:** abuse alarmı
  eşik=0 + info dahil olunca dev trafiği alarm körlüğü yaratıyordu; tespit ≠ email.

---

## Kampanya & Teklif Orkestrasyonu (Aksiyon Merkezi + Üyelik Teklifi + WhatsApp) — 2026-06-21, DEVAM EDİYOR

**Vizyon (kullanıcı):** Aksiyon Merkezi (ne yapmalıyım) + Üyelik Teklifleri (kişiye
özel teklif) + **WhatsApp Business Cloud API** (kurumsal başlıklı, sigortam.net tarzı
görsel-başlıklı, mavi-tik) tek orkestrasyonda. Hedef: sistem kullanıcıları (koç/kurum)
+ **sistem-dışı prospect'ler** (rehber/eklenen kurum) → tanıtım + kişiye özel teklif →
WhatsApp branded mesaj → `/membership/{token}` → paket seç → Iyzico ödeme (web tarafı VAR).

**Mevcut envanter (keşif):** Cloud API client `whatsapp.py send_template` (görsel başlık
+ buton component destekli) **VAR, stub modda**. webhook (teslim/okundu) VAR. membership
offer + markalı `/membership` sayfası + Iyzico VAR. Aksiyon Merkezi sinyalleri (trial
≤2g kritik → "dönüşüm görüşmesi"+"uzatma teklifi %20", 3-7g → "geri sayım e-postası";
past_due) → ama **öneri+CRM log; otomatik göndermiyor**. Eksik halka: branded gönderim
+ aksiyon-merkezi/teklif birleşimi + sistem-dışı hedef.

- **K1a — Hedef Havuzu ✅ CANLI** (commit `6063b02`, migration `q0r3u6v7u99p`):
  `sales_prospects` (üye olmayan kurum/koç adayı: ad+telefon+kind+org+opt-in+status
  hunisi) + `membership_offers.target_prospect_id` (batch FK). `prospect_service`
  (E.164 normalize + dedup) + `admin_prospects` router (CRUD+status) + `/admin/prospects`
  UI (durum filtre + tablo + wa.me manuel + create/edit). `test_api_v2_admin_prospects`
  12/12. admin-shell "Ticari Pano → Hedef Havuzu".
- **Faz 0 — Meta doğrulama (KULLANICI, paralel):** `deploy/META_WHATSAPP_SETUP.md`
  rehberi yazıldı. Business verification (Ltd) + WABA + numara + görsel-başlıklı
  Marketing template onayı. Anahtarlar `.env`'e (WHATSAPP_*), şablon adı sisteme.
- **Dedup fix ✅** (commit `8feb396`): `institution_360.create_action(dedup=True)` —
  quick-action öneri butonuna mükerrer basışta aynı owner+kind+summary için açık
  'Bekliyor' aksiyon varsa tekrar yaratmaz (manuel "Yeni Aksiyon" formu dedup=False).
- **K1b — prospect'e kişiye özel teklif ✅ CANLI** (commit `8feb396`, migration YOK):
  `membership create_offer` `target_prospect_id` alır (public_view prospect adını çözer).
  `POST /admin/prospects/{id}/offer` → markalı `/membership` linki + hazır wa.me mesajı
  + prospect 'contacted'. Hedef Havuzu meta'ya satılabilir planlar. Frontend: prospect
  satırı "Teklif" (Gift) → OfferDialog → sonuç link + "WhatsApp'tan gönder" + kopyala.
  `test_api_v2_admin_prospects` 15/15. **Grup senaryosu:** Cloud API gruba GÖNDEREMEZ;
  grup = markalı kampanya linki elle paylaş (Yol A), birey = 1:1 branded template (K2).
- **Meta-öncesi 3 düzeltme ✅ CANLI** (commit `3ec751d`, migration YOK):
  **A)** Membership landing kazanç — `public_view` list_price/savings/discount_pct →
  çizik liste fiyatı + "Sana özel %X · N₺ tasarruf" (amount<liste olunca).
  **B)** Contact request veri uyumu — `_contact_identity` prospect'i tanır (gerçek
  ad/eposta/telefon, placeholder değil); `_offer_summary` hedef_tip+aday_id+tutar.
  **C)** Dinamik onboard — `_contact_item` membership_offer parse (target_kind koc/
  kurum + plan + tutar + aday); İletişim Talepleri koç/kurum ayırır; yeni
  `POST /contact-requests/{id}/onboard-coach` (koç hesabı + solo plan + ödeme linki +
  e-posta + prospect=member); frontend target_kind=coach → "Koç Aç + Aktive Et"
  dialog, kurum → "Kurum Aç + Aktive Et". Inline uçtan uca + regresyon temiz.
- **3 düzeltme (deploy sonrası, 2026-06-21):** (A) eski membership_offer talepleri
  `hedef_tip` yoksa `_contact_item` plan tipinden koç/kurum türetir (commit `240e547`);
  (B) **membership savings API'de görünmüyordu** — `public_view` alanları vardı ama
  `MembershipPublicResponse` şeması taşımıyordu → Pydantic kırpıyordu; 3 alan eklendi
  (commit `b5a8cd8`); (C) **onboard dialog unmount** — başarı sonrası talep closed→tablo
  yenilenince dialog (link gösteren) unmount oluyordu → dialog her zaman mount + trigger
  `canOnboard` gate (commit `784a7cc`). + **KÖK NEDEN:** prod `auditaction` enum'unda
  PAYMENT_*/TESTIMONIAL_MODERATE değerleri eksikti → tüm ödeme linki oluşturma 500;
  ALTER TYPE ADD VALUE ile eklendi. [[feedback-postgres-enum-new-member-migration]]
- **Ödeme-linki havale fallback ✅** (commit `e6bcaa4`): `/payment/link/{token}` iyzico
  kapalıyken (`provider_available=false`) "Şimdi Öde"ye basınca çiğ hata veriyordu →
  provider-aware: iyzico açık → "Şimdi Öde" (3DS), kapalı → havale/EFT bilgisi (membership
  ile aynı kaynak) + "kartlı ödeme yakında". Key girilince otomatik döner.
- **Yol A — Kampanya/Genel Link ✅ CANLI** (commit `3c3b1db`, migration `r1s4u7v8u00r`):
  Cloud API gruba mesaj atamadığından admin tekrar kullanılabilir markalı landing
  oluşturur (1:çok) → WhatsApp grubuna paylaşır → tıklayan plan/fiyat/kazanç görür +
  ad+telefon bırakır → `SalesProspect` (lead, dedup) + `ContactRequest` (source=
  campaign_link, hedef_tip/hedef_kod/aday_id encode) → İletişim Talepleri'nde mevcut
  **Koç/Kurum Aç + Aktive Et** akışına akar. `campaign_links` (token+plan+amount+
  audience+status+view/lead sayacı) + `campaign_link_service` (membership/pricing tek
  kaynak reuse) + public router (`GET /campaign/{token}` + `POST /lead`) + admin router
  (create/list/status). Frontend: public `/kampanya/[token]` (markalı landing + lead
  formu, force-light, OG meta) + admin `/admin/campaign-links` (oluştur+liste+kopyala/
  WA paylaş+duraklat/arşivle) + admin-shell "Kampanya Linkleri". `test_api_v2_campaign_link`
  **17/17**. proxy allowlist + Caddy `/kampanya/*`. Prod: head=r1s4u7v8u00r · page 200 · admin 307.
- **K2 — Cloud API branded gönderim ✅ KOD CANLI (Meta onayı bekliyor)** (commit `d9025e8`,
  migration `s2t5v8w9v11s`): Meta API doğrulandı (hello_world). Onaylı `uyelik_teklifi`
  şablonu (görsel başlık + ad/plan/tutar + "Teklifi Gör" buton → `/membership/{token}`)
  ile DOĞRUDAN branded gönderim (mavi tik), manuel wa.me'den AYRI. `whatsapp.send_template`
  zaten gerçek (httpx→graph.facebook.com); `whatsapp.is_enabled` public + config
  `whatsapp_offer_template`/`whatsapp_offer_image_url`. `membership_offer_service.send_via_whatsapp`
  (telefon çöz + component kur + gönder + comm_log + offer.wa_sent_at/wa_message_id izi +
  prospect contacted). `comm_log.apply_whatsapp_event` (webhook teslim/okundu/hata →
  İletişim Sağlığı; NotificationLog'tan AYRI). `whatsapp_webhook` her status'te comm_log
  günceller. Endpoint `POST /admin/membership-offers/{id}/send-whatsapp` (403/409 disabled/
  422 no_phone/502 send_failed/404). Liste +whatsapp_enabled +wa_sent. docker-compose
  web+worker'a WHATSAPP_OFFER_* env. Frontend: admin membership listesinde "Cloud API gönder"
  (cyan, anahtar dolu+telefon var) + "WhatsApp gönderildi" rozeti; wa.me "Manuel" kalır.
  `test_api_v2_membership_whatsapp` **13/13**. **Stub modda çalışır; aktive için
  KULLANICI:** (1) Meta'da `uyelik_teklifi` şablonu oluştur+onaylat (Marketing/tr, IMAGE
  header + body {{1}}ad {{2}}plan {{3}}tutar + URL buton `https://rotam.etutkoc.com/membership/{{1}}`),
  (2) kalıcı System User token üret, (3) prod `.env`: WHATSAPP_PHONE_NUMBER_ID + ACCESS_TOKEN +
  APP_SECRET + WEBHOOK_VERIFY_TOKEN + WHATSAPP_ENABLED=true → `up -d web worker`, (4) Meta
  webhook URL `https://rotam.etutkoc.com/webhooks/whatsapp` + verify token. İşletme
  doğrulaması "Değerlendirmede" (1-3 gün). **K3** — dönüşüm takibi (kalan).
- **⚠️ Politika:** Cloud API marketing = opt-in/kalite kuralı; soğuk toplu → numara
  kısıtlanır. prospect.opt_in işareti + düşük hacim başlangıç. Maliyet: konuşma başı
  (kullanıcı kabul etti). [[project-ai-credits-packaging]]

---

## Koyu tema kontrast/okunabilirlik — sistemik fix (Faz 1-3) — 2026-06-20, CANLI

**Bağlam (kullanıcı, ekran görüntüleri):** Admin panellerinde koyu temada metin/kart
okunabilirliği düşüktü (tekrarlayan "kontrast" bug'ı). Kökten + tekrarsız çözüldü.
- **Faz 1 — regresyon kalkanı:** `eslint.config.mjs`'e yeni `lgs/no-unsafe-contrast`
  kuralı (aynı className string'inde `bg-*-50/100` + `text-foreground|muted-foreground`
  → koyu temada görünmez metin). Mevcut ihlal 0 (geçmiş düzeltmeler temizlemiş);
  kural yeni eklenmeyi engeller. (4. lgs kuralı.)
- **Faz 2 — sistemik token:** `globals.css` `.dark` → `--muted-foreground` L65→L74
  + `--border` L25→L30. **Tek değişiklik TÜM koyu-mod soluk metni** (footnote/empty/
  tablo) global iyileştirir. + Ticari Pano açık KPI kartlarına `dark:` varyantı.
- **Faz 3 — sweep (codemod):** aynı className'de `bg-{c}-50` + `border-{c}-200`
  (gerçek kart üçlüsü) olan **100 dosya / 373 className** → `dark:bg-{c}-500/10
  dark:border-{c}-500/30` (+ koyu metin varsa `dark:text-{c}-200`). Rozet/hover/
  gradient'e dokunulmadı. force-light sayfalarda dark: inert.
- **KURAL (yeni standart):** Açık tonal KART = `bg-{c}-50 border-{c}-200 text-{c}-900`
  **+ daima** `dark:bg-{c}-500/10 dark:border-{c}-500/30 dark:text-{c}-200`. Açık
  dolgu + tema-token metin (`text-foreground`) ASLA birlikte (lint yakalar). Soluk
  metin için tema token'ı (`text-muted-foreground`) kullan — global L74 ayarlı.
  Commit'ler `d5149ff` (Faz1+2) · `948cf8b` (Faz3). tsc/eslint temiz, next rebuild.
  [[feedback-holistic-change-propagation]]

---

## Öğrenci-bazlı Müfredat İlerleme + Yetişme Projeksiyonu (Faz 0-4) — 2026-06-19, CANLI

**Bağlam (kullanıcı):** Koç program hazırlarken öğrencinin müfredatta NEREDE
olduğunu (hangi konular işlendi, sırada ne, sınava yetişir mi) tek bakışta
görmeli. Hibrit omurga onaylandı: **resmi konu sırası (Topic.order) + eşleşmemiş
ekstra**. Yapay zekâ entegre edildi (Gemini önceliklendirme + içgörü). Tüm
fazlar bitti; demo + 5-öğrenci uçtan uca test + canlı deploy + mobil OTA yapıldı.

- **Faz 0 — kütüphane→müfredat eşleştirme** (`curriculum_mapping.py`): kitap
  section'larını resmi Topic'lere bağlar (normalize auto-map + Gemini öneri,
  `_AI_BATCH=12` + max_output_tokens=16384 — 2.5 düşünme tokenı JSON kesmesin).
  Modal `curriculum-mapping-modal.tsx` (valueFor = override ?? current ??
  suggested, seed YOK). `test_curriculum_mapping` 11/11.
- **Faz 1 — ilerleme haritası** (`curriculum_progress.py` `compute_curriculum_
  progress`): ders bazlı sıralı konu + durum (kaynak_yok/baslanmadi/planlandi/
  devam/tamamlandi) + coverage% + frontier (son işlenen/sıradaki) + eşleşmemiş
  ekstra. `applicable_subjects` = covers_grade + effective_curriculum_model +
  ad-dedup. Web "Müfredat" sekmesi (`curriculum-panel.tsx`).
- **Faz 2 — sıradaki atanabilir üniteler** (`next_units_for_assignment` + AI
  `ai_prioritize_units` Gemini personal_data=True): haftalık plan aside'ında
  `next-units-panel.tsx` (AI önceliklendir + AssignDialog gün/section/sayı →
  görev). `UsageKind.AI_CURRICULUM_PRIORITY` = 4 kredi (_require_ai_premium +
  consent). 
- **Faz 3 — son işlenen üniteler** (`recently_covered_units`): seans prefill'e
  `recent_units` + KS4 içgörü prompt'una "son 7 günde işlenen üniteler".
- **Faz 4 — sınava yetişme projeksiyonu** (`_compute_projection`): hız = son 14
  günde işlenen FARKLI konu / 2 hafta; tahmini kapsama = işlenen + hız×kalan
  hafta. **Eşikler GERÇEKÇİ** (kullanıcı kararı sonrası ayar): %100 kimse
  bitirmez → yetisir≥%90 / risk≥%70 / yetismez<%70 (pace=0 → yetismez) /
  sinav_yok / veri_yok. Web `ProjectionCard` (verdict rozeti + gün/kalan/tempo +
  tahmini kapsama barı). `test_curriculum_progress` **22/22**.
- **Demo + 5-öğrenci test** (`scripts/seed_demo_curriculum.py`, idempotent,
  --reset): her builtin ders için topic-eşli demo kitap (ad müfredat modeliyle
  BENZERSIZ — Matematik LGS/klasik/maarif çakışmasını çözer) + 5 profil. Uçtan
  uca doğrulama: Ayşe(g8,68%,aktif)→yetisir · Burak(g8,18%,durgun)→yetismez ·
  Ceren(g12,51%,sınav yarın)→yetismez · Deniz(g11,sınav yok)→sinav_yok ·
  Emre(g12,83%,sınav yarın)→risk. Her verdict doğru profille eşleşti.
  start.sh'e EKLENMEDİ (yalnız demo/test). NOT: projeksiyon OVERALL (tüm
  uygulanabilir dersler), tek ders değil.
- **Migration GEREKMEDİ** (topic_id mevcut, usage_events.kind plain VARCHAR).
  Commit'ler `888873b`(Faz3)·`a6b5d87`(Faz4)·`3013fa2`(demo+eşik). **CANLI**
  (web+next rebuild, OOM-güvenli; healthz 200 · /curriculum 401 · site 200).
- **MOBİL koç Müfredat sekmesi + OTA** (commit `5ebd6f4`): `teacher-student`
  detayına "Müfredat" sekmesi (web paritesi: kapsama + projeksiyon + ders
  accordion + ekstra; `curriculum-tab.tsx` + lib/teacher tipleri/fetcher).
  JS-only → **EAS OTA `update --channel production` ile yayınlandı** (runtime
  1.0.0 = v6 install'lara YENİDEN YÜKLEME OLMADAN düşer — OTA mekanizması uçtan
  uca doğrulandı, update group `796d6748`). + yeni **AAB v7** (versionCode 6→7
  autoIncrement) `eas build` ile kuyruğa alındı (build `4d4990c5`, Expo cloud
  ~15-20dk; kullanıcı EAS dashboard'dan indirir). Mobil tsc temiz.
  **DERS — OTA vs yeni AAB:** runtimeVersion=appVersion=1.0.0 sabit kaldığı için
  JS-only özellikler `eas update`'le store'suz dağıtılır; yeni AAB yalnız native
  değişiklik veya yeni store baseline için. v7 AAB de runtime 1.0.0 → OTA uyumlu.

---

## Maarif müfredatı resmi MEB tema/ünite + alt başlık yapısına taşındı — 2026-06-19, CANLI

**Bağlam (kullanıcı, Müfredat sayfası ekran görüntüsü):** 10. sınıf Maarif
müfredatındaki konular YANLIŞ/EKSİKti (örn. Biyoloji 10 "Ekoloji" teması komple
yok, "Üç Âlem Sistemi ve Biyoçeşitlilik" uydurma; "diğer derslerde de benzer
sorunlar"). **Kritik düzeltme (yanlış anlama):** bu konuları **Gemini ÜRETMEDİ**
— `scripts/curriculum_data.py`'ye ELLE yazılmıştı (2026-05-08 Lise/YKS genişlemesi,
yeni Maarif modeli hatalı/eksik girilmiş). Gemini yalnız Faz 0'da kitap→konu
EŞLEŞTİRMESİ yapar; konu listesini yazmaz. Müfredat sayfası seed verisini sadık
gösterir → çöp girer çöp çıkar.

**Detaylı web doğrulaması (6 paralel subagent, YALNIZ resmi tymm.meb.gov.tr):**
10 Maarif dersi (9-12) resmi onaylı programlardan çıkarıldı. **Terminoloji ders
bazında değişir** (kullanıcı haklı): Biyoloji/Kimya/Matematik/Edebiyat=**Tema**,
Fizik/Tarih/Coğrafya/Felsefe/Din=**Ünite**, İngilizce=**Theme**. Az temalı dersler
(Biyoloji 10 = 2 tema) aslında zengin alt başlıklı (Enerji→ATP/Fotosentez/Solunum/
Fermantasyon/Sindirim) — test kitapları bu alt başlıklarla düzenlenir.

**Kullanıcı kararları (AskUserQuestion):** granülerlik=**Hibrit** (tema zorunlu +
alt başlık; sonra "tema ve alt başlıkları KESİNLİKLE görmek istiyorum" → her yerde
alt başlık) · kapsam=**Yalnız Maarif** · eşleştirme=**Otomatik yeniden eşleştir**.

- **Veri:** `curriculum_data.py` MAARIF_LISE tamamen yeniden yazıldı — **175 tema/
  ünite + 468 alt başlık**, `units` formatı `(no, ad, sınıf, [alt başlıklar])`,
  `unit_term` ile resmi terim korunur.
- **Yapı (migration YOK):** `Topic.parent_id` (mevcut, kullanılmıyordu) → tema/ünite
  = PARENT topic (ad "1. Tema: Enerji"), alt başlık = CHILD (parent_id). Kitap
  bölümü LEAF'e eşlenir; tema parent'ı eşleştirme adayı DEĞİL.
- **seed.py:** `units` formatını işler (parent + child). `reseed_maarif_curriculum.py`:
  eski Maarif topic'leri sil + etkilenen `book_section.topic_id` NULL (Faz 0 re-map)
  + yeni yapı. **İDEMPOTENCY GUARD** (stale=parent_id NULL ama çocuksuz düz konu var
  mı) → start.sh'e eklendi: eski veriyi BİR KEZ düzeltir, temizse ATLAR (koç
  eşleştirmelerini re-null'lamaz). Prod start.sh: 756 karışık (113 stale) → 643 temiz.
- **Servis:** `compute_curriculum_progress` LEAF sayar + parent'ı `unit_name` olarak
  ekler. `_accessible_topics` (library+teacher_books) yalnız LEAF önerir.
- **UI:** web `curriculum-panel` + mobil `curriculum-tab` tema başlığı (unit_name
  değişince) + nested alt başlık. Schema `CurriculumTopicItem.unit_name`.
- **Test:** `test_curriculum_units` **10/10** (leaf sayım + parent hariç + unit_name +
  eşleştirme adayı leaf) · curriculum_progress 22/22 · mapping 11/11 · library 24/18.
- **CANLI (commit `9395887`):** web+worker+next rebuild; prod reseed otomatik
  (start.sh guard) — **643 Maarif topic (175 tema + 468 alt başlık)**, 38 gerçek
  kitap eşleştirmesi NULL'landı (koçlar Faz 0 ile yeniden eşler). Biyoloji 10 artık
  Enerji+Ekoloji temaları doğru (prod'da doğrulandı). Mobil JS-only → **EAS OTA
  `update --channel production`** (runtime 1.0.0, group `254c8e24`).
- **DERS:** Müfredat konuları kod-seed'dir (AI değil) — yanlışsa `curriculum_data.py`
  düzeltilir. Yeni model (Maarif) verisi resmi MEB kaynağından doğrulanmalı; eski
  seed yaklaşıktı. parent_id ile tema gruplama migration'sız mümkün.

**Müfredat sayfası 2 düzeltme + auto-remap (2026-06-19, kullanıcı bildirdi, CANLI):**
- **Sınıf başlığı:** Maarif tema adları her sınıfta tekrar ediyor (örn. "1. Tema:
  Sayılar" hem 9 hem 10) → sınıf bağlamı yoktu, tekrar ediyormuş gibi görünüyordu.
  `TopicProgress.grade_level` + UI **"N. Sınıf" başlığı** (grade değişince) tema
  adlarını ayırır.
- **Sınıf filtresi (kullanıcı):** tüm müfredatı 12'ye kadar göstermek mantıksız →
  `compute_curriculum_progress` leaf'leri **öğrencinin sınıfına kadar** (kümülatif,
  `grade<=grade_level`; mezun/None→tümü) filtreler. 10. sınıf → yalnız 9-10.
- **Auto-remap** (`remap_maarif_books.py`): reseed'de kopan eşleştirmeler (prod 38
  bölüm/11 kitap) deterministik + ücretsiz-key Gemini ile **otomatik yeniden eşlendi**
  (7 det + 30 AI = 37/40; 3 koça kaldı). Elif (student 34) artık kaynaklı.
- **AI parse fix:** `curriculum_mapping._ai_suggest_batch` Gemini'nin dizi-şekilli
  yanıtında ("'list' object has no attribute 'get'") patlıyordu → obje+dizi ikisi de
  kabul. Commit `251b8a5`. Web+mobil OTA (runtime 1.0.0). [[feedback-holistic-change-propagation]]

---

## YENİ İŞ — Öğrenci Tanıma Anket/Envanter Sistemi (2026-06-11, KARARLAR ALINDI, kod BAŞLAMADI)

**Bağlam:** Koç, öğrencisini tanımak için anket uygular (çoklu zeka, ilgi envanteri,
yaşam çarkı, SWOT, mesleki beceri...). Koç sistemden anketi öğrenciye gönderir →
öğrenci doldurur (mobil öncelikli!) → sonuç anında koça düşer. Literatür + koçluk
platformu taraması yapıldı (2026-06-11).

**Kullanıcı kararları (2026-06-11, AskUserQuestion):**
1. **Telif stratejisi = özgün + serbest kaynak**: Çerçeveler telifsiz ama madde
   metinleri telifli → yaygın çerçevelerle (çoklu zeka 8 alan, RIASEC 6 tip,
   VAK 3 stil, yaşam çarkı 8 dilim, SWOT) **ETÜTKOÇ'a özgü maddeler** yazılır
   (Claude taslak → kullanıcı onayı) + public domain olanlar (O*NET Interest
   Profiler CC BY 4.0, IPIP) Türkçeleştirilip atıfla alınır. MBTI/Kolb/VARK/16PF
   gibi lisanslı markalara GİRİLMEZ. TOAD'daki akademik ölçekler izinsiz KULLANILMAZ.
2. **Çekirdek set = 10 anket (4 grup)**: Tanıma 4'lüsü (Çoklu Zeka + Öğrenme
   Stilleri + Yaşam Çarkı + SWOT) · Sınav 2'lisi (Sınav Kaygısı + Çalışma
   Alışkanlıkları) · Kariyer 2'lisi (Mesleki İlgi RIASEC + Akademik Benlik) ·
   Motivasyon 2'lisi (Başarısızlık Nedenleri + Hedef/Motivasyon).
3. **Mimari = B motoru, fazlı C**: Genel anket motoru (soru tipleri: likert5/
   çoktan seçmeli/1-10 kaydırıcı/açık uç + boyut-bazlı skorlama + rapor şablonu
   radar/çark/kadran); hazır anketler motorun üstünde **idempotent seed**
   (whatsapp_templates deseni, süper admin düzenleyebilir). Faz 1: motor +
   10 hazır anket + koç gönder/sonuç + öğrenci doldurma (web+MOBİL) + görsel
   rapor. Faz 2: koç özel anket + veli anketi (token'lı). Faz 3: AI anket
   taslağı + **AI sonuç yorumu (kredili, KS4 deseni: GET ücretsiz cache /
   POST kredi, yalnız ücretli paket)**.
4. **Konumlandırma**: "psikolojik test" DEĞİL "koçluk amaçlı tanıma anketi" —
   rapor ekranlarında sabit ibare (test uygulama yetkisi PDR/psikolog meselesi).

**KARİYER KEŞİF eklemesi (kullanıcı 2026-06-12 — kritik):** Öğrencilerin çoğu
hangi mesleğe yatkın olduğunu bilmiyor; koçun hedef belirleme çalışmasının en
önemli girdisi beceri×ilgi denklemi. Karar: (a) **Beceri Seti Öz-Değerlendirme**
11. anket olarak çekirdek sete eklendi (8 beceri boyutu — ifade/analitik/problem/
yaratıcılık/sosyal/liderlik/teknik/dijital); (b) **AI Kariyer Sentezi** (sıradaki
paket): Gemini, RIASEC ilgi + Beceri Seti + Akademik Benlik + Çoklu Zeka sonuçlarını
sistemdeki GERÇEK akademik veriyle (deneme netleri, konu performansı) birleştirip
3-5 meslek/bölüm önerisi + YKS alan uyumu + koç için hedef-belirleme seans gündemi
üretir. KS4 deseni: cache'li, GET ücretsiz / POST kredili, ücretli paket; yeni
anket sonucu → stale. AI test SORMAZ — anketler ölçer, AI sentezler.

**FAZ 1 BACKEND+WEB ✅ (2026-06-12, migration `h1i4l7m8l55c` — head):**
- **Migration `h1i4l7m8l55c`** (down_revision g0h3k6l7k44b): survey_templates +
  survey_questions + survey_assignments. Additive, downgrade'li, uygulandı.
- Model `app/models/survey.py` (3 model + kategori/skorlama/qtype/durum sabitleri
  + `SURVEY_DISCLAIMER_TR` sabit ibare). Servis `survey_service.py` (TEK MERKEZ:
  compute_scores [dimensions likert5 (avg-1)/4·reverse 6-v / wheel slider10 /
  qualitative bloklar] + build_result [boyut etiket+level+high_is_good+yorum
  bandı] + save_answers [kısmi kaydet → in_progress; complete → doğrula+skorla]
  + has_open_assignment). AI Kariyer Sentezi skorları buradan okuyacak.
- Router `api_v2/surveys.py` (8 uç): koç catalog / students/{id}/surveys GET+POST
  (mükerrer 409) / assignments/{id} GET + cancel; öğrenci surveys GET /
  {id} GET (doldurma+sonuç) / {id}/answers POST (kaydet/tamamla). Sahiplik 404
  (sızıntı yok; koç değişiminde öğrencinin güncel koçu da görür). Tamamlanınca
  koça push (`coach_student`), atanınca öğrenciye push.
- **Seed `scripts/seed_surveys.py`** — 11 anket, ~250 ÖZGÜN madde (idempotent,
  code varsa atlar; `--reset` dikkat: atamaları CASCADE siler). start.sh'e
  eklendi (prod boş kalmaz kuralı). RIASEC = O*NET esinli özgün uyarlama
  (source_attribution'da CC BY 4.0 atfı).
- **Web koç**: öğrenci detayına **"Anketler" sekmesi** (`student-surveys-panel`:
  atamalar [durum rozeti + iptal + Sonucu Gör dialog] + kategori-gruplu katalog
  [Gönder → not'lu dialog]). **Web öğrenci**: `/student/surveys` (bekleyen/
  tamamlanan) + `/student/surveys/[id]` doldurma (mobil-öncelikli: likert5 5
  büyük buton + slider10 1-10 şerit + open textarea; sabit alt çubuk: ilerleme +
  Kaydet + Tamamla; eksikte ilk eksiğe scroll + kırmızı işaret) + site-header
  "Anketler" nav. Paylaşılan `shared/survey-result-view.tsx` (Recharts radar ≥5
  boyut + ton-güvenli bar/pill + SWOT kadran + açık uç + report_note + disclaimer).
- lib: `types/survey.ts` + `api/surveys.ts` (surveyKeys; invalidate
  `teacher:{tid}:students:{sid}:surveys` + `student:surveys` uyumlu) +
  `hooks/use-survey-mutations.ts` (assign/cancel/save + hata kodu etiketleri).
- **Test `scripts/test_api_v2_surveys.py` 18/18** (rol kapıları + atama/mükerrer/
  yabancı-404 + kısmi kaydet + eksikle tamamla + skor doğruluğu [görsel=100 high]
  + çark 8 dilim + SWOT 4 kadran + iptal + öğrenci izolasyonu). Regresyon:
  tenant 29 + teacher_read 12 + student_read 11 + student_mutations 12 + me 13.
  tsc/eslint temiz (build YOK — dev kuralı). **Commit + canlı deploy YOK**
  (kullanıcı kararı bekliyor).

**MOBİL ÖĞRENCİ + AI KARİYER SENTEZİ ✅ (2026-06-12, migration `i2j5m8n9m66d` — head):**
- **Mobil öğrenci anket ekranları** (mobil-only, deploy gerekmez): `lib/surveys.ts`
  (tipler + fetcher'lar) · `(app)/student-surveys` liste (bekleyen/tamamlanan +
  koç notu) · `(app)/student-survey-fill` doldurma (likert 5 büyük buton + 1-10
  şerit + open; alt çubuk ilerleme + Kaydet + Tamamla; eksikte ilk eksiğe scroll +
  Alert; tamamlanınca sonuç) · `components/student/survey-result-view.tsx` (bar +
  seviye rozet + SWOT kadran + disclaimer) · Gelişim hub'a **"Anketlerim" kartı**
  (bekleyen sayısı rozetli) · notification-router `student screen:"surveys"` →
  /student-surveys. Expo typed-routes (.expo/types/router.d.ts) elle eklendi
  (expo start'ta aynı şekilde yeniden üretilir). Mobil tsc temiz.
- **AI Kariyer Sentezi** (**migration `i2j5m8n9m66d`**: `career_insights` —
  additive, uygulandı): `CareerInsight` cache modeli (models/survey.py;
  öğrenci başına TEK satır) + `CAREER_SURVEY_CODES` (mesleki-ilgi/beceri-seti/
  akademik-benlik/coklu-zeka) + `CAREER_REQUIRED_CODES` (ilk ikisi zorunlu).
  `UsageKind.AI_CAREER_SYNTHESIS` = **8 kredi** ("AI Kariyer Sentezi").
  Servis `ai_career_synthesis.py`: anket boyut skorları (deterministik) + GERÇEK
  akademik veri (`_compute_session_prefill` + son 5 ExamResult) → Gemini ücretli
  (personal_data=True, max_output_tokens=16384) → {summary, career_suggestions
  [title/field=YKS alan/why/example_departments], strengths, agenda (hedef
  seansı), watch_outs}. Öneri dili zorunlu ("yakın duruyor"), ilgi↔performans
  çelişkisi watch_outs'a. Endpoint'ler (surveys.py): GET `/teacher/students/{id}/
  career-synthesis` (cache ÜCRETSİZ + ready/missing_surveys) · POST (üret/yenile,
  assert_ai_premium + consent_required + 422 not_enough_data + KREDİ). Öğrenci
  kariyer setinden anket tamamlayınca `_mark_career_stale` (AI çağrısı YOK).
  Web koç paneli: Anketler sekmesi üstünde **CareerSynthesisCard** (eksik anket
  rehberi / oluştur CTA / sonuç: öneri kartları + güçlü yönler + seans gündemi +
  dikkat noktaları + bayat banner + Yenile; consent_required'da confirm → 
  useSetAiConsent → otomatik yeniden dene — dead-end yok).
- **Test:** `test_api_v2_career_synthesis.py` **11/11** (readiness + consent +
  kredi=1 → GET ücretsiz → stale → yenile kredi=2 + free plan 403 + yabancı 404;
  Gemini monkeypatch) · surveys 18/18 yeniden · tenant 29 · coaching_insight 11 ·
  admin_usage 21 GREEN · web tsc+eslint temiz · mobil tsc temiz.
- **CANLI DEPLOY ✅ (2026-06-12):** commit `caedd92` push → sunucu git pull +
  DB yedek (`pre_survey_20260612_0855.dump`) + web/worker/next rebuild.
  Doğrulandı: alembic head = **`i2j5m8n9m66d`** (prod) · survey_templates=11,
  survey_questions=234 (start.sh seed) · healthz 200 · /api/v2/student/surveys
  401 (anonim) · site 200.
- **MOBİL AAB (2026-06-12):** EAS `appVersionSource=remote` + `autoIncrement` —
  versionCode EAS'ta yönetilir. **versionCode 5 build'i (bugün 04:00) Play'e
  HİÇ YÜKLENMEDİ → atlanması SORUNSUZ** (Play yalnız "öncekinden büyük" ister,
  ardışıklık istemez). Yeni production build **versionCode 6** başlatıldı
  (build id `1faafdb7-bd12-4e98-a36e-4d2a4eefad5f`) — v5'in tüm içeriği + anket
  ekranları TEK AAB'de; Play Console'a yalnız bu yüklenir (tek iş). Submit
  yapılandırılmadı (eas.json submit boş) → AAB'yi kullanıcı Play Console'a
  elle yükler.

**KALAN (opsiyonel/sonraki):**
- Koç mobil anket gönder/sonuç + Kariyer Sentezi ekranı (uçlar hazır; koça push
  şimdilik öğrenci detayına götürür).
- Süper admin anket şablonu düzenleme UI (şablonlar DB'de; seed ile yönetilir).
- Faz 2: koç özel anket + veli anketi (token'lı).

---

## Ölü rezerv telafisi (carryover) — geçen haftadan yapılmayan görevler (2026-06-17, migration `l5m8p1q2p44k`)

**Sorun (kullanıcı, student 34 hasta senaryosu):** Öğrenci geçen hafta atanan
testleri yapmayınca (hasta vb.) o testler `SectionProgress.reserved_count`'ta
GLOBAL kilitli kalıyordu → koç yeni haftada aynı üniteyi atayamıyordu ("kalan 0";
`reserve_item` 422). Rezerv "aktif plana taahhüt" ile "geçmişte planlanıp hiç
yapılmamış ölü taahhüt"ü aynı sayıyordu. Mimari: Task `date`'e bağlı (program_id
YOK), WeeklyProgram = tarih-aralığı kapısı; reserved_count öğrenci+bölüm global,
yalnız tamamlama/silme'de düşüyordu.

**Kullanıcı kararları (AskUserQuestion):** kapsam = **A + B**; sınır = **haftası/
programı geçince** (aktif hafta-içi telafi etkilenmez).

- **A — `task_service.reconcile_past_reservations(db, student_id, cutoff_date)`**:
  cutoff'tan ÖNCEKİ + `status != COMPLETED` + `is_draft=False` görevlerin
  yapılmamış (`planned - completed`) rezerv kısmını serbest bırakır (kapasite döner).
  **İdempotent** — **migration `l5m8p1q2p44k`**: `task_book_items.reservation_released_at`
  izi (additive, nullable, downgrade'li). İşaretli kalem tekrar iade EDİLMEZ →
  görev sonradan silinse bile çift-iade yok (`release_task_items`'a guard eklendi).
  Geçmiş kayıt (planned/completed) DEĞİŞMEZ — yalnız kilit kalkar. Section'lı her
  kalem rezerv ediyor (blok dahil; yalnız kitapsız deneme hariç). Tetik: `create_program`
  (cutoff=yeni program start) + add-task cascade (`sidebar-items` GET, lazy,
  cutoff=aktif program start, best-effort commit). Bugün/gelecek/taslak ASLA dokunulmaz.
- **B — Devret**: `GET /teacher/students/{id}/carryover-candidates` (reconcile +
  geçmiş eksik kalemleri listele) + `POST /teacher/students/{id}/carryover`
  (target_date + seçili kalemler → her biri yeni güne yeni görev, kapasiteyi
  yeniden rezerv eder; eski görev DURUR). Frontend: hafta görünümü aside'ında
  `CarryoverPanel` (amber, aday yoksa hiç görünmez; checkbox + tarih + "Bu haftaya
  taşı"). `useCarryover` + `getCarryoverCandidates` + `teacherKeys.carryoverCandidates`.
- **Test:** `test_reservation_carryover` **13/13** (reconcile + kısmi[3/5→3 serbest]
  + bugün/gelecek korunur + idempotent + reserve sonrası atanabilir + candidates +
  **çift-iade guard**) · `test_api_v2_carryover_http` **9/9** (login→candidates→
  reconcile kapasite→carry→yeni görev+rezerv→eski durur). Regresyon: weekly_plan
  14/14 · student_mutations 12/12 · teacher_read 12 · itemless 10 · paywall 5 ·
  gorev_checks (pre-existing itemless 0/0 hariç) · tenant 29.
- **KURAL:** rezerv = yalnız hâlâ yapılabilir göreve (aktif hafta/gelecek/taslak)
  ait kapasite kilidi; haftası geçmiş tamamlanmamış görevin rezervi "ölü"dür →
  serbest bırakılır (yeniden atanabilir). pwd_stamp deseni gibi: rezerv değiştiren
  her yeni yol idempotency + çift-iade guard'ına dikkat etmeli.

---

## Devret v2 — görev düzeyi + carried + güne-tıkla modal + bilgi-amaçlı geçmiş (2026-06-18, migration `m6n9q2r3q55l`)

**Kullanıcı geri bildirimi:** ilk Devret paneli (a) tüm geçmiş haftaları döküyordu
(19 kalem/56 test, kafa karışıklığı) → önce "yalnız geçen hafta + kapalı" yapıldı;
(b) eklenince listeden düşmüyordu + blok/itemless yoktu + geçmiş gezinme yoktu.
**Kullanıcı kararları (AskUserQuestion):** ekleme = güne-tıkla modal (sürükle-bırak
faz 2) · aday = görev düzeyi tüm tipler · blok bağımsız taşıma · carried kalıcı.

- **Migration `m6n9q2r3q55l`**: `tasks.carried_at` (additive, nullable, downgrade'li).
  Görev devret listesinden taşınınca işaretlenir → listeden **DİNAMİK düşer**;
  yeni programla önceki-hafta penceresi kayar → **otomatik sıfırlama** (carried
  temizlemeye gerek yok).
- **`task_service.list_carryover_candidates` GÖREV düzeyine geçti**: `since<=date<
  cutoff` + `status!=COMPLETED` + yayında + `carried_at IS NULL` görevler; her aday
  yapılmamış section kalemleri + itemless + toplam kalan. Tüm tipler (test/blok/
  itemless/deneme/etkinlik). `mark_task_carried` helper.
- **Carry (görev bazlı)**: `POST /carryover` body `task_ids[]` → her kaynak görevin
  YALNIZ yapılmamış işini (section: planned-completed; kitapsız: kalem) hedef güne
  **BAĞIMSIZ yeni görev** olarak kopyalar (blok dahil; eski blok muhasebesi geçmişte
  kalır, çift-sayım yok), kaynağı `carried_at` işaretler — kayıt DURUR. Part A (ölü
  rezerv serbest, TÜM geçmiş) aynen; reconcile yalnız plan modunda.
- **mode (plan vs browse)**: `_carryover_context(program_id)` → geçmiş program
  GÖRÜNTÜLENİYORSA (program_id + end_date<bugün) **browse** (o hafta, BİLGİ AMAÇLI
  eylemsiz, carried düşmüş); aksi halde **plan** (aktif/yeni hafta → bir önceki hafta,
  eylemli). GET `?program_id=N`.
- **Frontend** `CarryoverPanel(studentId, programId, weekDays)`: kapalı başlar +
  tek-satır özet; plan modunda her kartta **"Ekle" → AddToDayDialog** (hedef gün
  grid + varsa periyot Sabah/Öğle/Akşam) → tek görev taşı → dinamik düş; browse
  modunda salt-okuma (slate, "Bu haftada yapılmayanlar (bilgi)"). week-board
  `currentProgramId` + `data.days` geçirir; carryover key'e programId segment.
- **Test:** `test_reservation_carryover` **17/17** (görev düzeyi + carried düşme +
  çift-iade guard + since pencere) · `test_api_v2_carryover_http` **14/14** (mode
  plan/browse + dinamik düşme + carried hariç + bağımsız rezerv). Regresyon:
  weekly_plan 14 · student_mutations 12 · teacher_read 12 · itemless 10 · paywall 5 ·
  tenant 29. **Migration head = `m6n9q2r3q55l`.**
- **Düzeltmeler (2026-06-18, migration `n7o0r3s4r66m`):**
  - **Liste kapsamı**: düz TEST görevleri (kitaptan section, blok DEĞİL, kitapsız
    kalem yok) artık **listede GÖRÜNMEZ** — rezerv reconcile ile zaten iade edildi,
    kitapta "çözülmedi" görünür → koç normal akıştan yeniden atar. Yalnız **blok
    (work_block_id) + etkinlik (video/özet/tekrar/diğer) + kitapsız deneme** listelenir
    (`list_carryover_candidates` filtre).
  - **Hata 1 (geçmiş gün)**: carry hedef tarihi `< bugün` → 422 `past_target_date`
    (geçmiş güne tamamlanamayan görev eklenemez). Frontend `AddToDayDialog` yalnız
    **bugün + ileri** günleri gösterir (`!is_past`).
  - **Hata 2 (silince geri-al)**: **migration `n7o0r3s4r66m`** (`tasks.carried_from_task_id`,
    batch/SQLite-uyumlu FK). Carry yeni görevi kaynağa bağlar; **yeni görev silinince
    kaynağın `carried_at`'i temizlenir** → kaynak tekrar listeye döner. `useDeleteTask`
    carryover'ı invalidate eder. **Migration head = `n7o0r3s4r66m`.**
  - Test: `test_reservation_carryover` **20/20** (filtre + geri-al + browse) · `test_api_v2_carryover_http`
    **17/17** (Hata1 422 + Hata2 sil→geri + dinamik düşme + plan/browse).
  - **Browse modu test dahil**: geçmiş program (`?program_id`) BİLGİ AMAÇLI →
    `list_carryover_candidates +include_plain_tests`; endpoint browse'da True (tüm
    tipler), plan'da False (test hariç).
- **Blok yaşam döngüsü (2026-06-18, migration `o8p1s4t5s77n`):**
  - **Sorun**: Serbest Blok görevleri kitapsız kalem; "blok" işareti yalnız
    `work_block_id`. Blok SİLİNİNCE work_block_id NULL → kitapsız kalem yanlışlıkla
    **tam_deneme (DENEME "N soru")** sınıflanıyordu.
  - **`tasks.block_detached`** (migration, additive): blok silinince bağlı görevler
    işaretlenir → `classify_gorev` + frontend rozet bunu 'etkinlik/**Diğer**' sayar
    (DENEME değil). Program verisi DEĞİŞMEZ (görev kalır). Rozet **"{Ders} / Diğer"**
    (başlık `{Ders} · ...` önekinden; week-day-card/day-board/week-grid block_detached'i
    önek-parse'a dahil eder → uzun ders adları da çözülür). Carry: blok kökenli görev
    taşınınca yeni görev de block_detached (Diğer). `test_block_detach` **9/9**.
  - **Auto-arşiv**: blok tamamen tamamlanınca (`completed >= total`) work-blocks
    liste ucunda **otomatik status=archived** → Serbest Bloklar listesinden düşer
    (lazy, idempotent, GET-içi yazma). Görevler programda BLOK olarak kalır; kısmi
    blok kalır; `include_archived=true` ile yine görünür. `test_block_auto_archive`
    **8/8**. NOT: önceden silinmiş öksüz DENEME görevlerine DOKUNULMADI (kullanıcı kararı).
- **Faz 2 — sürükle-bırak ✅ (2026-06-18, frontend-only):** carryover kartı
  `draggable` (native HTML5 DnD), her gün kartı drop hedefi → görevi o güne taşır
  (carry). Mevcut dnd-kit gün-içi sıralamasına DOKUNMAZ (ayrı event sistemi). Geçmiş
  gün drop kabul etmez; drop'ta gün amber ring. Mobil 'Ekle' modalıyla (DnD masaüstü).
- **Migration head = `o8p1s4t5s77n`.**

---

## Öğrenci bazlı Müfredat İlerleme (2026-06-18, DEVAM EDİYOR — Faz 0 CANLI)

**Bağlam (kullanıcı):** Koç program hazırlarken öğrencinin müfredatta NEREDE olduğunu
+ tamamlama oranını, seansta GEÇEN HAFTA hangi üniteleri işlediğini, program yaparken
SIRADAKİ üniteleri görmek istiyor. Detaylı ihtiyaç analizi + AI-örülü yol haritası yapıldı.

**Mevcut model (keşif):** Resmi müfredat omurgası VAR — `Subject`+`Topic` (built-in,
teacher_id=NULL): Topic.order=resmi sıra, grade_level, curriculum_model (LGS/MAARIF/KLASIK).
Öğrencinin `effective_curriculum_model`+sınıf+track ile sıralı konu seti türetilir.
İlerleme: `SectionProgress` (reserved/completed per öğrenci-ünite) + `TaskBookItem`.
**KRİTİK BULGU:** prod'da 463 BookSection'ın yalnız %34'ü (156) resmi konuya (topic_id)
eşleşmiş → saf resmi-omurga %66 boşluklu. **Eşleştirme yükseltme ön şart.**

**Kullanıcı kararları (AskUserQuestion):** omurga = **Hibrit** (resmi Topic omurga +
eşleşmemiş ekstra). + **AI kullanımı sorusu** → en büyük kaldıraç EŞLEŞTİRME (Gemini
semantik, ÜCRETSİZ key — kişisel veri değil) + akıllı sıradaki üniteler (ücretli, KS4 deseni).

**AI-örülü yol haritası (onaylı):**
- **Faz 0 — Eşleştirme yükseltme** ✅ (2026-06-18, CANLI, migration YOK): deterministik
  auto-map + Gemini semantik öneri + koç onay UI.
- **Faz 1 — müfredat ilerleme servisi + öğrenci "Müfredat" sekmesi** ✅ (2026-06-19, CANLI).
- Faz 2 — program "sıradaki üniteler" + tek-tık ata + AI akıllı öncelik (perf+sınav+getiri).
- Faz 3 — seans "geçen hafta işlenenler" + KS4 içgörüye müfredat girdisi.
- Faz 4 (ops.) — müfredat yetişme projeksiyonu + AI kapsama planı + kurum/veli.

**Faz 0 detay (CANLI):**
- `app/services/curriculum_mapping.py`: `normalize` (Türkçe sadeleştirme) + auto-map
  (label→Topic.name exact-normalize) + `_ai_suggest` (Gemini `personal_data=False`=ücretsiz
  key, eşleşmeyenler; best-effort) + `apply_mappings`. Aday konular = kitabın subject'inin
  `_accessible_topics`.
- Uçlar (library): `GET /books/{id}/mapping-suggestions?ai=true` · `POST /books/{id}/apply-mapping`.
- Frontend: kitap detayı "Bölümler" sekmesinde **"Müfredata eşleştir"** butonu (eşleşmemiş
  rozeti) → `CurriculumMappingModal` (satır konu seçici + auto/AI/eşli rozet + "Yapay zekâ
  ile öner" + Uygula).
- `test_curriculum_mapping` **11/11** · library 24/18. Migration GEREKMEZ (topic_id zaten var).
- **AI batch fix (2026-06-18):** 22 ünitelik tam Gemini çağrısı 2.5 düşünme tokenıyla
  8192'yi aşıp JSON'u kesiyordu → tüm "öneri yok". `_ai_suggest` section'ları `_AI_BATCH=12`
  parçaya böler + `max_output_tokens=16384`. Modal: öneri açılır menüye `valueFor` ile
  OTOMATİK dolar (seed timing bug'ı düzeltildi) + amaç açıklaması.

**Faz 1 detay (CANLI):**
- `app/services/curriculum_progress.py`: `_applicable_subjects` (all_subjects kuralı —
  `covers_grade` + `curriculum_model`) + topic bazında agregat (StudentBook→Book→
  BookSection.topic_id → SectionProgress completed/reserved + test_count) → **durum**
  (kaynak_yok/baslanmadi/planlandi/devam/tamamlandi) + **coverage_pct** (işlenen/toplam) +
  **frontier** (son işlenen=en yüksek order-started · sıradaki=ilk kaynaklı-başlanmamış) +
  **eşleşmemiş ekstra** (topic_id NULL section'lar). Konu-içi derinlik = completed/test_total.
- `GET /teacher/students/{id}/curriculum` (sahiplik 404).
- Frontend: öğrenci detayına **"Müfredat" sekmesi** (Analitik'ten sonra) + `CurriculumPanel`
  (genel kapsama barı + ders akordeon: sıralı konu + durum rozet + "sıradaki" vurgu +
  test derinliği + eşleşmemiş ekstra grubu). "İşlenme" = en az 1 test çözülen konu/toplam.
- `test_curriculum_progress` **12/12** (durumlar + coverage + frontier + ekstra). Migration YOK.

---

## Dinamik vitrin + dönüşüm + sosyal kanıt + analitik (2026-06-15, CANLI)

**Bağlam:** Anasayfa bilgi kartlarının dinamik gösterimi (feature_catalog: fuzzy +
LinUCB bandit + MMR çeşitlilik + A/B), pazarlama stratejisi, dönüşüm ölçümü, GA-tarzı
site analitiği. Kullanıcı sırası (en küçük→büyük): #1 menü fix · #2 sosyal kanıt ·
#3 dönüşüm ölçümü · #4 Plausible · #5 dinamik gösterim (ayrı). Sonra #5 sırası
(kullanıcı onayı): dönüşüm döngüsü kapat → A/B kur → yayın akışı (önizleme).

- **Menü overflow** ✅: site-header öğrenci nav (10 link) → ilk 6 + `StudentMoreMenu`
  dropdown (son 4).
- **Sosyal kanıt** ✅ (**migration `j3k6n9o0n77e`** — testimonials): süper admin
  giriş (`/admin/testimonials`, kurum referansı/yorum/başarı hikayesi, moderasyon
  `TESTIMONIAL_MODERATE`) + landing slider + uygulama-içi `share-experience-prompt`
  (öğrenci/veli/koç/kurum yorum toplama). etutkoc.com yorumları JS-render →
  kullanıcı elle yükledi.
- **Dönüşüm ölçümü (#3)** ✅ (**migration `k4l7o0p1o88f`** — signup_attributions):
  `conversion_service` (record_signup_attribution: anon landing oturumu `fc_telemetry_sid`
  + A/B varyant → SignupAttribution; compute_funnel: ziyaretçi→etkileşim→tıklama→demo→
  üye→ücretli + varyant kırılımı). `/admin/conversion` panosu. Landing kartları
  tıklanabilir (`goSignup` → cta_click + /signup/teacher).
- **Plausible analitik (#4)** ✅: self-host (plausible+ClickHouse+Postgres),
  first-party tracking Caddy `/js/* + /api/event` → plausible; `analytics.etutkoc.com`
  bloğu ANA blok DIŞINDA (route{} 2 kapanış); env-driven script `web/app/layout.tsx`;
  `/admin/analytics` iframe embed. **OOM-güvenli deploy: 2GB swap + build sırasında
  plausible stop** (3.7GB VPS'te Next build OOM oluyordu). DERS: secret'ı grep'leme
  (SECRET_KEY_BASE sohbete sızdı → rotate edildi). DERS: Caddyfile bind-mount stale-FD →
  `restart proxy` gerek (reload yetmez).
- **Dönüşüm döngüsü (#5-1)** ✅ (CANLI, HEAD öncesi `11ea714`): `bandit.CONVERSION_REWARD=3.0`
  + `reward_conversion_for_session` (üye olan oturumun cta_click/demo_click yaptığı
  kartlara güçlü ödül) → `conversion_service.record_signup_attribution` hook'lar.
  Anasayfa artık "ilgi çekeni" değil "üye yapanı" öğrenir. `test_bandit_conversion_reward` 5/5.
- **Görsel şablonlar** ✅: mockup kütüphanesi zaten zengindi (16 mockup, registry=frontend
  MAP birebir); demo konularından gerçekten eksik 3 eklendi → **19**: focus_timer
  (Pomodoro halkası) + goals (hedef ağacı) + topic_performance (konu doğruluk barları).
  `MOCKUP_ICON` tek kaynağa (`mockups.tsx`) taşındı.
- **#2 Yayın akışı — anasayfa önizlemesi** ✅: admin kart formunda (`admin-feature-card-form-client`)
  paylaşılan `LandingCardPreview` (landing FeatureCard görünümü birebir, telemetri/
  navigasyon yok) sağ kolonda CANLI güncellenir; **yayın kapısı görünür** (durum!=Yayında →
  uyarı, manuel gizle → uyarı, yayında → yeşil onay).
- **#3 Kart-havuzu A/B (kesfet vs tema)** ✅: deney varyantına opsiyonel `pool` (slug
  öneki) boyutu — varyant artık yalnız sıralama stratejisini değil KART HAVUZUNU da
  değiştirir. `feature_catalog._variant_pool` + `LANDING_POOLS` tek kaynak + landing
  filtresi (boş havuz → graceful fallback). `ExperimentCreateBody +ctrl_pool/test_pool`;
  form meta +pools (yayında kart sayımlı); varyant brief +pool/pool_label; form havuz
  seçicisi + liste/detay pool rozeti. Dönüşüm ölçümü (#5-1) artık elle vs AI-temalı
  kart setlerini gerçekten kıyaslar. `test_landing_pool_ab` 9/9.
- **Panel düzeltmeleri** ✅ (kullanıcı bildirdi): "Filo durumu"→"Öğrencilerin durumu"
  (risk-bazlı, `risk_assessments`'ten kırmızı/sarı/yeşil); "Kritik 1 ama drill boş"
  (filter `?risk=medium` artık medium+high eşler); "1106 planlanan test" şişmesi
  (deneme test sayılıyordu) → `week_test_deneme_for` test=soru-hacmi (`item_is_test`) /
  **deneme=ADET** (soru toplamı değil); test+deneme yan yana (kurum panosu + öğretmen
  detayı + teacher card); compliance test-only (Book.type deneme HARİÇ).
- **Migration head:** `k4l7o0p1o88f` (signup_attributions) — `j3k6n9o0n77e`
  (testimonials) ile birlikte additive, prod'da uygulandı. Mockup/pool/önizleme
  migration GEREKTİRMEDİ (kod/config). Tümü CANLI (web+worker+next rebuild, OOM-güvenli).

---

## DEVAM EDEN — Konu Performansı + Veli AI + mobil eksikler (2026-06-06, P1-P4)

**Bağlam:** Kullanıcı cihaz-üstü derin test (4 rol) sırasında 11 maddelik kapsamlı
istek verdi (çoğu web+mobil+backend). Paketlere bölündü; **sonunda kapsamlı test +
canlı deploy (web + Android/iOS build) + push** istendi. Migration head =
**`f9g2j5k6j33a`** (parent_insights). Commit'ler origin'e push'landı (`5f7cdfb`),
**canlı deploy + mobil build BEKLİYOR** (tüm paketler bitince).

- **Mobil koç 7 düzeltme** ✅ (commit'li, **mobil build bekliyor** — expo-audio
  native modül): biten kaynak gizle / etkinlikte ders seç (başlık `{Ders}·{detay}`) /
  deneme ders-bazlı D-Y / **seans mikrofon dikte** (expo-audio + /sessions/transcribe,
  format audio/mp4) / DNA "Derslere göre" netlik + "(diğer)"→"Deneme/etkinlik (derssiz)" /
  Talepler→Destek notu / öneri biten-kaynaktan üretmiyor (teyit, suggestions.py:505).
  + klavye fix (FormSheet behavior="padding") + içgörü 500 graceful (gemini.py deploy'lı) +
  tekrar seed geri bildirimi.

- **P1 — Ders→Konu performansı** ✅ (backend+web+mobil, **14/14**): çözülen test +
  D/Y soru + doğruluk % (ders→konu, BookSection.label=konu; DENEME hariç; aynı isim
  birleşir). `topic_performance.py` + 3 endpoint (teacher/student/parent, gizlilik 404) +
  `build_topic_performance_response` (3 yüzey ortak). Web: koç "Konu Performansı" sekmesi +
  /student/topics + /parent/students/[id]/topics (paylaşılan TopicPerformancePanel
  source-tabanlı). Mobil: tek generic route `topic-performance.tsx` (source+id) + 3 nav.

- **P2 — Veli deneme geçmişi + AI içgörü** ✅ (backend+web+mobil, **11/11**, migration
  `f9g2j5k6j33a`): P2a GET /parent/students/{id}/exams (tüm denemeler, koça-özel not
  gizli). P2b `ai_parent_insight.py` (Gemini ücretli, konu perf+deneme→veliye sade analiz;
  koç-özel seans notu YOK) → kredi **öğrencinin KOÇUNUN** havuzundan (AI_PARENT_INSIGHT=6) +
  koç ücretli paket + onay kapısı; GET ücretsiz cache (hesaplanan bayatlık) / POST kredi /
  yeterli veri yok 422. `ParentInsight` modeli (öğrenci başına tek). Web+mobil veli
  "Denemeler & Analiz" ekranı (içgörü oluştur/yenile + deneme geçmişi).

- **P3 — Veli↔koç çift yönlü talep + öğrenci görev-talebi** ✅ (backend+web+mobil):
  P3a `parent_request_to_coach` (veli→çocuğun koçu, audience=teacher; mevcut koç
  inbox + thread reuse; exam_comment/progress_question kategori). POST /parent/
  students/{id}/coach-request. Veli /support gate'ine PARENT. `test_api_v2_parent_
  coach_request.py` 9/9. Web: /parent/support (SupportCenter mine + çocuk-seçimli
  create + exam ekranından "koça sor"). Mobil: parent/support tab + create dialog.
  P3b — öğrenci görev-değiştir/çıkar talebi MOBİLDE ZATEN VARDI (task-sheet "Koça
  ilet": Soru/Sayı değiştir/Görevi kaldır).
- **P4 — Kurum** ✅ (backend+web+mobil):
  - P4a Müdahale "programı var ama 3 gün yapmıyor" artık görünür (action_center
    4. sinyal inactive_program — consecutive_empty medium). simulate 11/11.
  - P4b risk/tükenmişlik "Koça ilet" GEÇMİŞİ (GET /institution/coach-interventions,
    subject'ten ad parse, ad-bazlı eşleşme; web+mobil InterventionBadge).
    notify_coach 15/15.
  - P4c aktivite heatmap okunabilirlik (hafta-ayrımı + tarih ekseni; mobilde
    kareye dokun→tarih).
  - P4d haftalık özet grafikleri (web Recharts + mobil CSS bar).
  - P4e kurum abonelik mobilden (yükseltme talebi zaten vardı + akademik yıl/
    duraklat/devam/garanti aksiyonları eklendi).

**Test (hepsi GREEN):** topic_performance 14 + parent_insight 11 + parent_coach_
request 9 + notify_coach 15 + action_center 8 + simulate 11 + institution/p2/p3 +
parent + support 54 + tenant + gorev_stats 27 + card_consistency 23 + projection 10.
(itemless_solved_count 0/0 = önceden-var-olan ilgisiz test bug'ı, CLAUDE.md notu.)

**Deploy (2026-06-06):** tüm commit'ler origin'e push (HEAD a424271). Canlı:
git pull + DB yedek + web/worker/next rebuild (migration f9g2j5k6j33a start.sh
`upgrade head` ile uygulanır). **Mobil EAS build** (Android+iOS; expo-audio + tüm
P1-P4 + koç fixleri) BEKLİYOR — ayrı adım.

---

## Proje

**ETÜTKOÇ** — LGS/YKS koçluk takip platformu. FastAPI + Jinja + HTMX'ten
Next.js 16 + React 19 + Tailwind v4 + TanStack Query v5'e taşınıyor (Strangler
Fig deseni; Caddy path-based routing).

- Deploy: AWS Lightsail VPS + 5-container Docker Compose (Caddy/FastAPI/Next.js/Postgres/Redis)
- BFF cookie auth, `/api/v2` JSON
- 5 rol izole: Öğrenci / Öğretmen / Kurum Yöneticisi / Veli / Süper Admin
- Backend Python 3.12, frontend pnpm + Next.js
- Dev: `uvicorn app.main:app --port 8081` + `pnpm dev` (port 3000)

## Yönetim kuralları (kullanıcının kırmızı çizgileri)

- **KURAL 1 — Jinja Read-Receipt Protokolü** (2026-05-19 yeniden tanımlandı):
  Her Jinja→Next.js paketinden önce **iki aşama** zorunlu:
  - **AŞAMA 1 — Link haritalama**: Hedef rolün ana sayfasından (örn.
    `/institution`) yayılan **TÜM** linkler haritalanır. Sadece o rolle ilgili
    kodlar incelenir.
  - **AŞAMA 2 — Eksiksiz okuma**: Haritadaki her route/template/service
    **SONUNA KADAR** okunur. İlk birkaç satıra bakıp tahmin yürütmek yasak;
    sayfa sonuna inilmeden sonraki dosyaya geçilmez. Mimari **tam ve
    eksiksiz** öğrenilir; "muhtemelen şöyledir" mantığı yok.
  - Çıktı: Files-Read Receipt + rolün **tüm eylemleri** (özellik listesi) +
    parite tablosu. Sonra eylem planı + **kullanıcı onayı**. Onaysız kod yasak.
  - Receipt çıkmadan kod yasak. Bu kuralın istisnası yok.
- **Eylem deşifreleme önceliği**: Sorun tasarım değil **fonksiyonellik**.
  Mimariyi anla, hangi eylemi nereden tetiklediğini öğren, eksik özellik
  bırakma. Öğretmen panelinde tek tek talimat verilmek zorunda kalındı —
  bunu kurum panelinde yaşatmamak için mimari önce eksiksiz çözülür.
- **Parite kuralı**: FEATURE parity zorunlu (yapı/akış aynı); VISUAL parity yasak
  (ikon/emoji/renk kopyası değil — fresh shadcn-flavored Next.js look). Parite
  tablosunda "Next.js görsel yaklaşımı" sütunu şart.
- **Rol izolasyonu**: 5 rolün her biri kendi dalgasında. 5a/5b/5c bölünmesi korunur.
- **Sade dil**: Yabancı kısaltma/jargon önce gelmez. Önce sade Türkçe + ne işe
  yaradığı + somut örnek; sonra parantez içinde teknik adı.
- **Admin panellerinde jargon yasak**: DAU/WAU/MRR/Tenant/Descending açıklamasız
  geçemez. Sayfa başına mini sözlük + metrik yanına ⓘ tooltip.
- **Section panel standardı**: Her bölüm `_macros/section_panel.html` (veya
  Next.js `<SectionPanel>`) içine sarılır — beyaz panel + renkli üst şerit +
  her zaman görünür açıklama. Çıplak h2+grid yasak.
- **Kullanıcı şifrelerine asla dokunma**: Gerçek hesapların password_hash/locked_until/
  failed_login_count alanları test için sıfırlanmaz; geçici test user oluştur.
- **Riskli sprint'ler**: auth/notification/external API/migration sprint'leri
  birleştirmeden göster, onay bekle.
- **Mobil hazır**: PWA terk edildi; Next.js + shadcn/ui + BFF cookie ile app-like UX.
- **Windows dev**: WatchFiles reload güvenilmez; port 8081 kullan; `taskkill //IM`
  yasak — PID ile kill.
- **Git/commit**: Kullanıcı açıkça istemeden commit oluşturma. Riskli ops
  (push --force, reset --hard, vs.) onaysız asla.

## Dalga sırası

| Dalga | Kapsam | Durum |
|---|---|---|
| **D0** | Aşama 0 envanter/contract/risk | ✅ Bitti |
| **D1** | `/me/account` auth foundation | ✅ Bitti |
| **D2** | Öğrenci paneli (`/student/*`) | ✅ Bitti |
| **D3** | Öğretmen paneli (`/teacher/*`) | ✅ **Tamamlandı 2026-05-19** |
| **D4** | Kurum Yöneticisi (institution admin) | ✅ **Tamamlandı 2026-05-19 (P1-P8)** |
| **D5** | Veli (`/parent/*`) | ✅ **Tamamlandı 2026-05-19 (P1-P6)** |
| **D6** | Süper Admin (`/admin/*`) | ✅ **TAMAMLANDI 2026-05-20** (P1-P6 + P7 Ticari Pano a-d + Güvenlik Kamarası G1-G4 + Caddy `/admin/*` → Next.js) |
| **D7** | Auth / güvenlik (`/login`, `/signup`, `/password`, 2FA) | ✅ **TAMAMLANDI 2026-05-20** (P1 parite+BFF güvenlik · P2 şifre sıfırlama · P3 signup+email doğrulama · P4 2FA/TOTP · P5 oturum yönetimi+public teklif) |

## Dalga 3 — son durumu (2026-05-19)

**Tamamlanan paketler:**

- **3.5a (1-8)** — Haftalık plan UX parite: 2-sütun, açılır günler, dnd-kit,
  inline edit dialog, sidebar invalidate, ders-bazlı sort, talep modalı SELECT
- **3.5b** — Header rozetleri/butonları (Yenile/Sınıf Yükselt/Hedefler/Tekrar/DNA/Odak),
  anchor, sinema-koltuk grid
- **3.5c** — Jinja read-receipt protokolü resmileşti; 5c gerçek içerik
  (promote/goals/review/dna/focus)
- **3.5d.2** — Students pasif row dim + library tonlu nav + /me redirect +
  password change kartı + settings güvenlik sekmesi
- **3.5d.3** — Book-set bulk apply endpoint + set→öğrenci agregasyon (student_count,
  grade_distribution, assigned_students) + Tabs (Set'ten uygula)
- **3.5d.4** — Öğrenci kitap envanteri: subject_id/name/publisher/sections eklendi;
  ders gruplama + 8-renk pastel ton (subject_id hash) + progress bar +
  3 KPI chip + `<details>` ünite breakdown + URL `?subject_id=` filter
- **3.5d.5** — `/teacher/library` redesign: overall KPI, chip-bar (Ders/Tip/Sınıf)
  her satır + sayım, ders bazlı bölümleme, tip-renkli kart şerit, klavye `/` + `Esc`
- **3.5d.6** — Müfredat farkındalığı: SubjectRef'e grade alanları,
  TargetGradePicker (3-radyo + ince ayar) book-create-form'da, optgroup ders
  dropdown, library'de müfredat chip-bar, book-set kitap-ekle dialog yeniden
  yapı (arama+tip+gruplama)
- **3.5d.7** — Curriculum hard-filter bug fix: kitap listesi de
  `subjectById[item].curriculum_model === effectiveCurriculum`'a göre frontend
  filtrelenir. "Tümü" müfredat chip'i kaldırıldı. Default = en dolu müfredat.
- **3.5d.8** — BookSet sınıf farkındalığı: migration `n5o7r0s1r99l` ile 3 alan
  (target_grade_min/max/graduate) + label_tr; create/patch validation;
  TargetGradePicker yeniden kullanım; set list kart badge; set detail edit
  formda picker; student-books-panel "Set'ten uygula" iki-grup (Önerilen / Diğer
  sınıflar) + uyumsuz seçimde AlertTriangle uyarı banner

**Asılı bırakılanlar (kullanıcının kararıyla):**
- **Jinja `/teacher/*` route emekliliği erteleme** — Caddy `/teacher/*` zaten
  Next.js'e yönlendiriyor; 14 Jinja teacher_*.py dosyası + 27 HTML şablonu dead
  code halinde **yayında bekliyor**. Silinmiyor (kullanıcı 2026-05-19 kararı:
  "Jinja'ya dokunma, kalsın").
- **Jinja `/institution/*` route emekliliği erteleme** — Caddy
  `/institution/*` Next.js'e yönlendiriyor (D4 P8, 2026-05-19);
  `app/routes/institution.py` (1153 satır, 28 route) + 17 HTML şablonu
  (`app/templates/institution/*.html`) dead-code halinde **yayında bekliyor**.
  Silinmiyor (aynı "Jinja'ya dokunma, kalsın" kararı).
- **Jinja `/parent/*` route emekliliği erteleme** — Caddy `/parent/*` +
  `/legal/kvkk-veli` Next.js'e yönlendiriyor (D5 P6, 2026-05-19);
  `app/routes/parent.py` (767 satır, 15 route) + 10 HTML şablonu (parent/*
  + legal/kvkk_parent.html) dead-code halinde **yayında bekliyor**. Bildirim
  altyapısı (producer/dispatcher/cron_jobs/whatsapp_webhook + 8 email
  template) DOKUNULMAMIŞ — server-side e-posta/WA gönderim için gerekli.
- **Jinja `/admin/*` route emekliliği erteleme** — Caddy `/admin` + `/admin/*`
  Next.js'e yönlendiriyor (D6 Caddy adımı, 2026-05-20); `app/routes/admin.py`
  (6154 satır, 133 endpoint) + 50 HTML şablonu (`app/templates/admin/*.html`)
  dead-code halinde **yayında bekliyor**. Silinmiyor (aynı "Jinja'ya dokunma,
  kalsın" kararı). `/api/v2/admin/*` zaten FastAPI'de (BFF backend). 27 admin
  servisi (tenant_health/revenue_panel/campaigns/offers/security_monitor/
  alarm_engine/abuse_detection/tenant_activity vb.) API v2 endpoint'leri
  tarafından AYNEN kullanılıyor — DOKUNULMADI.

## Sayım — backend smoke testleri

- `test_api_v2_teacher_read.py` — 12 senaryo
- `test_api_v2_teacher_students.py` — 14
- `test_api_v2_teacher_library.py` — 24 (18 senaryo, 24 alt-check)
- `test_api_v2_teacher_weekly_plan.py` — 14
- `test_api_v2_teacher_pages_5c.py` — 19
- `test_api_v2_teacher_pages_5d1.py` — 10
- `test_api_v2_teacher_pages_5d2.py` — 10
- `test_api_v2_teacher_book_set_apply.py` — 12
- `test_api_v2_teacher_book_set_grade.py` — 10
- `test_api_v2_teacher_program.py` — program endpoints
- `test_api_v2_teacher_insights_settings.py` — settings/cron/email
- `test_api_v2_teacher_requests.py` — talep yanıtlama
- `test_api_v2_teacher_academic_csv.py` — academic years + CSV
- `test_api_v2_institution.py` — D4 P1 (18 senaryo)
- `test_api_v2_institution_p2.py` — D4 P2 (19 senaryo)
- `test_api_v2_institution_p3.py` — D4 P3 (18 senaryo)
- `test_api_v2_parent.py` — D5 P1 (20 senaryo)
- `test_api_v2_parent_invitation.py` — D5 P2 (17 senaryo)
- `test_api_v2_admin.py` — D6 P1 (13 senaryo)
- `test_api_v2_admin_institutions.py` — D6 P2 (23 senaryo)
- `test_api_v2_admin_users.py` — D6 P3 (25 senaryo)
- `test_api_v2_admin_audit_kvkk.py` — D6 P4 (18 senaryo)
- `test_api_v2_admin_usage_quota_flags.py` — D6 P5 (21 senaryo)
- `test_api_v2_admin_feature_catalog.py` — D6 P6 (25 senaryo)
- `test_api_v2_admin_revenue_analytics.py` — D6 P7a (9 senaryo)
- `test_api_v2_admin_revenue_360.py` — D6 P7b (18 senaryo)
- `test_api_v2_admin_revenue_offers.py` — D6 P7c (19 senaryo)
- `test_api_v2_admin_revenue_campaigns.py` — D6 P7d (17 senaryo)
- `test_api_v2_admin_revenue_dashboard.py` — D6 G1 (11 senaryo)
- `test_api_v2_admin_security_overview.py` — D6 G2a (14 senaryo)
- `test_api_v2_admin_security_activity.py` — D6 G2b (15 senaryo)
- `test_api_v2_admin_security_sessions.py` — D6 G3 (17 senaryo)
- `test_api_v2_admin_security_alarms_abuse.py` — D6 G4 (21 senaryo)
- `test_api_v2_auth_p1.py` — D7 P1 (10 senaryo: ActiveSession/heartbeat/terminate/
  SuspiciousIp/turnstile/sid/must_change)
- `test_api_v2_auth_p2.py` — D7 P2 (11 senaryo: forgot/reset token akışı +
  enumeration + tek-kullanım + breach/policy + login doğrulama)
- `test_api_v2_auth_p3.py` — D7 P3 (13 senaryo: signup teacher/invite + email
  doğrulama + invite info + kuota + auto-login)
- `test_api_v2_auth_p4.py` — D7 P4 (14 senaryo: 2FA setup/enable/disable +
  login challenge + TOTP/yedek kod verify + rol kısıtı)
- `test_api_v2_auth_p5.py` — D7 P5 (12 senaryo: /me/sessions list+revoke +
  self-terminate + public offers view/accept/decline)
- `test_api_v2_institution_compliance.py` — Program Uyum Panosu (10 senaryo:
  kurum rate + doğruluk + öğretmen kırılımı + boş program + dikkat + trend)
- `test_api_v2_institution_action_center.py` — KP1 Müdahale Merkezi (8 senaryo)
- `test_api_v2_institution_scorecard.py` — KP2 Öğretmen Etkililik Karnesi (7 senaryo)
- `test_api_v2_institution_parent_trust.py` — KP3 Veli Güveni (9 senaryo)
- `test_api_v2_teacher_exams.py` — KP4a Deneme sonucu CRUD (16 senaryo: net
  hesap LGS/YKS + ders kırılımı + sahiplik 404 + summary/trend + sil)
- `test_api_v2_institution_academic.py` — KP4b Kurum Akademik Çıktı (13 senaryo:
  kapsama + net başarı % normalize + section/öğretmen kırılımı + gelişen/gerileyen)

**Toplam: ~205+ senaryo, hepsi yeşil** (2026-05-19 itibarıyla).

**D4 (Kurum Yöneticisi) frontend kapsamı (P7 sonu):** `/(institution)/*`
altında 19 route — Panel + 4 kişi (teachers list/detay/roster/davet) + 6
analiz (at-risk/cohorts/heatmap/burnout/goals/admin-digest list+detay) + 3
üyelik (subscription/quota/usage) + 3 print (at-risk/heatmap/cohorts).
Sidebar'da artık disabled item yok.

## Önemli mimari kararlar

- **MutationResponse.invalidate**: Backend her mutation'da etkilenen queryKey
  prefix'lerini liste olarak döner (`teacher:{id}:students:{sid}:books` gibi).
  Frontend `applyInvalidate(qc, keys)` ile TanStack Query'yi yeniden bayatlar.
  R-006 sözleşmesi.
- **Strangler Fig**: Caddy `/teacher/*` → Next.js (live); `/admin/*`, `/parent/*`,
  `/student/*` (kısmi) hâlâ Jinja'da. `/api/v2/*` Next.js BFF tarafından
  cookie-auth ile tüketilir.
- **Subject curriculum_model**: Subject tablosunda aynı ders adı (örn. "Matematik")
  farklı müfredat modellerinde (LGS / MAARIF_LISE / KLASIK_LISE) ayrı kayıt.
  UniqueConstraint (teacher_id, name, curriculum_model). UI'da optgroup ile
  gruplandırılır + müfredat chip-bar ile filtrelenir.
- **BookSet target_grade**: 3.5d.8'de eklenen alanlar (Book modeliyle aynı
  semantik). Set "Tüm seviyeler" sayılır = üç alan null/false. Bulk assign
  ENGEL DEĞİL — sadece uyarı.
- **Tonal sistem**: Subject_id hash → 8 pastel ton (indigo/emerald/amber/rose/
  violet/cyan/fuchsia/sky). Book tipi için 5 sabit ton. `border-l-4 +
  ring-1 ring-inset {tone}/10` deseni — açık background yok, dark mode uyumlu.

## Test komutları

```bash
# Backend smoke (tek dosya)
cd D:/LGS-Program && PYTHONPATH=. python scripts/test_api_v2_teacher_book_set_grade.py

# Frontend
cd D:/LGS-Program/web && pnpm tsc --noEmit
cd D:/LGS-Program/web && pnpm eslint . --max-warnings 0
cd D:/LGS-Program/web && pnpm build

# Tenant izolasyon regresyon
cd D:/LGS-Program && PYTHONPATH=. python scripts/test_tenant_isolation.py
```

## Dalga 4 — son durumu (2026-05-19)

**Tamamlanan paketler:**

- **D4 Aşama 1+2+3** — KURAL 1 protokolü: `/institution` link haritası (13 menü
  linki) + 30 endpoint + 17 template tam okundu; Files-Read Receipt + 50 ayrı
  eylem listesi + 17 satırlık parite tablosu üretildi; kullanıcı onayı alındı.
- **D4 Paket 1 — Backend foundation**:
  - `app/routes/api_v2/schemas/institution.py` (16 model)
  - `app/routes/api_v2/institution.py` (10 endpoint: dashboard / teachers list /
    POST teacher + auto-password / deactivate / activate / pause-alerts /
    resume-alerts / teacher card / roster + filters / goals summary)
  - `_require_institution_admin` dep (role + institution_id guard)
  - `scripts/test_api_v2_institution.py` — **18/18 yeşil**
- **D4 Paket 2 — Backend ileri özellikler**:
  - Şemalar: 17 yeni model (invitations + heatmap + risk + burnout + cohorts + WoW)
  - 7 yeni endpoint: `/invitations` GET/POST + revoke, `/activity-heatmap`,
    `/at-risk`, `/burnout`, `/cohorts` (4 sekme; sadece aktif sekme hesaplanır)
  - Privacy: `at-risk`/`burnout` öğretmen-öğrenci eşlemesi gösterir ama
    detay linki yok; mute durumu rozet olarak
  - Quota guard: invitation create'te `check_quota_for_create` ile öğretmen
    kuotası kontrol edilir (aşımda 403)
  - `scripts/test_api_v2_institution_p2.py` — **19/19 yeşil**
- **D4 Paket 3 — Backend abonelik & ticari**:
  - Şemalar: 16 yeni model (Subscription / Quota / Usage / AdminDigest)
  - 10 yeni endpoint: `/subscription` GET + 4 POST action
    (switch-academic-year / pause / resume / guarantee/enable),
    `/quota`, `/usage?days=N`, `/admin-digest` GET + send-now + detail
  - Yaz penceresi guard: `is_summer_window()` False → 409 summer_window_required
  - Idempotent: switch/resume/guarantee zaten aktifse 200 + no-op
  - Cross-tenant digest detail 404 — `institution_id` filtreli sorgu
  - `scripts/test_api_v2_institution_p3.py` — **18/18 yeşil**
- **D4 Paket 4 — Frontend foundation**:
  - `web/lib/types/institution.ts` (15 model) + `lib/api/institution.ts`
    (fetcher + queryKeys) + `lib/hooks/use-institution-mutations.ts`
    (create/deactivate/activate/pause/resume)
  - `app/(institution)/layout.tsx` — auth guard + redirect
  - `components/institution/institution-shell.tsx` — sticky sidebar (lg+) +
    mobil drawer; 13 menü linki 3 grup (Kişiler/Analiz/Üyelik); P5-P7
    item'lar "yakında" disabled görünür
  - 5 sayfa + client component'lar:
    - `/institution` Dashboard (KPI grid + risk/inactive callout + öğretmen tablosu)
    - `/institution/teachers` list + NewTeacherDialog (tek seferlik temp_password
      başarı kartı + "Kopyala") + TeacherRowActions (DropdownMenu + confirm dialog)
    - `/institution/teachers/[id]` kart (gizlilik banner, öğrenci listesi
      detay linki YOK)
    - `/institution/roster` filter form + URL state (geri/ileri navigasyon parite)
    - `/institution/goals` 3 KPI + hedefsiz uyarı + bilgi notu
  - `invalidate.ts` — `institution:{id}` → `institution:me` prefix mapping eklendi
  - **Birebir Jinja parite**: tüm form alanları, buton metinleri, onay
    diyaloğu cümleleri, gizlilik notları, rozet ayrımları (auto/manuel pause),
    renk eşikleri (≥70 emerald / ≥40 amber / <40 rose), pasif satır
    silikleştirmesi
  - **Verify**: tsc ✅ · eslint ✅ · build ✅ (5 yeni route)
- **D4 Paket 5 — Frontend risk & analytics**:
  - `recharts` bağımlılığı eklendi (Next.js standart bar chart)
  - Lib: `lib/types/institution.ts` 6 yeni şema (At-risk/Burnout/Heatmap/Cohort
    tüm tipler) + 4 fetcher + 4 queryKey
  - Paylaşılan: `heatmap-grid.tsx` (5-level emerald palette + 11px/8px),
    `level-badge.tsx` (RiskLevelBadge + BurnoutLevelBadge + PauseBadge +
    score color helper'ları), `cohort-bar-chart.tsx` (Recharts BarChart +
    custom Tooltip + Cell renkleri)
  - 4 görüntüleme sayfası:
    - `/institution/at-risk` — privacy banner + 3 count card (kritik/risk/dikkat)
      + tablo (öğrenci/öğretmen/seviye/risk puanı/indicator chip'leri); risk
      seviyesine göre satır arka planı + pause/mute rozetleri
    - `/institution/burnout` — risk skoru sıralı tablo + Seviye badge'leri +
      gizlilik notu
    - `/institution/activity-heatmap` — 4/12 hafta segmented buttons (URL state),
      bilgi banner (skor formülü + pasif tanımı), legend, GitHub-style grid
      + hover scale + native tooltip
    - `/institution/cohorts` — gizlilik notu + 3 WoW kartı (delta ↑↓ ok),
      4 sekme (border-bottom nav) + Recharts bar chart + tablo; tab-spesifik
      empty state
  - Backend ufak ekleme: `AtRiskRowItem.pause_reason` field (auto/manuel ayrımı için)
  - 3 print sayfası (`(print)` route group altında):
    - `/institution/at-risk/print` — A4 portrait, sayım kartları + risk tablosu
    - `/institution/activity-heatmap/print` — A4 landscape, heatmap grid table
    - `/institution/cohorts/print` — A4 landscape, 4 sekme 2x2 grid + WoW header
  - Sidebar: 4 disabled item aktif (Risk Paneli / Kohort / Aktivite / Tükenmişlik)
  - **Verify**: tsc ✅ · eslint ✅ · build ✅ (4 görüntüleme + 3 print = 7 yeni route)
- **D4 Paket 6 — Frontend davet & digest**:
  - `lib/types/institution.ts` — `AdminDigestPayload` detay tipi (totals,
    completion, at_risk, highlight, inactive_teachers, grade_cohorts)
  - `lib/api/institution.ts` — 3 yeni fetcher (invitations, admin-digest list,
    admin-digest detail) + 3 queryKey
  - `lib/hooks/use-institution-mutations.ts` — 3 yeni mutation hook:
    createInvitation (open/targeted) + revokeInvitation + sendAdminDigestNow
  - 3 yeni route:
    - `/institution/invitations` — güvenlik notu (violet) + tablo + 4 statü
      rozeti (pending/consumed/expired/revoked) + link copy + revoke confirm;
      "Yeni Davetiye" dialog (ad+email opsiyonel, "açık davetiye" varyantı)
    - `/institution/admin-digest` — otomatik gönderim notu (Pazartesi 12:00),
      "Şimdi Gönder" confirm dialog (force=True), 12 hafta arşiv tablo,
      4 send_status TR etiket (sent/log_only/failed/skipped_no_admin)
    - `/institution/admin-digest/[id]` — 4 KPI (öğretmen+pasif uyarı / öğrenci
      / tamamlama+delta+yön / risk+kritik) + Highlights (en iyi/en kötü sınıf)
      + pasif öğretmenler listesi (amber, +N daha) + sınıf kohort tablo +
      alıcı email listesi (collapsible)
  - Sidebar: 2 disabled item aktif (Davet, Haftalık Özet) — Üyelik grubu hâlâ
    P7 için disabled
  - **Verify**: tsc ✅ · eslint ✅ · build ✅ (3 yeni route)
- **D4 Paket 7 — Frontend abonelik & ticari**:
  - `lib/types/institution.ts` — 11 yeni tip (SubscriptionResponse / Status /
    GuaranteeEvaluation / QuotaResponse / QuotaInfoItem / PlanQuotaItem /
    UsageResponse / UsageAccount / Breakdown / DailyPoint / Event)
  - `lib/api/institution.ts` — 3 yeni fetcher + 3 queryKey
    (subscription / quota / usage(days))
  - `lib/hooks/use-institution-mutations.ts` — 4 abonelik aksiyon mutation
    (switchAcademicYear / pauseForSummer / resumeFromPause / enableGuarantee)
    + `summer_window_required` / `pause_not_allowed` errorTitle eşlemeleri
  - 3 yeni route:
    - `/institution/subscription` — kind badge'li durum kartı (period_end/
      pause_until/guarantee dahil 4 alanlı dl), akademik yıl promosyon kartı
      (`can_switch_to_academic_year`), yaz pause kartı (`can_pause` →
      PauseAction · `can_resume` → ResumeAction · değilse PauseHelpline ile
      "akademik yıl gerekli" veya "yaz penceresi gerekli" uyarısı), 60g garanti
      kartı (enable veya GuaranteeDetails: 60-gün ilerleme bar, eşik vs.
      mevcut tamamlama tabular, already_extended/triggered/note ayrımı);
      sidebar: Avantajlar (4-madde checklist) + Yardım (pricing / plans/me /
      destek email); 4 ayrı confirm dialog (Jinja onConfirm metinleri birebir)
    - `/institution/quota` — 3 quota kartı (is_at_limit=rose/is_warn=amber/
      normal=emerald progress bar) + has_override "size özel" badge
      (violet, override_note title) + is_unlimited "∞ sınırsız" durumu;
      plan karşılaştırma tablo (mevcut plan satır emerald + "sizin planınız"
      badge); 2 bilgi notu (sayım nasıl / limit dolarsa)
    - `/institution/usage` — 3 koşullu banner (hard_block / %80 warn /
      %100 overuse), ana bakiye kartı (used/allocated/+bonus/remaining +
      0-100 progress + scale 0%/N%/100%), tip kırılımı (her tip için
      kendi progress bar 0..100), 30 günlük Recharts bar chart
      (`usage-daily-bar-chart.tsx` indigo + custom tooltip), plan/birim
      maliyet stat'ları + 5 kind cost chip'i, son 50 event tablosu (ne zaman
      DD.MM HH:mm / etiketli kind / kredi mono / aktör)
  - Sidebar: 3 son disabled item aktif (Abonelik, Kredi Kullanımı, Limitler)
  - **Verify**: tsc ✅ · eslint ✅ · build ✅ (3 yeni route — toplam 19 route
    /(institution) grubu altında); backend smoke P3 18/18 + tenant 29/29
- Tenant izolasyon regresyon **29/29 yeşil** + tüm institution smoke (P1+P2+P3)
  **55/55 yeşil**

- **D4 Paket 8 — Caddy yönlendirme + tam regresyon**:
  - `deploy/Caddyfile`:
    - `@prints` istisna bloğu **kaldırıldı** (3 institution print path Next.js
      `(print)` route group altında P5'te yapılmıştı, hâlâ FastAPI'ye gidiyordu)
    - `/institution` + `/institution/*` reverse_proxy yorumları **açıldı**
      (öğretmen/öğrenci pattern'i ile aynı — `next:3000`)
    - Yorum metinleri P8 tarihiyle güncellendi
    - Stale "/student/week/print + weekly-report/print @prints'te" yorumu temizlendi
  - Caddy reload kullanıcının canlı ortamında: `docker compose exec proxy caddy
    reload --config /etc/caddy/Caddyfile`. <60 sn rollback (R-020).
  - Tam regresyon **otomatik** (84 senaryo geçti):
    - institution P1 18/18 · P2 19/19 · P3 18/18 · tenant_isolation 29/29 ✅
    - frontend tsc ✅ · eslint ✅ · build ✅ (18 institution route)
  - Manuel smoke (canlı ortam): admin login → 13 sidebar item tek tek
    açılıp doğrulanır — bu adım kullanıcının sorumluluğunda
  - Jinja `/institution/*` (28 route + 17 template) "asılı bırakılanlar"
    listesine eklendi (silinmez — kullanıcı kararı)

## Dalga 5 — son durumu (2026-05-19)

**Tamamlanan paketler:**

- **D5 Aşama 1+2** — KURAL 1: /parent envanteri (34 dosya, 10K+ satır)
  haritalandı; parent.py (767) + parent_view.py (334) + parent_invitation.py
  (159) + 10 template + parent.py model (358) tam okundu.
- **D5 Paket 1 — Backend API v2 foundation**:
  - `app/routes/api_v2/schemas/parent.py` (26 model)
  - `app/routes/api_v2/parent.py` (10 endpoint: dashboard / students[id] /
    students[id]/week / notifications / settings + 5 mutation:
    preferences / child-mute / WA start+verify+disable)
  - `_require_parent` dep (role kapısı + 403 role_required)
  - Privacy guard: assert_parent_can_view → 404 (sızıntı önleme)
  - OTP güvenliği: 60s cooldown / 10dk TTL / 5 max attempts /
    secrets.compare_digest
  - ParentSessionLog audit (preferences_updated / child_muted / whatsapp_*)
  - `scripts/test_api_v2_parent.py` — **20/20 yeşil**
- **D5 Paket 2 — Backend davet & unsubscribe (public)**:
  - 3 endpoint: GET invitation/{token}, POST invitation/{token}/accept,
    GET unsubscribe/{token}
  - Davet token: 4 hata durumu (not_found/expired/consumed/email_in_use)
  - Form validasyon: name>=3, password>=8, password_confirm match, kvkk_accept
  - can_register_parent_email: TEACHER/STUDENT email → 400 reddet
  - Mevcut PARENT → link ekle (şifre/ad değişmez, çoklu çocuk senaryosu)
  - Audit: invitation_accepted / invitation_added_link + login
  - JWT BFF cookie kuruldu (Jinja session yerine API v2 auth)
  - `scripts/test_api_v2_parent_invitation.py` — **17/17 yeşil**
- **D5 Paket 3 — Frontend foundation + dashboard + public sayfalar**:
  - `lib/types/parent.ts` (24 interface) + `lib/api/parent.ts` (7 fetcher) +
    `lib/hooks/use-parent-mutations.ts` (5 mutation + 15 error code label)
  - `(parent)/layout.tsx` auth guard
  - `parent-shell.tsx` — teal accent (#117A86) sticky header + mobile drawer
  - `(parent)/parent/page.tsx` — Dashboard çocuk kartları (warning_level
    border-l-4 + tonal bg + bugün/hafta/7g rate/istikrar)
  - `parent/invitation/[token]/page.tsx` — public form + 4 hata ekranı
  - `parent/unsubscribe/[token]/page.tsx` — public 3 durum
  - `legal/kvkk-veli/page.tsx` — KVKK aydınlatma 7 bölüm
- **D5 Paket 4 — Frontend: student detail & week**:
  - `parent/students/[id]/page.tsx` + client: 4 metrik + Projeksiyon (status
    pill) + Ders progress (hue rotation) + **Recharts 30g BarChart** +
    Öğretmen notları (teal left-border)
  - `parent/students/[id]/week/page.tsx` + client: gün accordion auto-expand
    dolu günler + subject tonal background + book_items detail
- **D5 Paket 5 — Frontend: notifications & settings**:
  - `parent/notifications/page.tsx` — 100 bildirim list, kind/channel/status
    badge'leri, empty state
  - `parent/settings/page.tsx` — 3 bölüm: Preferences (7 toggle + quiet hours)
    + Çocuk-başı mute (per-row badge + confirm dialog) + WhatsApp 3 durum
    (kapalı / kod bekleniyor / aktif) + DEV stub kod gösterimi
- **D5 Paket 6 — Caddy + tam regresyon + arşivleme**:
  - `deploy/Caddyfile`:
    - `/parent` + `/parent/*` reverse_proxy Next.js'e aç
    - `/legal/kvkk-veli` Next.js'e (generic /legal/* ÖNCE)
  - Tam regresyon (121/121 yeşil):
    - parent P1 20/20 · P2 17/17 · institution P1+P2+P3 55/55 · tenant 29/29
    - tsc ✅ · eslint ✅ · build ✅ (8 yeni parent route)
  - Jinja `/parent/*` (15 route + 10 template) "asılı bırakılanlar"a eklendi
- **Backend notification infra DOKUNULMAMIŞ**:
  - `app/services/notification_producer.py` + `notification_producers.py` +
    `notification_dispatcher.py` + `event_triggers.py` + `cron_jobs.py` +
    `whatsapp.py` + `whatsapp_webhook.py` + 8 email Jinja template — hepsi
    server-side e-posta/WA gönderim için gerekli, korundu.

## Dalga 6 — son durumu (2026-05-19)

**Envanter (Aşama 1+2 admin.py için):**
- Jinja `app/routes/admin.py` 6154 satır, **133 endpoint** tek monolit
- 50 template (`app/templates/admin/*.html` — 12.778 satır)
- 27 service (10.721 satır) — tenant_health, audit, revenue_panel,
  campaigns, offers, dunning, action_center, institution_360, feature_*,
  security_monitor, alarm_engine, abuse_detection, abuse_remediation,
  data_integrity, account_history, impersonation, error_capture, vb.
- 24 admin-spesifik model (3.086 satır) — Owner-pattern (institution|user)
  6 ana modelde (Invoice, Campaign, CRM, HealthScoreSnapshot,
  PlanChangeHistory, CreditAccount)
- **Owner-pattern KRİTİK**: Bağımsız öğretmen (TEACHER + institution_id=NULL)
  = ticari panoda birinci sınıf tenant
- `/api/v2/admin/*` SIFIR — tamamı sıfırdan inşa edilecek

**14 paket yol haritası onaylandı** (kullanıcı 2026-05-19):
- P1-P5: Çekirdek Yönetim
- P6-P10: Ticari Pano (Owner-pattern korunarak)
- P11-P12: Feature Catalog
- P13-P14: Güvenlik Kamarası + Caddy/regresyon

**Tamamlanan paketler:**

- **D6 Paket 1 — Backend foundation + Dashboard**:
  - `app/routes/api_v2/schemas/admin.py` (12 Pydantic model: counts,
    health summary/assessment/indicator, independent teacher activity,
    audit item, dashboard response)
  - `app/routes/api_v2/admin.py` — `_require_super_admin` dep +
    `GET /api/v2/admin/dashboard`:
    - 8 alanlı counts (Jinja birebir)
    - bulk_health_assessment + churn_summary + top-3 unhealthy
    - _independent_teacher_activity_payload (4 bant: healthy/watch/risk/
      critical login heuristiği — Jinja `_independent_teacher_activity()`
      ile birebir aynı algoritma)
    - recent_audits (son 10 + action_label + via_admin impersonation marker)
    - failed_logins_24h (LOGIN_FAILED+LOGIN_LOCKED son 24h sayım)
  - `web/lib/types/admin.ts` (11 interface) + `lib/api/admin.ts`
    (adminKeys + getAdminDashboard fetcher)
  - `web/app/(admin)/layout.tsx` — auth guard + redirect (5 rol mapping)
  - `web/components/admin/admin-shell.tsx` — sticky sidebar (lg+) + mobile
    drawer; 7 nav grup iskeleti (Panel + Kuruluşlar + Denetim + Limitler &
    Kullanım + Vitrin + Ticari Pano + Güvenlik Kamarası); P1 sonrası
    item'lar "yakında" disabled görünür; slate-900 brand header + amber
    "Süper" rozeti
  - `web/app/(admin)/admin/page.tsx` + `admin-dashboard-client.tsx` —
    6 bölüm: Hesap Özeti (4 OverviewCard, indigo/violet/sky/amber tonal),
    Failed Logins banner (>10), Commercial Shortcuts grid (7 kısayol — P6+),
    System Shortcuts grid (4 kısayol — P11+), Müşteri Sağlığı 2 sütun
    (kurum + bağımsız öğretmen 4-band stat + top-3 risk), Recent Audits
    table (action_class renkli + via_admin pill)
  - `scripts/test_api_v2_admin.py` — **13/13 yeşil** (happy + 4 shape check
    + 4 role guard + 1 anonim)
  - Verify: tsc ✅ · eslint ✅ · build ✅ (1 yeni route `/admin`)

- **D6 Paket 2 — Backend institutions + account-history (Owner-pattern)**:
  - `app/routes/api_v2/schemas/admin.py` — 18 yeni Pydantic model (institutions
    list/detail/CRUD + account-history poly + backup summary)
  - `app/routes/api_v2/admin.py` — 11 yeni endpoint:
    - `GET /institutions` (sort=health/name/created + filter_level=unhealthy/critical)
    - `POST /institutions` (slug auto-gen + çakışma kontrolü 409)
    - `GET /institutions/{id}` (sağlık + admin/teacher listeleri)
    - `POST /institutions/{id}` (edit — before/after diff audit)
    - `POST /institutions/{id}/delete` (cascade: User.institution_id SET NULL)
    - `GET /institutions/{id}/backup` (counts + size_bytes summary)
    - `GET /institutions/{id}/backup.json` (raw JSON download, password REDACTED)
    - `GET /account-history/{owner_type}/{owner_id}` (poly institution|user;
      years 1-10, include_archived flag)
    - `POST /account-history/archive` (tek kayıt — plan|invoice)
    - `POST /account-history/unarchive` (geri al)
    - `POST /account-history/bulk-archive` (X yıldan eski tümü)
  - `_slugify` helper (Türkçe karakter destekli, Jinja birebir)
  - Tüm mutation'larda audit (INSTITUTION_CREATE/UPDATE/DELETE +
    USER_UPDATE for archive ops)
- **D6 Paket 2 — Frontend institutions UI + account-history**:
  - `lib/types/admin.ts` — 18 yeni interface
  - `lib/api/admin.ts` — 5 fetcher + adminKeys.institutions/institution/
    backup/accountHistory + adminInstitutionBackupDownloadUrl
  - `lib/hooks/use-admin-mutations.ts` (yeni) — 6 mutation (create/edit/
    delete + archive/unarchive/bulk-archive) + 5 error code label
  - `(admin)/admin/institutions/page.tsx` + `admin-institutions-client.tsx`:
    - 4 health KPI rozet (emerald/yellow/amber/rose)
    - Sort + Filter chip-bar (URL-based navigation)
    - Tablo: sağlık badge + ad/slug + plan + öğr/öğr sayım + 7g aktivite
      progress bars (indigo/emerald) + durum + detay link
    - "Yeni Kurum" Dialog (name+slug+contact+plan, slug auto-gen hint)
  - `(admin)/admin/institutions/[id]/page.tsx` + detail client:
    - Header (status + plan rozetleri)
    - Health card (5xl emoji + score + 4 stat + indicators)
    - 2 sütun: edit form (name/email/plan/is_active) / sayım+backup+danger
    - Backup card (violet, download .json)
    - Danger zone (rose, delete confirm dialog)
    - Admin + teacher list 2 sütun
  - `account-history-client.tsx` (paylaşımlı poly):
    - Help details collapsible
    - 4 KPI (gösterilen/arşivli/eski/pencere başı)
    - Filter form (years selector + include_archived toggle)
    - Bulk archive button + confirm dialog (older_count > 0 ise)
    - Event timeline (her event: tarih + badge + record_type#id + arşivli rozet
      + title + subtitle + archive_note + archive/unarchive button)
  - 2 sayfa: `/admin/institutions/[id]/account-history` (institution)
    ve `/admin/users/[id]/account-history` (user, Owner-pattern)
  - Sidebar: Kurumlar item aktive (Bağımsız Öğretmenler/Kullanıcılar hâlâ
    disabled — P3'te aktive)
  - `scripts/test_api_v2_admin_institutions.py` — **23/23 yeşil**
  - Verify: tsc ✅ · eslint ✅ · build ✅ (4 yeni route)

- **D6 Paket 3 — Backend users + impersonate (1445 satır okundu)**:
  - `app/routes/api_v2/schemas/admin.py` — 12 yeni Pydantic model (users CRUD
    + impersonate + independent teachers response)
  - `app/routes/api_v2/admin.py` — 10 yeni endpoint:
    - `GET /users` (role + institution_id + q filter, 500 cap + truncated flag)
    - `POST /users` (slug değil — email kontrolü 409; sistem rol-bazlı güçlü
      geçici şifre + must_change=True; INSTITUTION_ADMIN için kurum zorunlu)
    - `GET /users/{id}` (detail + institutions + recent_audits + is_self flag)
    - `POST /users/{id}` (edit — email çakışma 409 + before/after diff +
      USER_DEACTIVATE audit)
    - `POST /users/{id}/reset-password` (temp_password issued + must_change +
      kilit aç + audit)
    - `POST /users/{id}/change-role` (kendi rolü → 403 + INSTITUTION_ADMIN
      kurum zorunlu)
    - `POST /users/{id}/delete` (kendi hesabı → 403 + CASCADE)
    - `POST /users/{id}/impersonate` (reason 10-200 char + 3 kısıt: self/
      super_admin/inactive yasak + idempotent + SessionMiddleware target set)
    - `POST /impersonate/end` (auth zorunlu DEĞİL — impersonator_id session'dan)
    - `GET /independent-teachers` (login-bazlı 4-band heuristik P1 ile aynı)
  - `auth_security.generate_strong_password(role)` (14/12/10/8 rol-bazlı uzunluk)
  - `impersonation.validate_reason + start_session + end_session + 30dk TTL`
- **D6 Paket 3 — Frontend users UI**:
  - `lib/types/admin.ts` — 14 yeni interface (AdminUserListItem + Create/Edit/
    ChangeRole/Detail/Mutation + Impersonate + IndependentTeachers)
  - `lib/api/admin.ts` — 3 fetcher (getAdminUsers + getAdminUser +
    getAdminIndependentTeachers) + adminKeys.users/user/independentTeachers
  - `lib/hooks/use-admin-mutations.ts` — 7 mutation hook (Create + Edit +
    ResetPassword + ChangeRole + Delete + Impersonate + EndImpersonation) +
    14 yeni error code label
  - `(admin)/admin/users/page.tsx` + `admin-users-client.tsx`:
    - URL-based filter form (q + role + institution)
    - Tablo: ad/email/rol-badge (5 renk)/kurum/son giriş/kilit-pasif rozet
    - Yeni Kullanıcı Dialog (5 rol opt + kurum select + 🔐 güvenlik notu)
    - `TempPasswordDialog` (re-usable, "Kopyala" butonu + DOM clipboard API)
  - `(admin)/admin/users/[id]/page.tsx` + `admin-user-detail-client.tsx`:
    - Header (5 renk rol badge + kilit/pasif rozet + hesap hareketleri buton
      teacher/admin/super_admin için)
    - 2 sütun: EditUserForm + (SecurityCard + ChangeRoleCard + ImpersonateCard
      + DangerZone)
    - SecurityCard: 5 alan dl + Reset şifre confirm dialog → TempPasswordDialog
    - ChangeRoleCard: rol + kurum dropdown + audit onay dialog
    - ImpersonateCard: gerekçe textarea (min-10) + confirm dialog + redirect
      window.location.href (session set sonrası Jinja path'e)
    - DangerZone: kullanıcıyı sil confirm + audit
    - Self mode: yukarıdaki kartlar gizli + amber "/me/account kullan" notu
    - Recent activity tablosu (son 10 audit)
  - `(admin)/admin/independent-teachers/page.tsx` + client:
    - 4 BandKpi rozet (emerald/yellow/amber/rose, summary'den)
    - Tablo: band-pill + ad/email/son giriş label + detay link
  - Sidebar: Kullanıcılar + Bağımsız Öğretmenler item'ları aktive (P2-P3 kapandı)
  - `scripts/test_api_v2_admin_users.py` — **25/25 yeşil** (list/filter/search
    + 5 mutation × 3 path + 5 impersonate guard + 2 role/anon guard)
  - Verify: tsc ✅ · eslint ✅ · build ✅ (4 yeni route)
- **D6 P1+P2+P3 tam regresyon: 182/182 yeşil**:
  - admin P1 13 + P2 23 + P3 25 = 61
  - parent P1 20 + P2 17 = 37
  - institution P1 18 + P2 19 + P3 18 = 55
  - tenant isolation 29

- **D6 Paket 4 — Backend audit + KVKK + system-health + announcements (1895 satır okundu)**:
  - `app/routes/api_v2/schemas/admin.py` — 18 yeni Pydantic model
  - `app/routes/api_v2/admin.py` — 8 yeni endpoint:
    - `GET /audit` (50/sayfa pagination + 4 filter: action/actor_id/start_date/
      end_date inclusive + before/after diff parse + via_admin map)
    - `GET /system-health` (3 alt-bileşen: crons/dispatcher/database +
      overall_health en kötü; cron warn 25h/crit 48h günlük + 8d haftalık;
      dispatcher 100/6h warn + 500/24h crit; DB 500MB/1GB)
    - `GET /announcements` (son 50 + severities + audiences enum)
    - `POST /announcements` (severity + audience + starts_at/ends_at +
      dismissible + 60s cache invalidate)
    - `POST /announcements/{id}/delete` (audit + cache invalidate)
    - `GET /kvkk` (summary 5 status + pending_rows + recent_rows +
      DATA_INVENTORY 10+ kayıt)
    - `POST /kvkk/requests/{id}/apply` (apply_deletion: anonimize
      email=anonymized-{id}@kvkk.local, password_hash="", is_active=False +
      USER_DELETE audit; export tipi → 400 only_delete_can_be_applied)
    - `POST /kvkk/requests/{id}/reject` (status=REJECTED + admin_note 500 char)
- **D6 Paket 4 — Frontend**:
  - `lib/types/admin.ts` — 18 yeni interface (Audit + SystemHealth + Announcements
    + Kvkk)
  - `lib/api/admin.ts` — 4 fetcher (getAdminAudit/SystemHealth/Announcements/
    Kvkk) + 4 queryKey (audit/systemHealth/announcements/kvkk)
  - `lib/hooks/use-admin-mutations.ts` — 4 mutation hook (CreateAnnouncement +
    DeleteAnnouncement + KvkkApply + KvkkReject) + 6 yeni error code label
  - `(admin)/admin/audit/page.tsx` + `admin-audit-client.tsx`:
    - 4 filter form (action select + actor_id input + start/end date)
    - Hızlı kısayollar (24h / 7g / 30g)
    - Pagination 50/sayfa (← Önceki / N/M / Sonraki →)
    - Tablo: zaman + olay (renkli + label) + aktör (link + via_admin pill) +
      email_attempted + hedef (link to user/inst detail) + IP + detay
      (before/after diff yan yana JSON)
  - `(admin)/admin/system-health/page.tsx` + client:
    - Overall status banner (3 renk: ok/warn/crit + icon)
    - Cron table (job_key + schedule + son çalıştırma + status + health badge
      5 durum: ok/warn/crit/never/disabled)
    - Dispatcher kartı (queued + failed + oldest age + 3 health durumu)
    - Database kartı (file size + table counts + 500MB/1GB eşikleri)
  - `(admin)/admin/announcements/page.tsx` + client:
    - Create form (title + message + severity dropdown + audience dropdown +
      starts/ends datetime-local + dismissible checkbox)
    - Son 50 tablo (severity badge 3 renk + audience + yayın aralığı +
      yayında durumu + sil confirm dialog)
  - `(admin)/admin/kvkk/page.tsx` + client:
    - 5 durum sayım kartı (total + processing + pending + completed +
      cancelled/rejected)
    - Bekleyen talepler tablosu (kind label + hesap + tarihler + sebep +
      Hemen Uygula confirm + Reddet not'lu confirm)
    - Sistem veri envanteri tablosu (DATA_INVENTORY: tablo + PII + saklama +
      hukuki temel + amaç)
    - Son 20 talep özet tablosu (status badge 5 renk)
  - Sidebar: 4 Denetim item'ı aktive (Audit Log + KVKK + Sistem Sağlığı + Duyurular)
  - `scripts/test_api_v2_admin_audit_kvkk.py` — **18/18 yeşil**
  - Verify: tsc ✅ · eslint ✅ · build ✅ (4 yeni route)
- **D6 P1+P2+P3+P4 tam regresyon: 200/200 yeşil** (admin 79 + parent 37 +
  institution 55 + tenant 29)

- **D6 Paket 5 — Backend usage + quota + feature-flags (1469 satır okundu)**:
  - `app/routes/api_v2/schemas/admin.py` — 22 yeni Pydantic model
  - `app/routes/api_v2/admin.py` — 11 yeni endpoint:
    - `GET /usage` (owner-pattern 2 grup: kurumlar + bağımsız öğretmenler,
      CreditAccount usage_pct sıralı + totals + kind_costs)
    - `POST /usage/institution/{id}/hard-block` (sadece kurum, toggle)
    - `POST /usage/{owner_type}/{id}/bonus` (1-100000, kurum|user)
    - `GET /quota` (kurum × quota_key tablosu + plan defaults)
    - `POST /quota/{id}/override` (-1/0/N validation)
    - `POST /quota/overrides/{id}/delete`
    - `GET /feature-flags` (all_flags_for_admin + override sayım)
    - `GET /feature-flags/{id}` (override liste + available_institutions)
    - `POST /feature-flags/{id}/toggle` (global + 60s cache invalidate)
    - `POST /feature-flags/{id}/overrides` (set_override + cache invalidate)
    - `POST /feature-flags/overrides/{id}/delete`
- **D6 Paket 5 — Frontend**:
  - `lib/types/admin.ts` — 22 yeni interface (Usage + Quota + FeatureFlag)
  - `lib/api/admin.ts` — 4 fetcher + 4 queryKey
  - `lib/hooks/use-admin-mutations.ts` — 6 mutation hook (HardBlockToggle +
    AddBonus + SetQuotaOverride + RemoveQuotaOverride + ToggleFeatureFlag +
    AddFeatureFlagOverride + RemoveFeatureFlagOverride) + 6 error code label
  - `(admin)/admin/usage/page.tsx` + client:
    - 4 özet kart + 2 sekme (kurumlar/bağımsız) + UsageBar (3-renk) +
      hard-block confirm dialog (sadece kurum) + bonus dialog (her ikisi)
  - `(admin)/admin/quota/page.tsx` + client:
    - Kurum × quota_key tablosu (current/limit + progress + özel badge) +
      "Özel Limit" dialog (-1/0/N hint) + plan default tablosu
  - `(admin)/admin/feature-flags/page.tsx` + client:
    - Tablo (key + açıklama + global toggle confirm + override sayım)
  - `(admin)/admin/feature-flags/[id]/page.tsx` + client:
    - Global toggle kartı + override tablosu (kaldır confirm) + override
      ekleme formu (kurum + açık/kapalı + not)
  - Sidebar: 3 "Limitler & Kullanım" item'ı aktive
  - `scripts/test_api_v2_admin_usage_quota_flags.py` — **21/21 yeşil**
  - Verify: tsc ✅ · eslint ✅ · build ✅ (4 yeni route)
- **D6 P1-P5 tam regresyon: 221/221 yeşil** (admin 100 + parent 37 +
  institution 55 + tenant 29)
- **D6 Paket 6 — Feature Catalog (Vitrin Kartları)**:
  - KURAL 1: 17 endpoint (admin.py:1847-2800) + 4 model + 8 servis
    (feature_catalog/feature_discovery/feature_scoring/experiments/
    curator_dashboard/telemetry/bandit/diversity + landing_strategies/
    mockup_registry) + 7 template **sonuna kadar okundu**; Files-Read Receipt +
    veri yapısı/akış raporu + parite tablosu üretildi (~5000 satır).
  - **Mimari karar**: 8 destek servisi (Mamdani fuzzy / LinUCB / MMR / Wilson CI)
    HİÇ değişmedi — API v2 endpoint'leri AYNEN import edip çağırıyor, sadece
    dönen nesneler Pydantic'e serialize ediliyor. Veri yapısı/sorgu mutlak korundu.
  - Backend: `schemas/admin.py` +~30 model (list/form/dashboard/discovery/
    experiment + 6 mutation body); `api_v2/admin.py` +17 endpoint
    (`_fc_invalidate`/`_fc_parse_dt`/`_fc_discovery_pending`/enum-option helper'ları).
    REST düzeltmesi: create=POST /feature-catalog, update=POST /{id}.
  - `scripts/test_api_v2_admin_feature_catalog.py` — **25/25 yeşil**
  - Frontend: `lib/types/admin.ts` +~35 tip · `lib/api/admin.ts` +9 fetcher +
    queryKey · `use-admin-mutations.ts` +9 mutation hook · `feature-catalog-ui.tsx`
    (statik tone map — Tailwind purge güvenli badge/anomali/skor tonları)
  - 8 route + 7 client:
    - `/feature-catalog` list (masaüstü tablo + mobil kart-grid; skor/telemetri/
      🧠bandit/🎨çeşitlilik rozetleri; sağlık bandı; durum sayım filtresi)
    - `/feature-catalog/new` + `/[id]` ortak form (26 alan; accordion bölümler;
      hedef rol checkbox; öncelik slider; tehlikeli aksiyon sil dialog)
    - `/feature-catalog/dashboard` (6 KPI + anasayfa sağlığı + son 7g + aktif
      deney + anomali + son hareketler)
    - `/feature-catalog/discovery-queue` (checkbox toplu reddet/sil + tekil;
      kaynak filtre; reddedilenleri göster toggle)
    - `/feature-catalog/experiments` list + `/new` form (ctrl+test variant,
      ağırlık 100 doğrulama) + `/[id]` detay (Wilson CI bar + durum aksiyonları)
  - Sidebar: "Vitrin" grubu 3 item aktive (Kartlar/Vitrin Yönetimi/Deneyler)
  - Verify: tsc ✅ · eslint ✅ · build ✅ (8 yeni route)
- **D6 P1-P6 tam regresyon: 246/246 yeşil** (admin 125 + parent 37 +
  institution 55 + tenant 29)

## Dalga 6 — Ticari Pano (Paket 7) son durumu (2026-05-20)

**Kapsam kararı (kullanıcı 2026-05-20):** `/admin/revenue/*` = 44 endpoint /
13 servis / 11 template / ~12K satır. **4 alt-pakete bölündü** (her biri kendi
KURAL 1 receipt + smoke + regresyon ile):
- **P7a — Analitik çekirdek**: Aksiyon Merkezi + Gelir Tahmini + Kohort/LTV
- **P7b — 360 + CRM**: Kurum 360 + Bağımsız Öğretmen 360 + CRM (not/aksiyon/
  iletişim/etiket) — en büyük, mutation-yoğun
- **P7c — Teklifler + Aksiyon Şablonları**: offers + action-templates + crm_templates
- **P7d — Kampanyalar**: campaigns (10 endpoint)

Güvenlik Kamarası (`/admin/security-monitor/*`) **ayrı oturuma** bırakıldı
(kullanıcı kararı). `_revenue_drill.html` + `/security-monitor/revenue` o tarafta.

- **D6 Paket 7a — Ticari Pano: Analitik çekirdek**:
  - KURAL 1: `/revenue/action-center` (3456) + `/forecast` (3901) + `/cohort`
    (3940) + `/action-center/quick-action` (3981) endpoint'leri + `action_center.py`
    (430) + `revenue_forecast.py` (395) + `revenue_cohort.py` (420) +
    `institution_360.create_action` + 3 template (action_center/revenue_forecast/
    revenue_cohort) **sonuna kadar okundu**; Files-Read Receipt + veri akışı raporu.
  - **Mimari karar**: 3 analitik servisi + create_action HİÇ değişmedi —
    API v2 endpoint'leri AYNEN import edip çağırıyor, dataclass/dict'ler
    Pydantic'e serialize. Owner-pattern korundu (risk_at_mrr bağımsız
    öğretmenleri `owner_type="user"` döndürür).
  - Backend: `schemas/admin.py` +~25 model (action-center/forecast/cohort) ·
    `api_v2/admin.py` +4 endpoint + `_revenue_invalidate` helper'ı
  - `scripts/test_api_v2_admin_revenue_analytics.py` — **9/9 yeşil**
  - Frontend (emoji yok — Lucide ikon): `lib/types/admin.ts` +~20 tip ·
    `lib/api/admin.ts` +3 fetcher + queryKey · `use-admin-mutations.ts` +1
    mutation (quick-action) · `revenue-ui.tsx` (kind→Lucide ikon map +
    severity/cohort statik ton map'leri)
  - 3 route + 3 client:
    - `/revenue/action-center` — 5 KPI + sinyal kartları (total_score rozeti +
      primary/other sinyaller + önerilen aksiyon butonları → quick-action 3g takip)
    - `/revenue/forecast` — save_rate seçici + 4 KPI + 30/60/90 projeksiyon tablo +
      risk altı kurum tablosu (owner ayrımı) + senaryo karşılaştırma 2 sütun
    - `/revenue/cohort` — 3 filtre + 6 plan-hareketi KPI + tutunma heatmap matrisi +
      yaşam değeri (LTV `JargonTooltip` ile) 3 KPI + plan tablosu
  - Sidebar: "Ticari Pano" grubu 3 item aktive (Aksiyon Merkezi/Tahmin/Kohort & LTV);
    Kampanyalar + Şablonlar P7c/P7d için disabled
  - Verify: tsc ✅ · eslint ✅ (lgs/no-bare-jargon LTV düzeltmesi) · build ✅ (3 route)
- **D6 P1-P7a tam regresyon: 255/255 yeşil** (admin 134 + parent 37 +
  institution 55 + tenant 29)
- **D6 Paket 7b — Ticari Pano: 360 + CRM (Owner-pattern)**:
  - KURAL 1: 20 endpoint (institutions/{id} + users/{id} GET + CRM notes/actions
    + contact + tags) + `institution_360` (581) + `revenue_owner` (306) +
    `owner_contact` (65) + `owner_tags` (133) + `health_score_v2` public API +
    `crm`/`owner_tag`/`owner_contact` modelleri + 2 template (979+956)
    **sonuna kadar okundu**; Files-Read Receipt + veri akışı raporu.
  - **Mimari karar**: institution_360 + revenue_owner + owner_contact +
    owner_tags + health_score_v2 servisleri HİÇ değişmedi — AYNEN çağrıldı,
    dataclass/dict/ORM nesneleri Pydantic'e serialize edildi.
  - **Owner-pattern**: CRM/tag/contact `owner_type` ("institution"|"user") ile
    tek API yüzeyi; not/aksiyon/tag pin/delete/complete owner-agnostic (id ile).
  - **P7b/P7c sınırı**: offers + fatura mutation'ları + invoices_for_owner +
    action-templates P7c'ye bırakıldı. Billing sekmesi P7b'de read (plan +
    özet + plan değişiklik geçmişi).
  - Backend: `schemas/admin.py` +~35 model · `api_v2/admin.py` +11 endpoint
    (`_rev360_invalidate`/`_crm_meta`/note·action·tag·contact·health dönüştürücü
    helper'ları)
  - `scripts/test_api_v2_admin_revenue_360.py` — **18/18 yeşil**
  - Frontend (emoji yok — Lucide): types +~35 · api +2 fetcher + queryKey ·
    mutations +9 hook · `revenue-360-shared.tsx` (HealthV2Card + CrmNotesPanel +
    CrmActionsPanel + ContactAndTagsPanel + PlanChangesTimeline + TabBar + statik
    ton map)
  - 2 route + 2 client (sekmeli, mobil-dostu):
    - `/revenue/institutions/[id]` — Sağlık&Riskler / Kullanım / Plan&Ödeme /
      Notlar / Aksiyonlar / İletişim&Etiketler + 4 KPI + sağlık v2 + risk listesi
    - `/revenue/users/[id]` — Sağlık / Öğrenciler / Kullanım / Plan&Ödeme /
      Notlar / Aksiyonlar / İletişim&Etiketler + öğrenci sağlık tablosu
  - Navigasyon: action-center kurum adları + "Kurum 360" linki, forecast risk
    tablosu isimleri → 360 detay (owner-aware detail_url)
  - Verify: tsc ✅ · eslint ✅ (set-state-in-effect düzeltmesi) · build ✅ (2 route)
- **D6 P1-P7b tam regresyon: 273/273 yeşil** (admin 152 + parent 37 +
  institution 55 + tenant 29)
- **D6 Paket 7c — Ticari Pano: Teklifler + Aksiyon Şablonları + Tahsilat**:
  - KURAL 1: 15 endpoint (offers create/send/cancel ×2 owner + invoice
    postpone/mark-paid/cancel/send-reminder + action-templates CRUD/render) +
    `offers.py` (446) + `crm_templates.py` (192) + `dunning.send_reminder` +
    `revenue_panel.invoices_for_owner`/`_invoice_row` + offer/crm_template/invoice
    modelleri + `action_templates.html` **sonuna kadar okundu**.
  - **Mimari karar**: offers / crm_templates / dunning servisleri HİÇ değişmedi —
    AYNEN çağrıldı. Invoice mark-paid/cancel/postpone (Jinja'da inline model
    mutation) aynı mantıkla API v2'de korundu. Owner-pattern: offer/invoice
    mutation'ları nesneden owner türetip 360 cache'ini bayatlar.
  - **360 entegrasyonu**: P7b'de boş bırakılan Teklifler sekmesi + billing fatura
    listesi şimdi dolu — 360 GET response'larına `offers` + `invoices` +
    `meta.offer_kinds` eklendi (tek query ile sekmeler dolar).
  - Backend: `schemas/admin.py` +~15 model · `api_v2/admin.py` +12 endpoint
    (`_offer_item`/`_invoice_item`/`_action_template_item`/owner-invalidate
    helper'ları). REST: create=POST /action-templates, update=POST /{id}.
  - `scripts/test_api_v2_admin_revenue_offers.py` — **19/19 yeşil**
  - Frontend (emoji yok — Lucide): types +~15 · api +1 fetcher + queryKey ·
    mutations +10 hook · `revenue-360-shared.tsx`'e `OffersPanel` +
    `InvoicesTable` (tahsilat: hatırlat/ötele/öden/iptal) eklendi
  - 360 sayfaları: Teklifler sekmesi (oluştur/gönder/iptal + public link) +
    billing'e fatura tablosu (mutation'lı) · yeni `/revenue/action-templates`
    sayfası (CRUD + accordion + inline düzenle) · sidebar "Şablonlar" aktive
  - Verify: tsc ✅ · eslint ✅ · build ✅ (1 yeni route — toplam 27 revenue endpoint)
- **D6 P1-P7c tam regresyon: 292/292 yeşil** (admin 171 + parent 37 +
  institution 55 + tenant 29)
- **Erişim iyileştirmesi**: Ticari 360 sayfalarına Kuruluşlar→Kurumlar ve
  →Bağımsız Öğretmenler listelerinden "Ticari 360" linki eklendi (eskiden sadece
  Aksiyon Merkezi/Tahmin'den koşullu erişiliyordu).
- **D6 Paket 7d — Ticari Pano: Toplu Kampanyalar**:
  - KURAL 1: 10 endpoint (list/new-meta/preview/create/detail + lifecycle
    launch/pause/resume/complete/cancel) + `campaigns.py` (695) + `campaign.py`
    modeli (Campaign + CampaignRecipient + Segment/Status/RecipientStatus enum) +
    4 template (campaigns_list/campaign_form/campaign_detail/_campaign_preview)
    **sonuna kadar okundu**.
  - **Mimari karar**: `campaigns.py` HİÇ değişmedi — AYNEN çağrıldı. Owner-pattern:
    segment hedeflemesi kurum + bağımsız öğretmeni birlikte kapsar (preview_segment
    Owner döndürür); PAUSED_30D yalnız kurum. A/B: deterministik hash split,
    funnel her varyant ayrı (accepted_pct dönüşüm). Launch P7c offers servisini
    reuse eder (her hedefe Offer + CampaignRecipient + e-posta).
  - Backend: `schemas/admin.py` +~14 model · `api_v2/admin.py` +10 endpoint
    (`_campaign_funnel`/`_campaign_variant`/`_campaign_lifecycle` helper'ları).
    REST: create=POST /campaigns, lifecycle=POST /{id}/<action>.
  - `scripts/test_api_v2_admin_revenue_campaigns.py` — **17/17 yeşil**
  - Frontend (emoji yok — Lucide): types +~14 · api +3 fetcher + queryKey ·
    mutations +7 hook (preview/create + 5 lifecycle)
  - 3 route + 3 client:
    - `/revenue/campaigns` liste (funnel sütunlu tablo)
    - `/revenue/campaigns/new` form (segment radyo + **canlı önizleme** +
      A/B variant accordion)
    - `/revenue/campaigns/[id]` detay (funnel KPI + A/B karşılaştırma + kazanan
      banner + recipient tablosu + lifecycle butonları)
  - Sidebar "Kampanyalar" aktive — **Ticari Pano grubu tamamen aktif**
  - Verify: tsc ✅ · eslint ✅ · build ✅ (3 route — toplam 37 revenue endpoint)
- **D6 P1-P7d tam regresyon: 309/309 yeşil** (admin 188 + parent 37 +
  institution 55 + tenant 29)

## Dalga 6 — Güvenlik Kamarası (2026-05-20)

**Kapsam kararı (kullanıcı 2026-05-20):** `/admin/security-monitor/*` = 27
endpoint / 8 servis / 15 template / ~8K satır. **4 alt-pakete bölündü**
(her biri kendi KURAL 1 receipt + smoke + regresyon ile):
- **G1 — Ticari Ana Dashboard**: revenue + drill + invoices ✅
- **G2a — Genel Bakış + Sistem + Bildirim + Bütünlük** ✅ (2026-05-20)
- **G2b — Aktivite Kamerası** ✅ (2026-05-20)
- **G3 — Oturumlar + Canlı + IP + Impersonation** ✅ (2026-05-20)
- **G4 — Alarmlar + Suistimal** ✅ (2026-05-20)
Caddy `/admin/*` yönlendirmesi **en sonda** (tüm G paketleri bitince — yarım
taşınmış sayfalarda kırık link riski olmasın).

- **D6 Güvenlik Kamarası G1 — Ticari Ana Dashboard**:
  - KURAL 1: 3 endpoint (revenue + revenue/drill + revenue/invoices) +
    `revenue_panel.py` (969 — get_revenue_panel_data/mrr/plan_distribution/
    trial/plan_change/daily/churn/payment_calendar/drill_for_key) + revenue_owner
    (P7b) + 3 template (security_monitor_revenue 545, _revenue_drill 103,
    security_monitor_invoices 136) **sonuna kadar okundu**.
  - **Mimari karar**: revenue_panel + revenue_owner HİÇ değişmedi — AYNEN
    çağrıldı, hepsi salt-okunur. Owner-pattern segment toggle (Hepsi/Kurum/
    Bağımsız) korundu. Bu, P7 Ticari Pano'nun üst dashboard'u.
  - Backend: `schemas/admin.py` +~17 model · `api_v2/admin.py` +3 endpoint
    (drill için generic RevenueDrillRow — esnek opsiyonel alanlar)
  - `scripts/test_api_v2_admin_revenue_dashboard.py` — **11/11 yeşil**
  - Frontend (emoji yok — Lucide): types +~17 · api +3 fetcher + queryKey ·
    2 route + 2 client:
    - `/security-monitor/revenue` ana dashboard (segment toggle + KPI kartları +
      ödeme takvimi bucket + plan dağılımı + trial tablo + plan hareketi +
      tıklanabilir drill paneli)
    - `/security-monitor/revenue/invoices` (status sayım chip + fatura tablosu)
  - Sidebar: "Ticari Pano" grubuna "Genel Bakış" girişi eklendi
  - Verify: tsc ✅ · eslint ✅ · build ✅ (2 yeni route)
- **D6 Güvenlik Kamarası G1 tam regresyon: 320/320 yeşil** (admin 199 + parent
  37 + institution 55 + tenant 29)

- **D6 Güvenlik Kamarası G2a — Genel Bakış + Sistem + Bildirim + Bütünlük**:
  - KURAL 1: 5 endpoint (`/security-monitor` overview + `/integrity` + `/system`
    + `/system/{id}/resolve` + `/notifications`) + 6 servis (`security_monitor`
    580, `error_capture` 358, `notification_health` 370, `data_integrity` 362,
    `attention_engine` 671 public API, `impersonation.list_active`) + 4 template
    **sonuna kadar okundu**; Files-Read Receipt + veri yapısı raporu + parite
    tablosu üretildi.
  - **Mimari karar**: 6 servis HİÇ değişmedi — `get_security_dashboard_data` /
    `get_integrity_panel_data` / `get_system_health_data` / `get_health_data` /
    `get_attention_summary` / `list_active` AYNEN çağrıldı, dönen dict/dataclass
    Pydantic'e serialize edildi. resolve_error audit `AuditAction.USER_UPDATE`
    (Jinja birebir). G2b (Aktivite) `tenant_activity` 3159 satır + template 1616
    olduğu için ayrı oturuma bölündü (kullanıcı onayı 2026-05-20).
  - Backend: `schemas/admin.py` +~30 model (Security/Integrity/System/Notif) ·
    `api_v2/admin.py` +5 endpoint + `_attention_item_to_model` helper. Matris
    serialize: channel_matrix `channels`→`rows`, kind_matrix `kinds`→`rows`.
  - `scripts/test_api_v2_admin_security_overview.py` — **14/14 yeşil** (role guard
    + overview/integrity/system/notifications shape + resolve happy/idempotent/404)
  - Frontend (emoji yok — Lucide): `types/admin.ts` +~30 tip · `api/admin.ts`
    +4 fetcher + 4 queryKey (`admin:security:*`) · `use-admin-mutations.ts`
    +useResolveSystemError (invalidate `admin:security:system`+`overview`) ·
    `security-ui.tsx` (severity/level statik ton map + LevelBadge/SeverityBadge
    + humanizeAgo/fmtDateTime/successPctColor) · `notif-trend-bar-chart.tsx`
    (Recharts stacked bar 4 seri)
  - 4 route + 4 client:
    - `/security-monitor` (overview): Dikkat Odası kartları (attention, severity
      Lucide ikon — emoji map'lenmez) + 8 KPI + rol dağılımı + aktif
      impersonation tablo (kritik kırmızı) + aktif oturum + şüpheli IP + kritik
      audit akışı + süper admin giriş; 30s auto-refresh
    - `/security-monitor/integrity`: migration kartı (ok/pending/error tonu) +
      DB dosya boyut (500MB/1GB eşik) + orphan tarama + KVKK SLA (30g) tablo +
      cron drift tablo
    - `/security-monitor/system`: 3 özet + açık hata grupları (genişleyebilir
      stack trace + "Çözüldü" dialog note textarea) + endpoint hata oranı +
      yavaş istek tabloları
    - `/security-monitor/notifications`: 24h/7g özet kart (başarı% renk) + en
      eski kuyruk uyarısı + 7g stacked trend (Recharts) + kanal/tür matrisi
      (total>0 satır + failed kırmızı) + engellenme nedenleri + son hatalar
  - Sidebar: "Güvenlik Kamarası" grubuna 3 item aktive (Veri Bütünlüğü / Sistem
    Sağlığı / Bildirim Sağlığı) + Genel Bakış zaten aktifti; live/sessions/
    alarms/abuse/activity hâlâ disabled (G2b/G3/G4)
  - Verify: tsc ✅ · eslint ✅ · build ✅ (4 yeni route)
- **D6 Güvenlik Kamarası G2a tam regresyon: 334/334 yeşil** (admin 213 + parent
  37 + institution 55 + tenant 29)

- **D6 Güvenlik Kamarası G2b — Aktivite Kamerası**:
  - KURAL 1: 3 endpoint (`/activity` panel + `/activity/active-users` drill +
    `/activity/heatmap` drill) + `tenant_activity` (3159 satır, ~50 fonksiyon)
    + 3 template (security_monitor_activity 1616, _activity_drill_users 58,
    _activity_drill_heatmap 92) **sonuna kadar okundu**; Files-Read Receipt +
    dev veri yapısı raporu + parite tablosu üretildi.
  - **Mimari karar**: `tenant_activity` HİÇ değişmedi — 3 endpoint
    `get_activity_panel_data_with_summary` / `active_users_window` /
    `institution_hour_day_heatmap` AYNEN çağırır, dönen dev dict'ler Pydantic'e
    serialize. Owner-pattern + segment (all/institution/solo) mutlak korundu.
    Heatmap int-key matrix → str-key (`_str_matrix`, JSON uyumu). D6'nın en
    büyük tek servisi.
  - Backend: `schemas/admin.py` +~45 model (ActivityPanelResponse + alt modeller
    + 2 drill response). `api_v2/admin.py` +3 endpoint + `_str_matrix` /
    `_retention_metric` helper.
  - `scripts/test_api_v2_admin_security_activity.py` — **15/15 yeşil** (3 segment
    + solo_special varlığı + heatmap 24×7 str-key + 2 drill + 6 role guard)
  - Frontend (emoji yok — Lucide): `types/admin.ts` +~45 tip · `api/admin.ts`
    +3 fetcher + 3 queryKey · `security-ui.tsx`'e band_color statik ton map
    (toneDot/toneBadge/toneText — purge-safe) · `activity-charts.tsx`
    (HeatmapGrid CSS + WowBarChart/DauTrendChart Recharts + StickinessSparkline +
    SessionBandsBar)
  - 1 route + client (6 sekme client-state, segment URL-state):
    - `/security-monitor/activity` — kritik özet 6 kart (sekmeye atlar) + segment
      toggle (Hepsi/Kurumlar/Bağımsız) + 6 sekme: **Bugün** (DAU/WAU/MAU
      tıklanabilir drill + yapışkanlık + rol kırılımı + solo özel panel + WoW
      grafik) · **Risk** (kalp atışı 6-bant + öneri popup + heatmap drill + plan×
      aktivite 4-quadrant + sönüş hızı + sessizleşenler) · **Tutunma** (yapışkanlık
      + sparkline + 1h/30g + geri dönenler + onboarding milestone tablosu) ·
      **Derinlik** (oturum süresi bantları + öğretmen/öğrenci oranı + power users
      + özellik popülerlik/matris — emoji→Lucide ikon) · **Zaman** (saat×gün ısı
      haritası + 14g DAU trend + en aktif kurumlar + kurum heatmap drill) ·
      **Karşılaştırma** (plan benchmark + champion kartları)
    - Drill'ler on-demand `useQuery` (açılır panel + kapat); owner-pattern
      detay linkleri 360 sayfalarına
  - Sidebar: "Güvenlik Kamarası → Aktivite" item aktive (live/sessions/alarms/
    abuse hâlâ disabled — G3/G4)
  - Verify: tsc ✅ · eslint ✅ · build ✅ (1 yeni route)
- **D6 Güvenlik Kamarası G2b tam regresyon: 349/349 yeşil** (admin 228 + parent
  37 + institution 55 + tenant 29)

- **D6 Güvenlik Kamarası G3 — Oturumlar + Canlı + IP + Impersonation**:
  - KURAL 1: 7 endpoint (`/live` + `/live/feed` + `/sessions` + `/sessions/{token}/
    revoke` + `/ips/block` + `/ips/unblock` + `/impersonations/{id}/end`) +
    `alarm_engine.live_event_stream` (352-394) + `impersonation.end_session` +
    `security_monitor.terminate_session`/`revoke_session_by_token`/`block_ip_manual`/
    `unblock_ip` + 3 template (security_monitor_live 70, _live_feed 31,
    security_monitor_sessions 321) **sonuna kadar okundu**; Files-Read Receipt +
    veri akışı raporu + parite tablosu üretildi.
  - **Kritik bulgu**: `sessions` sayfası `get_security_dashboard_data` +
    `list_active` kullanır = **G2a `SecurityOverviewResponse`'un alt kümesi**.
    Yeni GET endpoint açılmadı; frontend sessions sayfası mevcut overview
    fetcher'ını yeniden kullanır.
  - **Mimari karar**: security_monitor + impersonation + alarm_engine servisleri
    HİÇ değişmedi — aynen çağrıldı. Mutasyonlar
    `invalidate=["admin:security:overview","admin:security:sessions"]` ile
    sessions görünümünü tazeler.
  - Backend: `schemas/admin.py` +5 model (LiveFeedItem/Response + IpBlock/Unblock
    Body + SecurityActionResult). `api_v2/admin.py` +5 endpoint (1 GET live/feed
    `ge=10/le=86400` clamp + 4 POST mutation; revoke/block/unblock USER_UPDATE,
    imp-end IMPERSONATE_REVOKED audit — Jinja birebir).
  - `scripts/test_api_v2_admin_security_sessions.py` — **17/17 yeşil** (live/feed
    + 4 mutation × happy/404/403 + clamp + ORM doğrulama)
  - Frontend (emoji yok — Lucide): types +3 · api +1 fetcher + 2 queryKey
    (`securitySessions`/`securityLiveFeed`) · `use-admin-mutations.ts` +generic
    `useSecurityAction` + 4 hook (useRevokeSession/useBlockIp/useUnblockIp/
    **useRevokeImpersonation** — mevcut P3 `useEndImpersonation` ile çakışmamak
    için yeni ad) + 4 error code label
  - 2 route + 2 client:
    - `/security-monitor/sessions` — overview verisini kullanır: aktif sahte
      oturumlar (sonlandır confirm) + 4 KPI + aktif oturum tablosu (rol badge +
      kapat confirm) + 24s fail bucket (bloka al) + şüpheli/blokli IP tablosu
      (serbest/bloka al + manuel blok formu hours 1-720) + süper admin giriş akışı;
      tek paylaşılan confirm Dialog
    - `/security-monitor/live` — poll feed (`refetchInterval` seçili aralık;
      pencere 5dk/10dk/30dk/1saat + yenileme 2/5/15sn/durdur seçici) + canlı
      nabız göstergesi + audit/alarm satırları (severity Lucide ikon + renk)
  - Sidebar: "Oturumlar" + "Canlı Akış" aktive (alarms/abuse hâlâ disabled — G4)
  - Verify: tsc ✅ · eslint ✅ · build ✅ (2 yeni route)
- **D6 Güvenlik Kamarası G3 tam regresyon: 366/366 yeşil** (admin 245 + parent
  37 + institution 55 + tenant 29)

- **D6 Güvenlik Kamarası G4 — Alarmlar + Suistimal**:
  - KURAL 1: 8 endpoint (alarms list/scan/ack/rule-update + abuse list/scan/
    resolve/remediate) + `alarm_engine` (406 — evaluate_all/list_rules/
    list_recent_events/acknowledge/update_rule) + `abuse_detection` (run_all/
    list_signals/resolve_signal/open_signal_count) + `abuse_remediation`
    (auto_remediate_signal + RemediationResult + ACTION_BUTTON_LABELS_TR) +
    2 template (security_monitor_alarms 186, security_monitor_abuse 199) +
    5 model label dict **sonuna kadar okundu**.
  - **Mimari karar**: alarm_engine + abuse_detection + abuse_remediation
    servisleri HİÇ değişmedi — aynen çağrıldı. Alarm kuralı eşik/cooldown/
    enabled/channels güncelleme + abuse remediate (kind'a göre toplu aksiyon:
    mass_invitation→davet iptal, mass_notification→bildirim bastır,
    multi_account→oturum kapat; başarıda otomatik resolve) mantığı korundu.
    Mutasyonlar `invalidate=["admin:security:alarms"|"abuse","overview"]`.
    Abuse label/severity/açıklama TR dict'leri response `meta` olarak gönderilir
    (jargon yasağı — sade Türkçe).
  - Backend: `schemas/admin.py` +12 model. `api_v2/admin.py` +8 endpoint
    (audit: scan/ack/update USER_UPDATE, remediate ABUSE_REMEDIATION — Jinja
    birebir; remediate başarısız → 400 remediation_failed).
  - `scripts/test_api_v2_admin_security_alarms_abuse.py` — **21/21 yeşil**
    (8 endpoint × happy/404/403 + rule update + remediate happy/already_resolved
    + meta 5 dict + ORM doğrulama)
  - Frontend (emoji yok — Lucide): types +12 · api +2 fetcher + 2 queryKey ·
    `use-admin-mutations.ts` generic `useSecurityAction<TBody,TResult>` + 6 hook
    (AlarmScan/AlarmAck/AlarmUpdateRule/AbuseScan/AbuseResolve/AbuseRemediate)
    + 4 error code label
  - 2 route + 2 client:
    - `/security-monitor/alarms` — unack sayısı + "Şimdi tara" + kural tablosu
      (satır-içi düzenleme: eşik/cooldown/kanal/aktif → dirty-aware Kaydet) +
      son 72s tetiklenen alarmlar (severity renk + "Gördüm" ack)
    - `/security-monitor/abuse` — açık sinyal sayısı + "Şimdi tara" + filtre
      (tür dropdown + sadece açıklar, URL state) + 4 tür açıklama kartı + sinyal
      tablosu (aktör/kurum 360 linki + ⚡toplu aksiyon confirm dialog + çöz
      not dialog)
  - Sidebar: "Alarmlar" + "Suistimal" aktive — **Güvenlik Kamarası grubu
    tamamen aktif (6/6 item)**
  - Verify: tsc ✅ · eslint ✅ · build ✅ (2 yeni route)
- **D6 Güvenlik Kamarası G4 tam regresyon: 387/387 yeşil** (admin 266 + parent
  37 + institution 55 + tenant 29)

## D6 Caddy yönlendirmesi (2026-05-20) — TAMAM

- `deploy/Caddyfile`: "Dalga 5: Süper admin — KAPALI" bloğu **açıldı** →
  `reverse_proxy /admin next:3000` + `reverse_proxy /admin/* next:3000`
  (yorum metni "Dalga 6 — AÇIK 2026-05-20" olarak güncellendi). `/api/v2/admin/*`
  zaten yukarıdaki `/api/v2/*` matcher'ından FastAPI'ye (BFF backend) gidiyor.
- **Kullanıcı onayı alındı (2026-05-20)**; Jinja `/admin/*` silinmedi, "asılı
  bırakılanlar"a eklendi.
- Otomatik regresyon: 21 suite **387/387 yeşil** (Caddy değişikliği kodu
  etkilemez — doğrulama amaçlı çalıştırıldı).
- **Kullanıcının yapması gerekenler (canlı ortam)**:
  1. `docker compose exec proxy caddy reload --config /etc/caddy/Caddyfile`
     (<60 sn rollback — R-020; geri almak için iki `reverse_proxy /admin*`
     satırını tekrar yorum yap + reload)
  2. Manuel smoke: super admin login → 7 sidebar grubu (Panel + Kuruluşlar +
     Denetim + Limitler & Kullanım + Vitrin + Ticari Pano + Güvenlik Kamarası)
     tek tek açılıp doğrulanır.

## Dalga 7 — Auth / Güvenlik (full paket, fazlı) — 2026-05-20

**Kapsam kararı (kullanıcı 2026-05-20):** full güvenlik paketi · 2FA yalnız
Süper Admin + Kurum Yöneticisi · fazlara bölünmüş, her faz kullanıcı onayıyla.
5 fazlı yol haritası:
- **P1 — Çekirdek parite + BFF güvenlik birleştirme** ✅ (2026-05-20)
- **P2 — Şifre sıfırlama (forgot password)** ✅ (2026-05-20, migration `o6p8s1t2s00m`)
- **P3 — Signup (teacher + invite) + email doğrulama** ✅ (2026-05-20, migration `p7q9t2u3t11n`)
- **P4 — 2FA/TOTP** (Süper Admin + Kurum Yöneticisi) ✅ (2026-05-20, migration `q8r0u3v4u22o`)
- **P5 — Oturum yönetimi + public teklif + Caddy/kapanış** ✅ (2026-05-20, migration YOK)

Migration'lı fazlar (P2/P3/P4) başlatılmadan önce migration kullanıcıya ayrıca
gösterilir (riskli-sprint kuralı).

**Mevcut güvenlik altyapısı envanteri** (zaten olgun, KURAL 1 ile okundu):
bcrypt · JWT access+refresh `pwd_stamp` rotation · HttpOnly+Secure+SameSite+
`__Host-` cookie · rol-bazlı lockout (3/30·5/15·5/10) · rol-bazlı şifre politikası
(14/12/10/8 + özel karakter) · ~150 yaygın şifre kara listesi · HaveIBeenPwned
breach check · Cloudflare Turnstile · IP brute-force blok (SuspiciousIp) ·
sliding-window rate limit · audit · ActiveSession heartbeat · süper admin login
alarmı · email enumeration koruması · auto-resume · self-signup + invite + trial.

- **D7 Paket 1 — Çekirdek parite + BFF güvenlik birleştirme**:
  - KURAL 1: tüm auth mimarisi okundu (api_v2/auth 330 + auth_security 223 +
    rate_limit/security/jwt_auth 264 + Jinja auth/signup/password/offers 891 +
    turnstile/password_breach/security_monitor_alerts 276 + 6 template).
  - **Kritik bulgu**: BFF login (api_v2), Jinja login'in 6 güvenlik katmanını
    kaçırıyordu (IP blok / CAPTCHA / SuspiciousIp besleme / **ActiveSession** /
    auto-resume / süper admin alarmı). ActiveSession eksikliği → G2a/G3 "Aktif
    Oturumlar + Canlı Akış" panelleri Next.js kullanıcılarını **göstermiyordu**.
  - **Mimari karar**: BFF stateless JWT olduğu için ActiveSession takibi JWT'ye
    opsiyonel `sid` claim eklenerek yapıldı — `jwt_auth.py` mobile (api_v1) ile
    PAYLAŞILDIĞINDAN `sid` None ise payload birebir aynı (geriye uyum; api_v1
    47/47 korundu). Her authenticated cookie isteğinde
    `dependencies._resolve_from_cookie` heartbeat atar; uzaktan revoke edilince
    401 `session_terminated`.
  - Backend:
    - `jwt_auth.py`: `_make_token`/`issue_*`/`issue_token_pair`'a `sid` (opsiyonel)
      + `TokenPayload.session_id` + decode `data.get("sid")`
    - `dependencies.py`: `_resolve_from_cookie` heartbeat + `_resolve_user_v2`
      helper + **`get_current_user_v2_allow_pwchange`** (must_change 403'ü atmaz)
    - `me.py`: `/me/password-change` artık `allow_pwchange` dep kullanır →
      **must_change kullanıcı kilitlenmesi giderildi** (kritik bug fix)
    - `api_v2/auth.py` login: IP blok (429 ip_blocked) + Turnstile CAPTCHA
      (LoginIn.turnstile_token; 401 captcha_failed) + record_failed_login_ip +
      record_session_start (sid) + maybe_auto_resume + süper admin alarmı;
      refresh sid taşır + heartbeat; logout terminate_session; yeni
      `GET /api/v2/auth/turnstile` (enabled + site_key, public)
  - `scripts/test_api_v2_auth_p1.py` — **10/10 yeşil**; mevcut
    `test_api_v2_auth.py` 14/14 + `test_api_v1.py` 47/47 korundu
  - **Test izolasyon notu**: `record_failed_login_ip` TestClient IP'sini
    ("testclient") brute-force eşiğiyle bloklayabilir → auth testlerinin
    cleanup'ına `SuspiciousIp.ip=="testclient"` temizliği eklendi (yoksa sonraki
    paketler 429 alır).
  - Frontend (emoji yok — Lucide): `app/login` güçlendirildi (role landing
    `_home_for` paritesi: admin/institution/teacher/parent/student + Turnstile
    widget `next/script` explicit render + `ip_blocked`/`captcha_failed` hata
    kodları + must_change → `/password/change`); yeni `app/password/change`
    (server auth-durum çözer: 403 password_change_required → zorunlu mod / 200 →
    normal / 401 → login) + form (breach/policy/lockout hata kodları)
  - Caddy: `/login` + `/password/change` → next:3000 AÇIK; `/logout` Jinja'da
    (Next.js çıkışı BFF ile); `/password/*`+`/signup/*`+`/offers/*` P2-P5'te
  - Verify: tsc ✅ · eslint ✅ · build ✅ (/login + /password/change)
- **D7 P1 tam regresyon: 25 suite GREEN** (api_v1 47 + auth 14 + auth_p1 10 +
  me + admin tüm + parent + institution + tenant)

- **D7 Paket 2 — Şifre sıfırlama (forgot password)**:
  - **Migration `o6p8s1t2s00m`** (down_revision n5o7r0s1r99l): `password_reset_tokens`
    tablosu. **Additive** — yalnız yeni tablo, mevcut veriyi ETKİLEMEZ, downgrade'li.
    `alembic upgrade head` uygulandı.
  - Model `app/models/password_reset.py` — `PasswordResetToken` (token unique 64 +
    user_id CASCADE + expires_at + consumed_at + requested_ip; `is_usable` property;
    TTL 60 dk). models/__init__ export.
  - Servis `app/services/password_reset.py` — `request_reset` (kullanıcı varsa
    token üret + eski kullanılmamışları iptal + e-posta gönder; yoksa sessizce None),
    `get_usable_token`, `consume_reset` (şifre değiştir + tüket + kilit/sayaç
    sıfırla → pwd_stamp değişir, eski tüm oturumlar revoke).
  - Endpoint'ler (`api_v2/auth.py`):
    - `POST /auth/forgot-password` — **enumeration koruması** (her zaman generic
      200) + rate limit + CAPTCHA (aktifse). E-posta `email_service` (disabled →
      log-only dev).
    - `POST /auth/reset-password` — token validate (400 invalid_token) + mismatch
      (422) + politika (422 password_weak) + eski-ile-aynı (422 password_same) +
      **HaveIBeenPwned breach** (422 password_breached) + tek-kullanım + audit.
  - Email template `emails/password_reset.html` (Subject + reset_url + 60 dk notu).
  - `scripts/test_api_v2_auth_p2.py` — **11/11 yeşil**.
  - Frontend (emoji yok — Lucide): `/password/forgot` (e-posta + Turnstile +
    generic başarı ekranı) + `/password/reset/[token]` (yeni şifre + confirm +
    hata kodları + ölü-token ekranı → yeni bağlantı iste). Login sayfasına
    "Şifremi unuttum" linki; "yöneticinizle iletişime geçin" metni kaldırıldı.
  - Caddy: `/password/change` spesifik → `/password/*` generic AÇIK (change +
    forgot + reset). Verify: tsc ✅ · eslint ✅ · build ✅.
- **D7 P2 tam regresyon: 16 suite GREEN** (api_v1 47 + auth 14 + auth_p1 10 +
  auth_p2 11 + me + admin çekirdek + parent + institution + tenant)

- **D7 Paket 3 — Signup (teacher + invite) + email doğrulama (soft)**:
  - **Migration `p7q9t2u3t11n`** (down_revision o6p8s1t2s00m): `users.email_verified_at`
    (nullable) + DATA (mevcut tüm kullanıcılar geriye dönük doğrulanmış) +
    `email_verification_tokens` tablosu. **Additive**, downgrade'li. Uygulandı.
  - **Soft doğrulama kararı (kullanıcı 2026-05-20)**: kayıt+giriş serbest, panelde
    banner ile teşvik; doğrulamadan da kullanılabilir. SMTP gecikse kimse
    kilitlenmez.
  - Model `email_verification.py` (EmailVerificationToken, 7g TTL, tek kullanım) +
    `User.email_verified_at` + `UserPublic.email_verified` (login/me yanıtında).
  - Servis `email_verification.py` — `issue_and_send` (token + mail, eski iptal),
    `verify` (email_verified_at doldur + tüket).
  - Endpoint'ler (`api_v2/auth.py`): `POST /auth/signup/teacher` (self-signup +
    14g trial + CAPTCHA + auto-login + doğrulama maili) · `GET /auth/signup/invite/{token}`
    (davet bilgisi public) · `POST /auth/signup/invite/{token}` (kuota + atomik
    consume + auto-login) · `POST /auth/verify-email/{token}` · `POST /auth/resend-verification`.
    Ortak `_establish_bff_session` helper (ActiveSession sid + cookie — login ile aynı).
    Email template `emails/email_verify.html`.
  - `scripts/test_api_v2_auth_p3.py` — **13/13 yeşil**.
  - Frontend (emoji yok — Lucide): `/signup/teacher` (full_name/email/şifre×2/
    şartlar + Turnstile) + `/signup/invite/[token]` (server invite-info + 4 durum
    ekranı + form pre-fill) + `/verify-email/[token]` (otomatik doğrulama:
    verifying/success/error). **NOT**: soft doğrulama banner'ı (resend butonu)
    P5'te `/me/account`'a eklenecek (resend endpoint hazır).
  - Caddy: `/signup/*` + `/verify-email/*` AÇIK. Verify: tsc ✅ · eslint ✅ · build ✅.
- **D7 P3 tam regresyon: 15 suite GREEN** (api_v1 47 + auth p1/p2/p3 + me + admin
  çekirdek + parent + institution + tenant)

- **D7 Paket 4 — İki faktörlü doğrulama (2FA/TOTP)**:
  - **Migration `q8r0u3v4u22o`** (down_revision p7q9t2u3t11n): `users.totp_secret` +
    `users.totp_enabled_at` (nullable) + `totp_backup_codes` tablosu. **Additive**,
    downgrade'li. Uygulandı.
  - **Kapsam (kullanıcı kararı)**: yalnız Süper Admin + Kurum Yöneticisi
    etkinleştirebilir (opsiyonel — kullanıcı kendi açar). `pyotp` kütüphanesi
    (requirements.txt) + frontend `qrcode.react`.
  - Model: `User.totp_secret`/`totp_enabled_at` + `two_factor_enabled` property +
    `TotpBackupCode` (bcrypt hash, tek kullanım).
  - Servis `totp.py`: setup (secret + provisioning_uri + 10 yedek kod) / enable
    (TOTP doğrula → aktif) / disable / verify_login (TOTP veya yedek kod ±1 pencere)
    / can_use_2fa (rol kısıtı) / remaining_backup_codes.
  - Endpoint'ler:
    - Login akışı: şifre doğru + 2FA aktif → cookie KURMA, `LoginOut(two_factor_required,
      challenge)` (5 dk imzalı `type=2fa` JWT). Ortak `_complete_login` helper
      (login 2FA'sız + 2fa/verify paylaşır).
    - `POST /auth/2fa/verify` (challenge + kod → register_failed_login brute force
      koruması + _complete_login + cookie)
    - `/me/2fa/status` · `/me/2fa/setup` (403 rol) · `/me/2fa/enable` · `/me/2fa/disable`
  - `scripts/test_api_v2_auth_p4.py` — **14/14 yeşil**. api_v1 47/47 + auth 14/14 +
    auth_p1 10/10 korundu (login akışı refactor regresyon-temiz).
  - Frontend (emoji yok — Lucide): login'e 2FA 2. adım (`TwoFactorStep` — kod/yedek
    kod + vazgeç) + `/me/account` `TwoFactorCard` (yalnız yönetici rolünde görünür:
    QR `qrcode.react` + secret + 10 yedek kod + enable/disable kod doğrulama).
  - Caddy: yeni path yok (`/login` + `/me` zaten açık). Verify: tsc ✅ · eslint ✅ · build ✅.
- **D7 P4 tam regresyon: 16 suite GREEN** (api_v1 47 + auth p1/p2/p3/p4 + me +
  admin çekirdek + parent + institution + tenant)

- **D7 Paket 5 — Oturum yönetimi + public teklif + kapanış** (migration YOK):
  - Backend: `me.py`'ye `GET /me/sessions` (kullanıcının son 24s aktif oturumları;
    access cookie sid → is_current işareti) + `POST /me/sessions/{token}/revoke`
    (sahiplik kontrolü — yalnız kendi oturumu; başkasının token'ı 404;
    terminate_session reason=self_revoke). Yeni `api_v2/offers_public.py` router
    (public, login'siz): `GET /offers/{token}` + `/accept` + `/decline` — P7c
    `offers` servisi AYNEN çağrıldı (get_offer_by_token/accept_offer/decline_offer/
    describe_offer). `api_v2/__init__` include. `me.py`'ye `Request` importu
    eklendi (sessions için).
  - `scripts/test_api_v2_auth_p5.py` — **12/12 yeşil**.
  - Frontend (emoji yok — Lucide): `/me/account`'a `SessionsCard` (cihaz/IP/son
    aktivite + "Bu cihaz" rozeti + uzaktan kapat) + `EmailVerifyBanner` (soft
    doğrulama uyarısı + resend, P3'ten ertelenen). Yeni `/offers/[token]` public
    sayfa (server view + `OfferActions` accept/decline + reason).
  - Caddy: `/offers/*` AÇIK. `/logout` Jinja'da kaldı (Next.js çıkışı BFF ile).
  - Verify: tsc ✅ · eslint ✅ · build ✅.
- **D7 P5 tam regresyon: 19 suite GREEN** (api_v1 47 + auth p1/p2/p3/p4/p5 + me +
  admin tüm + parent + institution + tenant)

## Kurum Yöneticisi — Program Uyum Panosu (2026-05-20)

**Bağlam:** Kullanıcı, kurum yöneticisi kimliğiyle paneli değerlendirdi. Tespit:
mevcut panel güçlü bir "gözlem kulesi" (aktivite/risk/tükenmişlik/kohort) ama
**çekirdek değeri (program → uyum → çıktı) yönetici görünürlüğü zayıf**. Öneri
kataloğundan **Program Uyum Panosu** seçildi (doğruluk % + boş-program dahil).

- **Kritik altyapı bulgusu (KURAL 1)**: Tamamlama verisi soru-adedi düzeyinde
  (`TaskBookItem.planned_count`/`completed_count`) **+ doğru/yanlış** (`correct_count`/
  `wrong_count`) zaten mevcut → "uydu mu" + "doğru mu yaptı" birlikte ölçülebilir.
  **Migration GEREKMEDİ.** Veri yapısı `tenant_health._compute_weekly_completion_rate`
  deseniyle birebir (Task + TaskBookItem + User.teacher_id); ek olarak `is_draft=False`
  (yayınlanmış program) filtresi.
- Servis `institution_compliance.py` — kurum özeti (rate + WoW delta + doğruluk +
  planlanan/yapılan soru) + haftalık trend (N hafta) + öğretmen kırılımı (rate +
  doğruluk + boş-öğrenci) + öğrenci dikkat listesi (en düşük 25) + boş-program
  (koç başına + örnek isim). Renk eşikleri D4 (≥70 emerald/≥40 amber/<40 rose).
  Gizlilik: öğrenci detay sayfası YOK (at-risk/burnout deseni).
- Endpoint `GET /api/v2/institution/compliance?weeks=8` (`_require_institution_admin`).
  `scripts/test_api_v2_institution_compliance.py` — **10/10 yeşil**.
- Frontend (emoji yok — Lucide): `/institution/compliance` route + `ComplianceClient`
  (4 KPI kartı + Recharts haftalık trend + öğretmen kırılım tablosu + öğrenci
  dikkat listesi + boş-program bölümü). Sidebar "Analiz → Program Uyumu" item
  (ClipboardCheck) en üste.
- Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon 10 suite GREEN.

**Kurum Yöneticisi Vizyon Paketleri (sırayla, kullanıcı 2026-05-20):**
KP1 Müdahale Merkezi ✅ · KP2 Öğretmen Etkililik Karnesi ✅ · KP3 Veli Güveni
Görünürlüğü ✅ · KP4 Akademik Çıktı/Deneme Takibi ✅ (KP4a öğretmen giriş ✅ ·
KP4b kurum panosu ✅) — **tüm KP vizyon paketleri tamamlandı**.

- **KP1 — Müdahale Merkezi** ✅ (2026-05-20, migration YOK):
  - `institution_action_center.py` — mevcut sinyalleri (compliance boş-program +
    düşük-uyum + `risk_analysis.bulk_risk_assessment`) tek önceliklendirilmiş
    aksiyon kartı listesinde toplar (attention_engine'in kurum-içi versiyonu).
    Eşik: boş 3+ kritik, uyum <40 uyarı / <25 kritik, risk high+critical.
  - `GET /api/v2/institution/action-center` · `test_api_v2_institution_action_center.py` 8/8 yeşil.
  - Frontend: `/institution/action-center` (3 özet + severity-renkli aksiyon
    kartları + kategori ikonu + öneri) · sidebar "Müdahale Merkezi" (Siren) en üste.
  - Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon 8 suite GREEN.

- **KP2 — Öğretmen Etkililik Karnesi** ✅ (2026-05-20, migration YOK):
  - `institution_teacher_scorecard.py` — son N hafta birleşik etkililik skoru
    (0-100): %40 tamamlama + %25 doğruluk + %20 program disiplini (öğrenci başına
    haftalık planlanan soru / 50 hedef) + %15 düşük-risk. `institution_compliance`
    helper'larını (`_student_totals_for_week`/`_week_bounds`/`_rate`/`_accuracy`)
    + `risk_analysis.bulk_risk_assessment` reuse. burnout'un (kim yoruldu)
    çıktı-odaklı tamamlayıcısı (kim sonuç alıyor). Rozet: ≥75 Örnek/≥50 İyi/
    ≥30 Gelişmeli/<30 Dikkat.
  - `GET /api/v2/institution/teacher-scorecard?weeks=4` · `test_api_v2_institution_scorecard.py` 7/7 yeşil.
  - Frontend: `/institution/teacher-scorecard` (ortalama skor + en etkili koç +
    karne tablosu: skor bar/rozet + tamamlama/doğruluk/disiplin/risk) · sidebar
    "Analiz → Öğretmen Karnesi" (GraduationCap, Tükenmişlik'ten sonra).
  - Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon 7 suite GREEN.

- **KP3 — Veli Güveni Görünürlüğü** ✅ (2026-05-20, migration YOK):
  - `institution_parent_trust.py` — kurum aktif öğrencileri üzerinden: veli
    kapsaması (ParentStudentLink), aktif veli (parent last_login son N gün),
    bekleyen davet (ParentInvitation consumed=null + süre>now), bildirim
    teslimatı (NotificationLog student_id kurum filtreli → sent/failed/suppressed
    + kanal kırılımı). notification_health'in kurum-filtreli versiyonu.
  - `GET /api/v2/institution/parent-trust?days=30` · `test_api_v2_institution_parent_trust.py` 9/9 yeşil.
  - Frontend: `/institution/parent-trust` (4 KPI: kapsama/aktif veli/bekleyen
    davet/bildirim başarısı + kanal teslim tablosu + düşük-kapsama uyarısı) ·
    sidebar "Analiz → Veli Güveni" (HeartHandshake, Haftalık Özet'ten sonra).
  - Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon 8 suite GREEN.

- **KP4a — Akademik Çıktı / Deneme Takibi: ÖĞRETMEN GİRİŞ** ✅ (2026-05-20,
  **migration `r9s1v4w5v33p`**):
  - **Yeni özellik** (Jinja'da deneme sonucu modeli YOKTU — KURAL 1 parite için
    değil, mevcut öğretmen mimarisini anlamak için keşif yapıldı). Kullanıcı
    kararı: deneme sonucunu **öğretmen (koç)** girer · KP4'ü **KP4a (giriş) →
    KP4b (kurum panosu)** sırasına böl.
  - **Migration `r9s1v4w5v33p`** (down_revision q8r0u3v4u22o): `exam_results`
    tablosu. **Additive** — yalnız yeni tablo, mevcut veriyi ETKİLEMEZ,
    downgrade'li. `alembic upgrade head` uygulandı.
  - Model `app/models/exam_result.py` — `ExamResult` (student_id CASCADE +
    created_by_id SET NULL + title + exam_date + section[ExamSection enum] +
    total_correct/wrong/blank + net + subject_nets JSON-Text + note). Net hesabı
    `compute_net(correct, wrong, section)` = D − Y/ceza (LGS ceza=3, YKS=4, taban
    0). `section_penalty` helper. models/__init__ export.
  - Backend: `schemas/teacher.py` +8 model (ExamCreate/Result/Subject/Summary/
    SectionOption + StudentExamListResponse). `api_v2/teacher.py` +3 endpoint
    (`GET /students/{id}/exams` özet+liste · `POST /students/{id}/exams` net
    auto-hesap, ders kırılımı verilirse toplam türetilir · `DELETE /exams/{id}`)
    + `_get_owned_exam`/`_build_exam_row`/`_exam_section_options` helper'ları.
    Sahiplik 404 (cross-tenant/başka öğretmen sızdırmaz). invalidate
    `teacher:{id}:students:{sid}:exams`.
  - `scripts/test_api_v2_teacher_exams.py` — **16/16 yeşil**.
  - Frontend (emoji yok — Lucide): `lib/types/teacher.ts` +8 tip · `lib/api/teacher.ts`
    `studentExams` queryKey + `getTeacherStudentExams` fetcher · `use-teacher-mutations.ts`
    +useCreateExam/useDeleteExam · `student-exams-panel.tsx` (özet 4 KPI + net trend
    Recharts LineChart + deneme kartları: net/D-Y-B/section ton rozeti + açılır ders
    kırılımı tablosu + sil · ekleme dialog: Toplam/Ders-kırılımı mod seçici + canlı
    net önizleme + section sabit ton map purge-safe). Öğrenci detay sekmelerine
    "Denemeler" eklendi (Genel/Analitik/**Denemeler**/Kitaplar/Veliler).
  - Verify: tsc ✅ · eslint ✅ · build ✅ (`/teacher/students/[id]` derlendi).
  - **Regresyon notu**: 23-suite batch'te 3 suite (teacher_students/weekly_plan/
    parent_trust) Dalga 7 auth sertleştirmesinin `testclient` IP brute-force
    kontaminasyonu nedeniyle düştü; **üçü de tek başına yeşil** (14/14·14/14·9/9).
    KP4a regresyonu DEĞİL — büyük sıralı test koşusunda suite arası `SuspiciousIp`
    temizliği gerekir (exam smoke kendi cleanup'ında yapıyor).

- **KP4b — Akademik Çıktı / Deneme Takibi: KURUM PANOSU** ✅ (2026-05-20,
  migration YOK — veri KP4a `ExamResult`'tan gelir):
  - `institution_academic.py` — kurum aktif öğrencileri × ExamResult agregasyonu.
    **Net karşılaştırılabilirliği**: ham net sınava göre değişir (LGS ~90 soru,
    TYT 120) → kurum geneli/trend/koç karşılaştırması için **net başarı oranı**
    (`_net_pct` = net ÷ soru sayısı, %) kullanılır; section kırılımında ham ort
    net de gösterilir. Üretilen bloklar: özet (kapsama + ort net başarı + toplam/
    son30g deneme + trend deltası), sınav türü kırılımı (ham net + net başarı %),
    haftalık trend (net başarı %), öğretmen kırılımı (en yüksek üstte + son deneme
    tarihi), en çok gelişen/gerileyen öğrenci (≥2 deneme, ilk→son delta), deneme
    girmeyen (koç kırılımlı kapsama eksiği). Renk eşikleri D4 (≥70 emerald/≥40
    amber/<40 rose). Gizlilik: öğrenci adı görünür, detay sayfası YOK.
  - `GET /api/v2/institution/academic?weeks=8` · `_require_institution_admin` +
    `_get_institution_or_403` + `_institution_brief`. `schemas/institution.py`
    +7 model (AcademicSummary/Section/Trend/Teacher/Mover/NoExam + Response).
  - `scripts/test_api_v2_institution_academic.py` — **13/13 yeşil**.
  - Frontend (emoji yok — Lucide): `lib/types/institution.ts` +7 tip · `lib/api/institution.ts`
    `academic` queryKey + `getInstitutionAcademic` fetcher · `/institution/academic`
    route + `academic-client.tsx` (sade-dil "net başarı oranı" bilgi notu + 4 KPI
    + Recharts haftalık trend LineChart [connectNulls, 0-100 domain] + sınav türü
    tablosu + koç tablosu + gelişen/gerileyen 2 sütun + deneme girmeyen amber
    uyarı bölümü; PCT_TEXT sabit ton map purge-safe). Sidebar "Analiz → Akademik
    Çıktı" (LineChart ikon, Program Uyumu'ndan sonra).
  - Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon (suite arası SuspiciousIp
    temizlikli) GREEN.

## Güvenlik düzeltmesi — kimlik formları `method="post"` (2026-05-20)

- **Sorun (kullanıcı bildirdi)**: Login formu JS hydrate olmadan submit edilince
  (dev'de ilk derleme yavaş / hydration yarışı) tarayıcı **native GET** yapıp
  `?email=...&password=...` ile şifreyi URL'ye koyuyordu (tarayıcı geçmişi /
  sunucu logu / referrer sızıntısı).
- **Kök neden**: react-hook-form `onSubmit` handler'ı hydration tamamlanmadan
  bağlanmıyor; form'da `method` yoktu → default GET.
- **Düzeltme**: TÜM kimlik/şifre formlarına `method="post"` eklendi (login +
  2FA + signup teacher/invite + password change/forgot/reset). Hydrate olunca
  `handleSubmit` preventDefault yapar (fetch ile çalışır); olmazsa native POST
  gövdede taşır — şifre **asla URL'ye düşmez**. **KURAL**: yeni kimlik formları
  daima `method="post"` ile yazılır.

## Anasayfa (vitrin) Next.js'e taşındı (2026-05-20)

- **Bağlam**: Kök `/` son Jinja içerikli sayfaydı (giriş yapmamışa pazarlama
  vitrini + feature_catalog A/B kartları). Kullanıcı "Next.js'te yeni tanıtım
  sayfası" + "UI'da son derece yaratıcı ol, sayfa mimarisini koru, görseli
  Next.js tasarım araçlarına bırak" dedi. KURAL 1: landing/index.html (1378) +
  _feature_card + 5 mockup + feature_catalog A/B servisi + telemetri sonuna
  kadar okundu, receipt + parite tablosu + plan onaylandı.
- **Mimari karar**: feature_catalog (A/B + strateji) + telemetry servisleri
  DOKUNULMADI — yeni public router AYNEN çağırır. Kartlar + variant + telemetri
  client tarafında (`/api/v2/landing`) yüklenir; anon session cookie (fc_sid)
  same-origin taşınır (Caddy prod / dev rewrite). FEATURE parity tam, VISUAL
  parity yok (emoji→Lucide, indigo/violet/fuchsia fresh palet).
- Backend: `api_v2/landing_public.py` (offers_public deseni, auth'suz) —
  `GET /api/v2/landing` (kartlar + variant_slug + ensure_session_id cookie) +
  `POST /api/v2/landing/telemetry` (record_event, KVKK hash, 204). __init__'e
  kayıt. `scripts/test_api_v2_landing_public.py` — **8/8 yeşil**.
- Frontend: `lib/types/landing.ts` + `lib/api/landing.ts` (fetcher + sendBeacon
  telemetri) + `components/landing/reveal.tsx` (Reveal + CountUp, IO-based) +
  `mockups.tsx` (5 mockup_type → React component map) + `landing-client.tsx`
  (10 bölüm: header/hero+DNA mock/trust marquee/dinamik feature kartları/stats
  CountUp/kurumlar B2B heatmap/nasıl çalışır 5 adım/paketler billing toggle/
  final CTA/footer; telemetri impression+view+demo_click). `app/page.tsx`
  Dalga 0 önizlemeyi DEĞİŞTİRDİ — server'da rol redirect (Jinja index() paritesi)
  + anonimde LandingClient.
- Caddy: `@root path /` → next:3000 (yalnız tam kök; /demos /kvkk /privacy Jinja
  fallback'te). next.config'e `/demos` rewrite (dev'de demo linki çalışsın).
  Jinja landing/index.html + /api/telemetry/event dead-code olarak kalır.
- **Kapsam dışı**: `/demos` video sayfası Jinja'da (kartların "Demo İzle" linki
  oraya gider, çalışır). İstenirse ayrı pakette taşınır.
- Verify: tsc ✅ · eslint ✅ · build ✅ (`/` dinamik) · regresyon 7 suite GREEN
  (landing 8/8 + feature_catalog + auth + institution + admin + parent + tenant).
- **Tasarım iterasyonları (2026-05-21, kullanıcı geri bildirimi)**:
  - **Marka paleti**: logodan (petrol labirent + altın figür) çıkarıldı →
    Tailwind `cyan` (petrol, #0e7490≈marka) + `amber` (altın) + sıcak nötrler.
    Eski indigo/violet markadan kopuktu. Gerçek logo `web/public/etutkoc-logo.png`
    (next/Image) header/footer/final-CTA + login'de kullanıldı; hepsi `/`'a tıklanır.
  - **Login logosu**: tıklanabilir (logout → /login → logo → anasayfa). KURAL:
    kimlik/landing sayfalarında logo daima `/`'a Link.
  - **Kaldırıldı**: "önde gelen koçlar" logo şeridi + sahte istatistik bandı
    (placeholder veriler).
  - **Özellikler = Bento grid** (kullanıcı seçimi): hero 2×2 (gradient+büyük
    mockup) + 3 dar + 1 geniş; fayda-odaklı başlık. İçerik DİNAMİK kalır
    (feature_catalog + A/B), telemetri korunur — sadece sunum düzeni.
  - **FOIC fix (kritik)**: `Reveal` IntersectionObserver+opacity-0 yerine saf
    CSS animasyonu (`.lp-reveal` globals.css) — içerik dinlenmede DAİMA görünür;
    hydrate gecikince hero kaybolmaz. KURAL: landing'de içerik gizleyen
    JS-bağımlı reveal yasak.
  - **force-light**: landing + login `.force-light` ile her zaman açık tema
    (koyu sistemde sabit cyan/beyaz + koyu token karışımı bozuluyordu).
  - **Zemin/kart ayrışması**: `--background` belirgin serin-gri (L91→L88) + `.lp-card`
    gerçek elevation gölgesi + `border-slate-200`. Soluk cyan-50 zeminler kaldırıldı.
  - **Logo → şeffaf SVG**: `etutkoc-logo.png` (krem kutulu) → vtracer ile **2 renk
    şeffaf SVG**. Amblem (`etutkoc-mark.svg`) metinden ayrıldı (tam kilit küçük
    boyutta okunmuyordu); paylaşılan **`components/brand-logo.tsx`** = amblem +
    "etütkoç·rotam" metni. Tüm shell'ler (site-header/teacher/institution/admin/
    parent) + auth sayfaları + landing bunu kullanır.
  - **KRİTİK proxy düzeltmesi**: `proxy.ts` (Next 16 middleware) statik dosyaları
    da auth'a sokup `/login`'e 307 redirect ediyordu → logo/görseller kırık. Artık
    statik uzantılar (svg/png/woff…) auth'suz geçer. **KURAL**: proxy statik
    varlıkları redirect etmemeli.

## Bağımsız Koç — Koçluk İşletme Modülü (2026-05-21)

**Bağlam:** Bağımsız koç = `TEACHER` + `institution_id` NULL = sistemin stratejik
bileşeni. Akademik araçları zengin ama **kendi işletmesi** için operasyonel/ticari
katman yoktu. Kullanıcıyla sorun fırtınası + ihtiyaç analizi → 4 paketlik yol
haritası (her biri ayrı migration + smoke + onay):
- **KS1 — Seans kaydı çekirdeği** ✅ (aşağıda)
- **KS2 — Tahsilat**: öğrenci başına ücret (genelde seans başı 2000-3000, aylık
  elden) + yapılan seans otomatik sayım + ödeme kaydı + "ayı kapat" + gelir panosu.
- **KS3 — Zahmetsiz yakalama** (2 alt-paket): **KS3a fotoğraf→metin** ✅ ·
  **KS3b ses→metin** ✅ (aşağıda). Kâğıt form fotoğrafı / sesli dikte → AI taslak
  doldur (3-tık ilkesi). Çok-modlu AI + KVKK rıza + medya saklanmaz.
- **KS4 — AI koçluk içgörüsü** ✅ (aşağıda): birikmiş seanslardan bir sonraki
  seans için özet + gündem + psikolog-vari ipuçları (sistem içinde, Claude).
- **İlke (kullanıcı):** teknoloji koçun zamanını çalmasın; veri girmek + sonuca
  ulaşmak en fazla 3 tık. Notlar yalnız koça özel (KVKK).

- **KS1 — Seans kaydı çekirdeği** ✅ (2026-05-21, **migration `s0t2w5x6w44q`**):
  - **Migration `s0t2w5x6w44q`** (down_revision r9s1v4w5v33p): `coaching_sessions`
    tablosu. **Additive**, downgrade'li, uygulandı.
  - Model `coaching_session.py` — `CoachingSession` (coach SET NULL + student CASCADE
    + session_date + **status** [done/postponed/cancelled/no_show] + duration/channel
    + agenda [zorunlu] + next_change + coach_note + mood 1-5 + tags JSON + **auto_snapshot
    JSON** [Kova 1, seans anında saklanır] + capture_source). 3 enum + label dict'leri.
  - **Senin "Haftalık Program Değerlendirme Formu" → 3 kova**: Kova 1 otomatik
    (study_dna/analytics/exam_result'tan: tamamlama %, hız, geride kalan ders, son
    net) → `auto_snapshot`; Kova 2 anlatı → coach_note (KS3'te ses/foto); Kova 3
    koç kararı → agenda (zorunlu) + next_change. Koç ~3 tık.
  - Backend: `schemas/teacher.py` +9 model · `api_v2/teacher.py` +6 endpoint
    (GET sessions [özet+timeline] · GET sessions/prefill [otomatik panel] · POST
    create [snapshot saklar] · GET/POST/DELETE detay) + helper'lar. Sahiplik 404.
  - `scripts/test_api_v2_teacher_sessions.py` — **14/14 yeşil**.
  - Frontend (emoji yok — Lucide): types +12 · api `studentSessions`/`sessionPrefill`
    + 2 fetcher · `use-teacher-mutations.ts` +useCreateSession/Update/Delete ·
    `student-sessions-panel.tsx` (özet 4 KPI + zaman çizelgesi + otomatik-panelli
    form: durum/kanal/süre/gündem[zorunlu]/not/değiştirilecek/ruh hali 1-5/etiketler)
    + öğrenci detayına **"Seanslar" sekmesi** (Genel/Analitik/Denemeler/**Seanslar**/
    Kitaplar/Veliler) + yazdırılabilir boş form (`(print)/teacher/students/[id]/
    sessions/print`, A4, senin form başlıkların).
  - Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon (suite arası SuspiciousIp
    temizlikli) GREEN.

- **KS2 — Tahsilat (koç ↔ öğrenci)** ✅ (2026-05-21, **migration `t1u3x6y7x55r`**):
  - **Migration `t1u3x6y7x55r`** (down_revision s0t2w5x6w44q): `coach_student_rates`
    + `coach_payments`. **Additive**, downgrade'li, uygulandı.
  - Modeller `coach_billing.py` — `CoachStudentRate` (öğrenci başı seans ücreti,
    unique student_id, upsert) + `CoachPayment` (tutar/tarih/yöntem [cash/transfer/
    other]/period_month "YYYY-MM"/not). **Koç↔öğrenci** ilişkisi — platform↔koç
    `Invoice` (Owner-pattern admin) ile KARIŞTIRMA.
  - **Aylık hesap modelde DEĞİL — hesaplanır**: o ay status=DONE seans × ücret −
    o aya işlenen ödemeler = kalan. Ertelenen/iptal sayılmaz. "Ayı kapat" = kalan
    tutarı period_month'la ödeme girmek.
  - Backend: `schemas/teacher.py` +9 model · `api_v2/teacher.py` +6 endpoint
    (GET billing?month [aylık pano: öğrenci satırları + totals] · POST students/{id}/
    rate [upsert] · GET/POST students/{id}/payments · DELETE payments/{id}) +
    `_month_bounds`/`_payment_row`/`_get_owned_payment` helper. Sahiplik 404.
  - `scripts/test_api_v2_teacher_billing.py` — **15/15 yeşil**.
  - Frontend (emoji yok — Lucide): types +9 · api `billing`/`studentPayments`
    queryKey + 2 fetcher · `use-teacher-mutations.ts` +useSetRate/CreatePayment/
    DeletePayment · `/teacher/billing` sayfa + `billing-client.tsx` (ay seçici
    prev/next + 3 KPI [tahakkuk/tahsil/kalan] + tablo [öğrenci·seans·ücret·tahakkuk·
    ödenen·kalan·durum·işlem] + Ücret belirle dialog + Ödeme gir / **Ayı kapat**
    dialog [kalan ön-dolu]) + teacher-shell "Tahsilat" nav (Wallet).
  - Verify: tsc ✅ · eslint ✅ · build ✅ (`/teacher/billing`) · regresyon **12/12
    suite GREEN** (billing 15/15 + sessions + teacher + institution + admin +
    parent + auth + tenant).

- **KS3a — Fotoğraftan yakalama (foto→metin, AI taslak)** ✅ (2026-05-21,
  **migration `u2v4y7z8y66s`**):
  - **Migration `u2v4y7z8y66s`** (down_revision t1u3x6y7x55r): `users.ai_capture_consent_at`
    (nullable). **Additive**, downgrade'li, uygulandı. **Maliyet/KVKK planı kullanıcıya
    sunuldu + onaylandı** (foto-önce, ses KS3b'ye; rıza akışı uygun).
  - **KVKK kararı (kullanıcı 2026-05-21)**: el yazısı/not fotoğrafı yurt dışı alt-işleyene
    (Anthropic Claude) gönderildiğinden **açık rıza zorunlu** (`ai_capture_consent_at`).
    **Medya SAKLANMAZ** — bellekte işlenir, metne çevrilir, atılır. Yalnız koç görür.
  - **Kredi**: yeni `UsageKind.AI_SESSION_CAPTURE` (5 kredi). `usage_events.kind` plain
    VARCHAR (CHECK yok) → **migration gerekmedi**. `KIND_CREDITS` map'e eklendi.
    Bağımsız koç Owner-pattern: `consume_credits(owner=CreditOwner.for_user(coach))`.
  - Servis `ai_session_capture.py` — `parse_session_photo(image_base64, media_type)`
    → Claude **vision** (httpx, `ai_book_template` deseni: ANTHROPIC_API_URL +
    claude-haiku-4-5 + x-api-key) çok-modlu mesaj (image block + prompt) →
    `{agenda, coach_note, next_change, mood, tags}`. `AIInvalidResponse`/
    `AIServiceUnavailable` reuse. ALLOWED_MEDIA = jpeg/png/webp. Görsel kaydedilmez.
  - Backend: `schemas/teacher.py` +AiConsentResponse/ParsePhotoBody/SessionDraftResponse ·
    `api_v2/teacher.py` +GET/POST `/ai-consent` + POST `students/{id}/sessions/parse-photo`
    (consent yok→403 consent_required · boş→422 image_required · tür→422
    invalid_media_type · >7MB→422 image_too_large · CreditBlocked→402
    ai_credit_exhausted · AIInvalidResponse→422 photo_unreadable · AIServiceUnavailable→
    502 ai_unavailable). `_apply_session_body` capture_source set eder.
  - `scripts/test_api_v2_teacher_ai_capture.py` — **10/10 yeşil** (parse_session_photo
    monkeypatch — gerçek Claude çağrısı yok).
  - Frontend (emoji yok — Lucide): types +AiConsentResponse/SessionDraftResponse +
    CoachingSessionCreateBody.capture_source · api `aiConsent` key + getTeacherAiConsent ·
    `use-teacher-mutations.ts` +useSetAiConsent/useParseSessionPhoto (kod-bazlı toast;
    parse yan etkisiz → invalidate susturuldu) · `student-sessions-panel.tsx`'e
    **"Fotoğraftan doldur"** butonu (gizli file input, `capture=environment` mobil
    kamera) + **rıza modalı** (ShieldCheck: AI işleme + yurt dışı + saklanmaz +
    yalnız-koç açıklaması; onay→useSetAiConsent→parse) + parse sonucu **taslak →
    SessionForm prefill** (violet "AI okudu, kontrol edin" banner; kaydette
    capture_source=photo). İlk denemede rıza yoksa modal, sonra otomatik parse.
  - Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon GREEN (ai_capture 10/10 +
    exams 16 + sessions 14 + billing 15 + teacher_read 12 + teacher_students 14 +
    tenant 29).

- **KS3b — Sesten yakalama (ses→metin, AI taslak)** ✅ (2026-05-21,
  **migration GEREKMEDİ**):
  - **Migration YOK**: rıza (`ai_capture_consent_at`, KS3a) + `capture_source`
    ("voice" değeri) + `usage_events.kind` plain VARCHAR (CHECK yok) zaten mevcut.
  - **KVKK**: ses kaydı da yurt dışı alt-işleyene gönderildiğinden KS3a rızası
    AYNEN kapsar (rıza metni "Anthropic, OpenAI" olarak genişletildi). **Ses
    SAKLANMAZ** — bellekte işlenir, metne çevrilir, atılır. Yalnız koç görür.
  - **Kredi**: yeni `UsageKind.AI_SESSION_VOICE` (**8 kredi** — Whisper STT +
    Claude yapılandırma = 2 çağrı, foto'nun 5 kredisinden pahalı; maliyet
    şeffaflığı). `KIND_CREDITS` + `USAGE_KIND_LABELS_TR` ("AI Seans Yakalama
    (Ses)") güncellendi; foto label'ı "(Foto)" oldu. AI_SESSION_CAPTURE yorumu
    "vision — foto (KS3a)" olarak netleştirildi.
  - Servis `ai_session_capture.py` (KS3a dosyasına eklendi):
    - `_claude_messages(content)` — Anthropic messages çağrısı tek helper'a
      refactor (foto vision + metin yapılandırma paylaşır).
    - `transcribe_audio(audio_base64, media_type)` → **OpenAI Whisper**
      (`whisper-1`, httpx multipart `files=` + `language=tr`, `OPENAI_API_KEY`
      env). ALLOWED_AUDIO = webm/mp4/ogg/mpeg/wav. Ses kaydedilmez.
    - `_structure_text_to_draft(transcript)` → Claude metin (`_TEXT_PROMPT`) →
      `{agenda, coach_note, next_change, mood, tags}`; boş yapılanırsa ham döküm
      coach_note'a fallback (veri kaybetme).
    - `parse_session_voice(audio, mt)` = transcribe → structure.
  - Backend: `schemas/teacher.py` +ParseVoiceBody · `api_v2/teacher.py`
    +POST `students/{id}/sessions/parse-voice` (consent yok→403 consent_required ·
    boş→422 audio_required · tür→422 invalid_media_type · >18MB→422 audio_too_large ·
    CreditBlocked→402 ai_credit_exhausted · AIInvalidResponse→422 voice_unreadable ·
    AIServiceUnavailable→502 ai_unavailable). consume_credits AI_SESSION_VOICE.
  - `scripts/test_api_v2_teacher_voice_capture.py` — **10/10 yeşil**
    (parse_session_voice monkeypatch — gerçek Whisper/Claude çağrısı yok).
  - Frontend (emoji yok — Lucide): `use-teacher-mutations.ts` +useParseSessionVoice
    (kod-bazlı toast; invalidate susturuldu) · `student-sessions-panel.tsx`'e
    **"Sesle doldur"** butonu (**MediaRecorder**: getUserMedia → kayıt → Durdur
    butonu + canlı süre sayacı m:ss → blob→base64; `pickAudioMime` webm/mp4/ogg
    desteklilik kontrolü) + paylaşılan rıza modalı (metin genişletildi) + parse
    sonucu **taslak → SessionForm prefill** (kaynak-bilinçli banner "AI sesinizi/
    fotoğrafı okudu"; kaydette `capture_source` foto/ses ayrı). `dispatch` ortak
    akış (foto+ses): rıza yoksa modal → onay → parse.
  - Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon GREEN (voice 10/10 +
    ai_capture 10 + sessions 14 + billing 15 + exams 16 + admin_usage 21 + tenant 29).
  - **Yeni env (prod)**: `OPENAI_API_KEY` (Whisper). Tanımsızsa parse-voice 502
    ai_unavailable döner (özellik bozulmaz, diğer akışlar etkilenmez).

- **KS4 — AI koçluk içgörüsü** ✅ (2026-05-21, **migration `v3w5z8a9z77t`** —
  cache'li; KREDİ GÜVENLİĞİ revizyonu):
  - **Amaç (kullanıcı)**: "bugün şu öğrenciyle şunu konuş" — birikmiş seans
    notları + akademik durumdan koça bir sonraki seans için hazırlık. Öneri/
    taslak; yalnız koç görür; klinik teşhis değil (koçluk dili).
  - **KREDİ GÜVENLİĞİ (kullanıcı 2026-05-21 — kritik)**: içgörü **DB'ye cache'lenir**.
    İlk sürüm her görüntülemede Claude'a gidiyordu (her seferinde kredi) → düzeltildi.
    **Migration `v3w5z8a9z77t`** (down_revision u2v4y7z8y66s): `coaching_insights`
    tablosu (öğrenci başına TEK kayıt, unique). Additive, downgrade'li, uygulandı.
    - **GET** `students/{id}/coaching-insight` → cache'den okur, **KREDİ DÜŞMEZ**
      (insight null = henüz üretilmemiş).
    - **POST** `students/{id}/coaching-insight` → üret/**yenile**, **kredi düşer**,
      cache'i upsert eder (is_stale=False).
    - Seans create/update/delete → `_mark_insight_stale` cache'i `is_stale=True`
      yapar (AI çağrısı YOK; koça "yenile" önerilir).
  - **Kredi**: `UsageKind.AI_COACHING_INSIGHT` (**6 kredi** — tek Claude çağrısı,
    geniş bağlam). `KIND_CREDITS` + label ("AI Koçluk İçgörüsü").
  - Model `coaching_session.py`'a `CoachingInsight` (student_id unique + summary +
    3 JSON liste + based_on_sessions + is_stale + generated_at/by). models/__init__
    export.
  - Servis `ai_coaching_insight.py` — `generate_coaching_insight(student_name,
    sessions, academic)` → son ≤8 seans + akademik anlık görüntü
    (`_compute_session_prefill`) → Claude → `{summary, agenda_suggestions[],
    psychological_tips[], watch_outs[]}`. `_claude_messages` + `_extract_json_object`
    `ai_session_capture`'dan reuse. "Uydurma, yalnız notlara dayan, teşhis koyma".
  - Backend: `schemas/teacher.py` +CoachingInsightResponse (+generated_at) +
    CoachingInsightCacheResponse {insight, is_stale} · `api_v2/teacher.py` GET+POST
    + `_insight_to_response`/`_mark_insight_stale` helper'ları.
  - `scripts/test_api_v2_teacher_coaching_insight.py` — **11/11 yeşil**
    (GET ücretsiz · POST kredi=1 · GET tekrar kredi=1 · yeni seans→stale · POST
    yenile kredi=2; monkeypatch).
  - Frontend (emoji yok — Lucide): types +CoachingInsightCacheResponse · api
    `coachingInsight` queryKey + getTeacherCoachingInsight · `use-teacher-mutations.ts`
    `useGenerateCoachingInsight` (POST → setQueryData ile cache güncelle) ·
    `student-sessions-panel.tsx` "İçgörü" butonu dialog açar (ücretsiz GET);
    dialog: yoksa "İçgörü oluştur (kredi)" · varsa göster + stale ise amber uyarı +
    "Yenile (kredi)" + "Bu gündemle seans aç" (`draftSource="insight"`; capture_source
    YOK — manual). Rıza akışı tüm AI özelliklerine genelleştirildi
    (`gateConsent(action)` callback; modal metni foto/ses/seans notları +
    Anthropic+OpenAI). DraftSource = photo|voice|insight.
  - Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon GREEN (insight 11/11 +
    voice 10 + ai_capture 10 + sessions 14 + tenant 29).
  - **Koçluk İşletme Modülü (KS1-KS4) tamamlandı.** Bağımsız koç artık seans
    kaydı + tahsilat + zahmetsiz yakalama (foto/ses) + AI içgörü ile tam
    operasyonel/ticari katmana sahip.

- **AI özellikleri — kredi/paket notu (kullanıcı 2026-05-21, [[project-ai-credits-packaging]])**:
  AI özellikleri (foto/ses yakalama + içgörü) ileride **yalnız ücretli pakette**
  açık olacak; **trial/free → kapalı**; paket yükseltince açılır. Tüm AI çağrıları
  kullanıcının kendi kredisinden düşer. Bu kapı (entitlement) + paket yükseltme UI'ı
  **ücretlendirme/üyelik çalışmasında** yapılacak. API anahtarları (Anthropic/OpenAI)
  **süper adminde merkezi** yönetilecek (DB, env fallback) — Süper Admin Ayarlar paketi.

## AI Altyapısı — Süper Admin Anahtar + Ücretli Kapı + Simülasyon (2026-05-21, DEVAM EDİYOR)

**Bağlam (kullanıcı 2026-05-21):** KS3/KS4 AI özellikleri pahalı (gerçek Anthropic/
OpenAI çağrısı). 3 karar: (1) API anahtarları **süper adminde merkezi** yönetilsin
(DB şifreli, env fallback); (2) AI özellikleri **yalnız ücretli pakette**, trial/free
KAPALI, paket yükseltince açılsın; (3) gerçek anahtarla **uçtan uca ölçümlü simülasyon**.
Detaylı ücretlendirme/üyelik ileride ([[project-ai-credits-packaging]] memory'si).

**Paket A — KS4 kredi cache** ✅ (yukarıda KS4 bloğu — `coaching_insights` tablosu,
GET ücretsiz / POST kredi, migration `v3w5z8a9z77t`).

**Paket B — Süper Admin Merkezi AI Ayarları** ✅ (2026-05-21, **migration `w4x6a9b0a88u`**):
- Model `system_secrets` (name unique, value_encrypted, updated_by) — additive,
  downgrade'li, uygulandı. models/__init__ export `SystemSecret`.
- Servis `system_secrets.py`: **Fernet** şifreleme (anahtar `settings.session_secret`
  SHA256 türevi); `set_secret`/`delete_secret`/`get_db_value`/`mask`/`ai_settings_status`.
- **TEK SAĞLAYICI = GEMINI'YE GEÇİLDİ (kullanıcı 2026-05-21).** Anthropic/OpenAI
  kodu kaldırıldı; tüm AI işleri `app/services/gemini.py` üzerinden (generateContent,
  `responseMimeType=application/json`). Erişimciler: `get_gemini_paid_key()` /
  `get_gemini_free_keys()` (liste) / `get_gemini_model(paid)`.
- **KVKK key yönlendirmesi (kullanıcı kararı)**: öğrenci verili işler (foto/ses/içgörü)
  → `gemini.generate(personal_data=True)` = **ÜCRETLİ key** (no-training), fallback YOK.
  Kişisel-veri-içermeyen kitap şablonu → `personal_data=False` = ücretsiz key(ler)
  sırayla, kota (429) dolunca sıradakine, en son ücretliye.
- config.py: `gemini_paid_api_key` / `gemini_free_api_keys` (virgülle çoklu) /
  `gemini_paid_model` (vars. `gemini-2.5-pro`) / `gemini_free_model` (vars. `gemini-2.5-flash`).
- **AI servisleri Gemini'ye taşındı**: `ai_session_capture` (foto vision + **ses tek
  Gemini çağrısıyla** — Whisper ELENDİ) · `ai_coaching_insight` · `ai_book_template`
  (free→paid). Anahtar yoksa AIServiceUnavailable ("süper admin → AI Ayarları").
- `AuditAction.SYSTEM_SETTING_UPDATE` (değer ASLA loglanmaz).
- Endpoint'ler: GET `/admin/settings/ai` (anahtarlar maskeli + modeller düz + source) ·
  POST `/admin/settings/ai` (set, 400 invalid_setting/empty_value) · POST
  `/admin/settings/ai/{name}/delete`. schemas: AiSettingItem/AiSettingsResponse/SetAiSettingBody.
- `scripts/test_api_v2_admin_ai_settings.py` — **11/11 yeşil** (401/403 + şifreli
  roundtrip + get_gemini_* resolve + model config + delete).
- Frontend: types AiSetting* · api `aiSettings` key + getAdminAiSettings · use-admin-mutations
  +useSetAiSetting/useDeleteAiSetting · `/admin/settings` + `admin-ai-settings-client.tsx`
  (ücretli/ücretsiz key kartı maskeli + 2 model kartı düz + KVKK uyarısı) · admin-shell
  "Sistem → AI Ayarları".
- **.env değişken adları (kullanıcı bunları girecek)**: `GEMINI_PAID_API_KEY` (ilk/ücretli),
  `GEMINI_FREE_API_KEYS` (diğerleri/ücretsiz, virgülle), opsiyonel `GEMINI_PAID_MODEL` /
  `GEMINI_FREE_MODEL`. (Veya süper admin panelden.) Pillow + cryptography mevcut.
- Verify: tsc ✅ · eslint ✅ · build ✅.

**Paket C — AI ücretli paket kapısı (entitlement) + yükseltme** ✅ (2026-05-21, migration YOK):
- `plans.py`: `effective_plan_for_user(db, user)` (institution_id varsa Institution.plan,
  yoksa user.plan) + `ai_premium_allowed(db, user)` = `is_paid_plan(effective_plan)`.
  Ücretli = solo_pro/solo_elite/etut_standart/dershane_pro/enterprise; **trial/free →
  KAPALI** (is_paid_plan price!=0).
- `api_v2/teacher.py`: `_require_ai_premium(db, user)` → parse-photo + parse-voice +
  coaching-insight **POST**'una (sahiplik'ten sonra, consent/kredi'den önce) → 403
  `plan_upgrade_required`. GET cached insight ücretsiz okuma — gate YOK.
- `AiConsentResponse`'a `ai_premium` + `plan_code` eklendi (panel kilit göstergesi).
- **Self-serve yükseltme**: GET `/teacher/plan` (mevcut plan + solo seçenekleri +
  ai_premium) + POST `/teacher/plan/upgrade` (solo_pro|solo_elite, kurumlu → 403
  managed_by_institution, change_plan UPGRADE). **NOT: ödeme entegrasyonu (Stripe) ayrı
  iş — şimdilik doğrudan plan değişimi.**
- `scripts/test_api_v2_teacher_ai_entitlement.py` — **12/12 yeşil** (free/trial→403,
  paid→geçer, upgrade→açılır, kurumlu→403, geçersiz plan→400).
- Frontend: types +TeacherPlan* · api `plan` key + getTeacherPlan · use-teacher-mutations
  +useUpgradePlan + 3 AI hook'a `plan_upgrade_required` toast'ı · `student-sessions-panel`
  AI butonları kilitli (Lock ikon + "ücretli pakette" + amber banner → /teacher/plan) ·
  yeni `/teacher/plan` sayfa + `teacher-plan-client.tsx` (mevcut plan + 3 solo kart +
  yükselt confirm) · teacher-shell "Paket" nav (Gem).
- Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon (entitlement 12 + ai_capture 10 +
  voice 10 + insight 11 + sessions 14 + api_keys 10 + admin 13 + tenant 29) GREEN.

**Paket D — Gerçek Gemini anahtarıyla simülasyon** ✅ (2026-05-21, GERÇEK çağrı doğrulandı):
- **`.env` kolaylığı**: tek `GEMINI_API_KEY`'e **virgülle** birden çok anahtar girilebilir
  → ilk = ücretli (öğrenci verisi), kalan = ücretsiz (kitap şablonu). Tek anahtar =
  hepsi ücretli. (Veya açık `GEMINI_PAID_API_KEY`/`GEMINI_FREE_API_KEYS` / süper admin.)
- **Gemini 503** (model yoğunluk) geçici → `gemini.py` kısa backoff retry (1.5s/3s).
- `scripts/simulate_ai_real.py` ile **gerçek** uçtan uca çalıştırıldı:
  - free koç (solo_free) → AI 403 (kapı), **maliyetsiz**.
  - paid koç → GERÇEK Gemini içgörü (6 kredi, kaliteli psikolog-vari çıktı) + cache GET
    ücretsiz (6→6) + sentetik formdan GERÇEK foto okuma (5 kredi). Toplam 11/50 kredi.
  - Ses: gerçek mikrofon kaydı gerektiğinden UI'dan test (Gemini tek çağrı).

**DURUM (2026-05-21):** A + B + C + D BİTTİ + **tek sağlayıcı Gemini geçişi BİTTİ**,
GERÇEK anahtarla doğrulandı. Smoke: ai_settings 11 + ai_capture 10 + voice 10 + insight 11
+ entitlement 12 + sessions 14 + admin 13 + tenant 29 + api_v1 47. tsc/eslint/build temiz.
Commit'ler: `94d9c92` (AI altyapı+Gemini+kapı) · `b2aaa43` (virgül-ayırma+503 retry) — pushed.
Migration'lar: `v3w5z8a9z77t` (coaching_insights), `w4x6a9b0a88u` (system_secrets) —
uygulandı, alembic head = `w4x6a9b0a88u`.

**UX iterasyonları (2026-05-22, kullanıcı geri bildirimi — pushed):**
- **`.env` GEMINI_API_KEY virgülle çoklu**: ilk=ücretli, kalan=ücretsiz (`_gemini_api_key_list`).
- **`.venv`'de cryptography eksikti** → AI 500; kuruldu + requirements'a eklendi.
- **Gemini 2.5 maxOutputTokens 2048→8192**: düşünme tokenı çıktıyı kesip JSON
  parse hatası veriyordu (AI ünite önerisi).
- **feature_flags cache ORM yerine düz veri**: commit sonrası detached ORM →
  DetachedInstanceError (is_enabled). Tüm is_enabled'ı etkiliyordu.
- **KS4 içgörü**: "Bu gündemle seans aç" butonu KALDIRILDI (erken "Yapıldı" seans
  yaratıyordu); içgörü yalnız okuma/hazırlık. Bayat uyarısı "N seansa dayanıyor,
  şu an M seans var" gösterir.
- **KS3b yeniden tasarım**: "Sesle doldur" üst butonu kaldırıldı → Yeni Seans
  formunda Gündem+Görüşme notu yanında **alan-bazlı 🎤 dikte** (SAF ses→metin,
  `POST /sessions/transcribe`, `UsageKind.AI_TRANSCRIBE`=3 kredi). "Fotoğraftan
  doldur" da form içine taşındı (tüm formu doldurur). Eski parse-voice (yapılandıran)
  kaldırıldı. Kredi: foto=5, dikte=3, içgörü=6.
- Commit'ler: `d954af4`/`94d9c92`/`b2aaa43`/`d373369`/`deb7345` (cryptography)/
  `3cecdd3` (feature_flags)/`3849985` (insight buton)/`0529903` (bayat banner)/
  `da91723` (token)/`dc79947` (dikte+foto form içine).

## Üyelik & Fiyatlandırma (2026-05-22, DEVAM EDİYOR)

**Onaylanan model (kullanıcı 2026-05-22):** Değer-bazlı. Solo öğrenci bandı:
ücretsiz 3 öğr · 1-5=2.000 · 6-15=4.000 · 16-30=6.000 · 30+ öğr başı +200 ₺/ay.
Kurum koç-başı (≤30 öğr/koç): Etüt 4.000/koç · Dershane 3.000/koç · Özel Okul/
Enterprise 2.500/koç + white-label; ücretsiz 2 öğretmen/20 öğrenci. Yıllık=10 ay
peşin. AI yalnız ücretli. Ödeme: **manuel aktivasyon** (Stripe/iyzico ertelendi).
Rakip kıyas: TR koçluk hizmeti 2.5-7.5K/ay; uluslararası tutor-SaaS ~$15-40/ay.

- **M1 ✅ tek kaynak** `app/services/pricing.py` (kod default + DB override) +
  public `GET /api/v2/pricing`. Hesaplayıcılar: compute_solo_monthly / 
  compute_institution_monthly / institution_tier_for_coaches. is_paid_plan_code.
  solo_pro sert öğrenci sınırı kaldırıldı (band-fiyatlı). Smoke 7/7.
- **M2 ✅ süper admin override** — `app_settings` tablosu (migration `x5y7b0c1b99v`,
  additive) + `app_settings.py` (generic JSON, kod default+DB). Süper admin
  GET/POST/reset `/admin/settings/pricing` → düzenleme her yere yansır (tek kaynak).
  UI `/admin/pricing` (Sistem nav). Koç Paket sayfası eski 299/599 kaldırıldı →
  /pricing linki (tutarlılık) + manuel aktivasyon notu. Smoke 8/8.
- **M3 ✅ public `/pricing` Next.js** — anasayfa kırık linki giderildi (proxy public
  allowlist + Caddy). Sekmeli (Koç/Kurum) + aylık/yıllık toggle, /api/v2/pricing'den.
- **M5 ✅ tek-kaynak pazarlama kopyası + anasayfa/`/pricing` birleşimi + kurumsal
  iletişim** (2026-05-22, **migration `y6z8c1d2c00w`** — contact_requests, additive):
  - **Tek kaynak kart kopyası**: `pricing.py` `_marketing_cards` → fayda-odaklı
    sade-dil 3 kart (free/solo/institution). Anasayfa + `/pricing` AYNI paylaşılan
    `PricingCards` bileşenini + `/api/v2/pricing`'i kullanır (tutarlılık). Anasayfa
    eski sabit-kodlu kartlar silindi.
  - **Solo kopyası sadeleşti** (eğitimci şıp diye anlasın): sınırsız öğrenci /
    "bugün şunu konuş" AI hazırlığı / sesle-fotoğrafla not / kopan öğrenci uyarısı /
    veli otomatik bildirim + net grafiği.
  - **Kurum kartı**: fiyat **kaldırıldı** ("Kurumunuza özel teklif") + ayrı **koyu
    slate** zemin (dikkat çeker) + CTA `/pricing?type=kurum#kurumsal`'a gider.
  - **Kurumsal iletişim akışı**: `/pricing?type=kurum` → kurum bölümüne kayar,
    fiyat yok, detaylı anlatım + **iletişim formu** + WhatsApp/telefon/e-posta
    alternatifi. Talep → `contact_requests` + satışa e-posta (`contact_request_admin.html`)
    + süper admin **İletişim Talepleri** sayfası (sayım/filtre/Yönet diyaloğu).
    Backend: model + public `POST /api/v2/contact` + admin GET/POST. Smoke
    `test_api_v2_contact.py` 11/11. İletişim ayarları `pricing.contact` (sales/
    support email + whatsapp/phone, boş→gizli) süper adminden doldurulabilir.
  - **14-gün uygulaması doğrulandı (kullanıcı sorusu)**: AI = `is_paid_plan`
    (trial/free dahil KAPALI, istek anında); öğrenci limiti `trial_expire` cron'u
    (`c1x7a0z1a00u`, günlük 00:15 UTC) ile solo_trial→solo_free düşünce sertleşir.
    Kısıt gerçek.
  - Verify: pricing 8/8 · contact 11/11 · tsc/eslint/build ✅ · admin 13/13 ·
    tenant 29/29.
- **M6 (P6) ✅ pakete duyarlı signup** (2026-05-22, frontend-only, migration YOK):
  - `/signup/teacher?plan=X` artık `/api/v2/pricing` kataloğundan okur (anasayfa
    kartıyla TUTARLI). Panel: seçilen Solo paketinin ad+tagline'ı + **"denemende
    hemen açık"** listesi (sınırsız öğrenci + tüm takip/veli/deneme — yapay zekâ
    HARİÇ) + ayrı **amber "Yapay zekâ — Solo aboneliğinde"** notu (dürüst: AI
    trial/free'de KAPALI) + "14 gün sonra Solo Ücretsiz'e (N öğrenci) düşer".
  - Eski yanıltıcı liste ("Yapay zeka plan şablonu / Veli WhatsApp" = 14 günde
    açık) kaldırıldı — AI ücretli gerçeğiyle çelişiyordu.
  - Panel hep Solo (pro) kartını gösterir (free/no-plan dahil; deneme Pro
    deneyimi verir). Kurum planıyla gelinirse `/pricing?type=kurum`'a yönlendiren
    bilgi bandı. Signup backend'i DEĞİŞMEDİ (solo trial açar; plan görüntüleme-
    amaçlı, aktivasyon manuel). Verify: tsc/eslint/build ✅.
- **P7 (firma bilgisi tamamlama) İPTAL** (kullanıcı 2026-05-22): bağımsız koça
  firma bilgisi gerekmez; kurumlar self-signup yapmaz (iletişim formundan gelir,
  süper admin panelden girilir). Yerine **Koç Trial Yaşam Döngüsü** işine geçildi.

### Koç Trial Yaşam Döngüsü (2026-05-22, DEVAM EDİYOR)

**Bağlam:** Üyelik sistemi yalnız bağımsız koçlar için. Simülasyonla
(`scripts/simulate_trial_lifecycle.py`) doğrulanan mevcut durum: signup→`solo_trial`
(14g sınırsız öğrenci, AI yok; `?plan` backend'de yok sayılıyor) → `expire_trials`
(günlük cron) `solo_free`'ye düşürür (3 sert sınır). **Öğrenciler PASİF OLMAZ** —
aktif kalır, sadece yeni eklenemez. **Trial bitiş uyarısı YOKTU** (ne banner ne
e-posta — `compute_trial_banner` yalnız ölü Jinja base.html'de).

**Onaylanan model (kullanıcı 2026-05-22):** tek "14 gün Pro deneme" (herkes alır,
AI kredi-tavanlı — *ayrı onay bekliyor*); 14 gün sonunda yükseltmezse **yumuşak
ödeme duvarı**: veri silinmez, öğrenciler görünür kalır ama limit aşıldıysa aktif
koçluk salt-okunur → koç ya yükseltir ya **kendisi 3 öğrenci tutup gerisini
arşivler** (sistem otomatik pasifleştirmez, "hangi 3" sorununu koç çözer).
**Zamanlama:** son 3 gün → banner + e-posta + offer + admin bildirimi; 14. gün →
pasiflik + ödeme duvarı.

- **Faz 1 ✅ Trial durum servisi + Next.js banner** (migration YOK):
  - `plans.solo_trial_status(db, user)` → is_solo/plan/trial_active/days_left/
    trial_critical(≤3g)/student_count/student_limit/over_limit/**paywall**/upgrade_target.
  - `GET /api/v2/teacher/trial-status` (`TrialStatusResponse`). Smoke
    `test_api_v2_teacher_trial_status.py` **6/6**.
  - `teacher-shell` üstünde `TrialBanner`: paywall (kırmızı, kapatılamaz →
    yükselt/arşivle) · son-3-gün (amber, kapatılabilir geri-sayım). Verify ✅.
- **Faz 2 ✅ proaktif uyarı** (migration YOK, yeni cron YOK):
  - `trial_notifications.py`: `send_trial_reminders` (≤3 gün koçlara "3 gün kaldı"
    e-postası + otomatik **DRAFT PLAN_UPGRADE teklifi** = süper admin CRM/360
    bildirimi; dedup = açık teklif varlığı) + `notify_trial_expired` ("deneme
    bitti" e-postası).
  - Mevcut **`trial_expire` günlük cron'una bağlandı** (cron_jobs): önce
    reminders → expire → expired e-postaları. `expire_trials` artık
    `expired_user_ids` döndürür.
  - E-posta şablonları: `trial_reminder.html` + `trial_expired.html`.
  - Smoke `test_trial_notifications.py` **4/4**; offers 19/19 + trial-status 6/6
    regresyon temiz.
- **Faz 3 ✅ yumuşak ödeme duvarı backend** (migration YOK):
  - `dependencies.assert_active_coaching(db, user)` → paywall aktifse (solo_free +
    limit aşıldı) 403 `paywall_active`. Çekirdek koçluk write'larına eklendi:
    teacher `POST /students/{id}/tasks` + `/bulk-tasks`, weekly_plan
    `publish-day` + `publish-week`. Salt-okuma + öğrenci pasifleştirme (limite
    inme) SERBEST → "arşivle akışı" mevcut `deactivate` ile çözülür.
  - Frontend: teacher mutations `paywall_active` → "Deneme bitti — paketi
    yükseltin" toast (banner Faz 1'de zaten var).
  - Smoke `test_api_v2_teacher_paywall.py` **5/5**; teacher_read 12 + weekly_plan
    14 + teacher_students 14 regresyon temiz.
- **Faz 4 ✅ AI-in-trial** (kullanıcı 2026-05-22: "50 kredi; tükenince ücretliye
  yönlendir; bitince AI iptal"; migration YOK):
  - `ai_premium_allowed` = ücretli plan **VEYA aktif solo_trial**. Deneme bitince
    (solo_free) AI gate kapanır (otomatik). `PLAN_ALLOCATIONS` solo planları
    explicit: solo_trial=50 (kredi tavanı), solo_free=50, solo_pro=500, solo_elite
    =2000 (pro/elite "yükselince daha fazla" — ücretlendirmede ayarlanabilir).
  - Akış: trial koç AI kullanır → consume_credits 50 havuzdan düşer → tükenince
    402 `ai_credit_exhausted` (frontend "yükselt" toast) → 14 gün bitince gate
    403 `plan_upgrade_required`.
  - `test_api_v2_teacher_ai_entitlement.py` **13/13** (trial→200 + tükenince→402 +
    free/expired→403 + paid→200 + upgrade); ai_capture 10 + insight 11 +
    trial-status 6 regresyon temiz.

### Abonelik Sistemi — uygulama-içi billing (2026-05-23, DEVAM EDİYOR)

**Bağlam (kullanıcı 2026-05-23):** Üye olmuş koç `/teacher/plan`'dan "Planları gör"
ile **public /pricing**'e (edinme/pazarlama sayfası, "14 gün ücretsiz dene")
gidiyordu — yanlış. Olgun SaaS ilkesi: **edinme (public /pricing) ≠ hesap yönetimi
(uygulama-içi abonelik)**. Onaylanan model: durum-bilinçli uygulama-içi abonelik +
ödeme/devam akışı + yenileme; public /pricing edinme-only kalır. Ödeme döngüsü
aylık + akademik yıl (/pricing ile tutarlı). Ödeme şimdilik MANUEL (Stripe sonra).

- **Faz 1 ✅ durum-bilinçli uygulama-içi abonelik ekranı** (migration YOK):
  - `/teacher/plan` artık **public /pricing'e yönlendirmiyor**; kendi içinde
    durum-bilinçli. `TeacherPlanResponse` +`status`(trialing/active/free/managed)
    +`student_count` +`solo_monthly_price`(öğrenci-bandı, pricing.py tek kaynak)
    +`annual_paid_months` +`sales_email`.
  - **Hata düzeltildi**: trial koça "Ücretli paketin aktif" diyordu (Faz4'te trial
    AI=açık olunca ai_premium ile karıştı) → artık trialing/active/free ayrı; AI
    rozeti "denemede açık (N gün)" / "açık" / "kapalı".
  - Frontend: Solo yükseltme kartı (aylık/akademik-yıl toggle, bant fiyatı, mevcut
    durum) + manuel-aktivasyon dialog (sales_email mailto). Verify tsc/eslint/build
    + entitlement 13/13 + trial-status 6/6.
- **Faz 2 ✅ ödeme/devam akışı** (manuel aktivasyon, migration YOK):
  - Koç: `/teacher/plan` "Öde ve devam et" → `POST /teacher/subscription-request`
    {plan, cycle} → `contact_requests`'e (source=`subscription_request`, mesajda
    plan/döngü/fiyat/koç_id) düşer; idempotent (bekleyen talep varsa tekrar
    yaratmaz). Dialog "Talebin alındı" durumu gösterir.
  - Süper admin: talep **İletişim Talepleri**'nde "Abonelik talebi (koç)" olarak
    görünür → ödeme alınınca admin user-detail'deki **Abonelik aktivasyonu**
    kartından `POST /admin/users/{id}/activate-plan` {plan} (yalnız solo koç;
    change_plan UPGRADE + audit). `AdminUserListItem`'a `plan` eklendi.
  - Smoke `test_api_v2_subscription_request.py` **11/11**; admin_users 25 +
    contact 11 + entitlement 13 regresyon temiz; tsc/eslint/build temiz.
- **Faz 3 ✅ solo abonelik durumu + yenileme** (**migration `z7a9d2e3d11x`** —
  users +subscription_status/period_end/cycle, additive nullable):
  - `activate-plan` artık `cycle` alır → ücretli planı active + period_end
    (aylık 30g / akademik yıl 365g) + cycle set eder; free → temizler. Admin
    kartına döngü seçici eklendi.
  - `/teacher/plan` aktif durumda **yenileme tarihi** gösterir.
  - `trial_notifications.process_renewals`: gün-3 yenileme hatırlatma e-postası +
    dönem sonu geçince `past_due` işaretle + "ödeme gerekli" e-postası. Mevcut
    `trial_expire` cron'una bağlandı. Şablonlar `renewal_reminder/overdue.html`.
  - **past_due → paywall**: `solo_trial_status` + `assert_active_coaching`
    past_due'yu da kapsar (koçluk write 403 paywall_active, mesaj "yenileme
    gerekli"); teacher-shell banner + /teacher/plan past_due durumu ("Aboneliğini
    yenile").
  - **İletişim Talepleri "koç sayfasına git" linki**: subscription_request'in
    mesajından `koç_id` parse edilip `linked_user_id` döner → admin tek tıkla
    koç user-detail'e gidip aktive eder.
  - Smoke `test_api_v2_subscription_renewal.py` **6/6**; subscription_request 11 +
    trial-status 6 + paywall 5 + entitlement 13 + admin_users 25 + trial_notif 4
    regresyon temiz; tsc/eslint/build temiz.
- **Bütüncül düzeltme** (2026-05-23, kullanıcı bildirdi — [[feedback-holistic-change-propagation]]):
  aktivasyonda `change_plan` `trial_ends_at`'i temizlemiyordu → koç solo_pro olsa
  bile is_trial_active True kalıp /teacher/plan + banner + AI rozeti "deneme"
  gösteriyordu. Düzeltildi: `change_plan` (USER+ücretli→trial temizle) + activate-plan
  (defensive). Admin SubscriptionCard artık durum rozeti (Aktif·yenileme/past_due/
  deneme) + "Güncelle/Yenile" butonu gösterir (`AdminUserListItem` +subscription_status/
  period_end/trial_active). renewal smoke 7/7 (trial-temizleme regresyonu dahil).
  **KURAL: bundan sonra bir alan/durum değişince etkilenen tüm yüzeyler aynı
  commit'te güncellenir.**
- **Abonelik iptal/geri-al** ✅ (2026-05-23, migration YOK): aktif abonede
  `/teacher/plan` "Aboneliği iptal et" (onaylı) → `subscription_status=canceled`
  (plan + erişim dönem sonuna kadar sürer) + "İptali geri al" (resume).
  `process_renewals` dönem sonunda canceled → **solo_free**'ye düşürür (past_due
  DEĞİL) + sub alanlarını temizler. Endpoint'ler `POST /teacher/subscription/
  cancel|resume`. Bütüncül: /teacher/plan (ActiveSubscriptionCard + StatusLine)
  + admin user-detail kartı "İptal edildi" rozeti + cron. renewal smoke **12/12**.
- **Admin dashboard kısayolları** ✅: `/admin`'de "Ticari & Ödemeler" (7) +
  "Sistem & Güvenlik" (4) kartları "YAKINDA"/disabled idi ama sayfalar mevcut →
  `disabled` kaldırıldı, tıklanır oldu. "Ödeme Takvimi" hedefi düzeltildi
  (`/admin/security-monitor/revenue/invoices`).
- **Ticari Pano (`/admin/security-monitor/revenue`) düzeltmeleri** ✅:
  - **Crash giderildi**: drill tablosu `key={institution_id}` mükerrer (owner-pattern/
    çoklu fatura) → `${institution_id}-${idx}`; 360 linki owner-aware `detail_url`.
  - **Okunabilirlik**: ödeme-takvimi bucket'larına açık metin rengi (rose/amber/
    emerald-900) — koyu temada beyaz-metin-açık-zemin görünmezliği giderildi.
  - **"7 gün içinde denemesi bitenler"** dar listeden belirgin kart-ızgarasına
    (gün-kaldı rozeti + owner-aware link) yükseltildi.
- **Teklif izleme + CRM şablon entegrasyonu** ✅ (2026-05-23, **migration `a8b1e3f4e22y`**):
  - **Teklif "açıldı" izleme**: `offers.viewed_at` (additive). Public `GET /offers/{token}`
    ilk açılışta doldurur → 360 Teklifler panelinde **"Açıldı: tarih" / "Henüz açılmadı"**
    + yanıt tarihi gösterilir (`OfferItem.viewed_at`). Admin artık "iletildi ama
    açtı mı?" sorusunu görebiliyor.
  - **Şablon → Aksiyon**: 360 "Yeni Aksiyon" formuna **"Şablondan doldur"** seçici
    (render endpoint owner placeholder'larını doldurur → kind/özet/detay otomatik aksar).
  - **Aksiyon Şablonları sayfası**: canlı **önizleme** (örnek koç verisiyle) +
    **tek-süslü `{...}` uyarısı** (yalnız `{{...}}` render edilir — kullanıcının
    `{trial_ends_at}` hatası önlenir).
  - **FIRE düzeltmesi**: past_due / limit-aşımı koçu öğrenci eklemeyi de artık
    paywall engelliyor (`_check_student_creation_quota`'ya `assert_active_coaching`).
    Önce sadece program/görev gate'liydi; öğrenci ekleme plan-kotasından geçiyordu.
  - **Kapsamlı simülasyon** `scripts/simulate_offer_action_flow.py`: teklif yaşam
    döngüsü (DRAFT kuyruk→gönder→açıldı→kabul) + 4 senaryo öğrenci-sayısı karar
    mekanizması + aksiyon merkezi sinyal yakalama. **Bulgular**: (a) öğrenciler
    asla otomatik pasifleşmez/silinmez — plan düşer, fazla öğrencide aktif koçluk
    kilitlenir, "hangi öğrenci"yi koç seçer; (b) **Aksiyon Merkezi KURUM-merkezli**
    (bağımsız koç orada görünmez; solo koç trial_reminder cron + Ticari Pano
    "denemesi bitenler"de yakalanır); (c) aksiyon = manuel görev/log, sistem
    otomatik aramaz/mesaj atmaz.
  - **Teklif kuyruk→onay→gönder sistemi VAR**: trial_reminder cron DRAFT teklif
    yaratır (kuyruk) → admin 360 Teklifler'de görür → "Gönder" → e-posta + public
    link → kullanıcı açar (viewed_at) → kabul/ret. (Eksik: admin DRAFT'ı
    göndermeden DÜZENLEYEMİYOR — iptal+yeniden oluştur gerekir.)
  - Verify: paywall 5/5 + offers 19/19 + renewal 12/12 + admin 13 + 360 18 +
    dashboard 11 + tenant 29; tsc/eslint/build temiz.
- **Kalıcı demo senaryolar + DRAFT teklif düzenleme + Aksiyon Merkezi solo desteği**
  ✅ (2026-05-23, migration YOK):
  - `seed_demo_revenue_scenarios.py`: 5 kalıcı örnek koç (A limit-aşımı / B normal /
    C past_due / D iptal / E 2 SENT teklif [1 açılmış]) — UI inceleme için (idempotent,
    `--delete`). Şifre: DemoRevenue2026!. URL: /admin/revenue/users/{id}.
  - **DRAFT teklif düzenleme**: `offers.update_offer` (yalnız DRAFT) + `POST
    /revenue/offers/{id}`; 360 OffersPanel'de DRAFT'a "Düzenle" (başlık/mesaj/not
    satır-içi → kaydet). SENT → 400 not_draft.
  - **Aksiyon Merkezi owner-aware (bağımsız koç desteği)** — kurum-merkezli boşluk
    kapatıldı: `action_center._build_solo_items` solo koç sinyalleri (deneme bitiyor /
    past_due / ücretsiz limit-aşımı) → `ActionItem` owner_type/owner_id/detail_url;
    endpoint + quick-action owner-aware (user_id ile CrmAction); frontend
    "Kurum/Bağımsız koç" rozeti + "Koç 360" linki. Doğrulandı: demo C (past_due
    skor 90) + A (limit-aşımı skor 70) artık Aksiyon Merkezi'nde görünüyor.
  - Verify: analytics 9/9 + offers 19/19 + admin 13 + tenant 29; tsc/eslint/build temiz.
- **Uyarı/risk yanlış-pozitif FIRE düzeltmesi** ✅ (2026-05-23, kullanıcı bildirdi —
  yeni öğrenci hemen "giriş yok/hareket yok/programsız" alıyordu):
  - Kök neden: `risk_analysis` (no_login_5d `last_login is None`→hemen; no_program
    `planned==0`→hemen) + `analytics.generate_warnings` (inactive_3d program/yaş
    bakmadan) hesap yaşını dikkate almıyordu.
  - **Onboarding grace**: yeni öğrenci (hesap < ~3-5 gün) inaktivite sinyali ÜRETMEZ.
    no_login: hiç giriş yapmamışta "kaç gün" = hesap yaşı (yaş<5 → işaretlenmez);
    no_program: hesap ≥3 gün; inactive_3d: program (son 3g planlı>0) + hesap ≥3g.
  - **Bütüncül test** `scripts/simulate_alert_correctness.py` **9/9**: yeni→sessiz,
    eski programsız→no_login+no_program, dün-giriş→no_program, zamanlama 2g/4g
    eşiği, eski programlı 3-gün-boş→inactive_3d, aktif→temiz. Gerçek sinyaller
    hâlâ doğru üretiliyor; yanlış-pozitif yok.
  - Regresyon: institution_p2 19 + action_center 8 + scorecard 7 + compliance 10.
- **Öğrenci detay "Durum Özeti"** ✅ (2026-05-23, migration YOK): koç öğrenci
  profilini açınca düz metin uyarı listesi yerine **bir-bakışta linkli özet**.
  - Backend: `TeacherStudentDetailResponse.warning_items` (yapısal: level/code/
    title/detail + **kanıt sayfası link'i**). Kod→sayfa eşlemesi (today/yesterday→
    /day, inactive_3d/weekly→/week, projection→/dna).
  - Frontend: `StatusSummary` (verdict bandı "Acil/Dikkat/Yolunda" + bugün/hafta/
    tutarlılık tek satır) + uyarı kartları (renk + başlık + detay + "→ link_label",
    tıkla→kanıt sayfası); MetricsStrip KPI'ları tıklanır (Bugün→/day, Hafta→/week,
    Hız/Tutarlılık→/dna). Verify: teacher_students 14/14 · tsc/eslint/build temiz.
  - NOT: teacher_students smoke'unda görülen 13/14, institution smoke'larının
    sızdırdığı 3 orphan BookSection (id-reuse) kontaminasyonuydu — temizlendi,
    kod değişikliğiyle ilgisizdi.
- **Öğrenci detay "Durum Özeti" — kontrast + başarı kartları** ✅ (2026-05-23,
  migration YOK): kart metinleri koyu temada okunmuyordu (`bg-*-50` açık zemin +
  `text-foreground` beyaza çözülüyordu — gelir panosu bucket hatasının aynısı) →
  ton-bazlı explicit renkler (`text-{rose|amber|emerald}-900/800`). Panel artık
  yalnız riski değil, `program_summary`'den türetilen **linkli pozitif sinyaller**
  de gösterir (bugünü tamamladı→/day · haftalık tempo iyi→/week · tutarlı→/dna ·
  hedef tutturuyor→/week). İki grup: "Dikkat gerektirenler" + "İyi giden".
- **AI ücretli kapı tutarlılığı (FIRE) + yükseltmede pasif öğrenci reaktivasyonu**
  ✅ (2026-05-23, migration YOK):
  - **FIRE**: Kitap-AI ünite önerisi (`library` ai-suggest) ücretli kapıyı
    ATLIYORDU (yalnız feature-flag + krediye bakıyordu) → süresi bitmiş ücretsiz
    koç kullanabiliyordu. Diğer 3 AI ucu (foto/ses/içgörü) doğru engelliyordu.
    Ücretli kapı tek kaynağa alındı (`dependencies.assert_ai_premium`); 4 AI ucu
    AYNI kapıyı kullanır. `test_simulate_paywall_archive_ai.py` 15/15.
  - **Reaktivasyon**: paket yükseltme/aktivasyonda (ücretsiz/past_due → ücretli)
    ödeme duvarında pasifleştirilen öğrenciler OTOMATİK geri açılır
    (`plans.reactivate_solo_students`). Self-serve `/teacher/plan/upgrade` +
    admin `activate-plan` (past_due aynı-plan yenileme dahil — `change_plan`
    erken-return'e rağmen). **Aktif-ücretli koçun kasıtlı arşivi KORUNUR**
    (was_paid_active gate). `simulate_upgrade_reactivation.py` 15/15 (4 koç:
    self-serve / admin / past_due / kontrol).
  - **Mesajlar**: paywall banner + toast + `/teacher/plan` → "arşivle" yerine
    "pasif duruma geçir" + "paketi yükseltince pasif öğrenciler otomatik aktif olur".
- **Abonelik iptal akışı — doğrulandı (kod değişikliği YOK)** ✅ (2026-05-23):
  `simulate_subscription_cancel_flow.py` 23/23. İptal → `status=canceled`, plan
  ücretli kalır → **dönem sonuna kadar erişim sürer** (AI açık, paywall yok,
  program serbest) → cron (`process_renewals`) dönem sonunda **solo_free**'ye
  düşürür (AI kapanır; 3'ten fazla öğrenci varsa paywall; öğrenciler OTOMATİK
  pasifleşmez — koç arşivler). Resume → erişim sürer. Aktifken AI = ücretli
  tahsisat dahilinde açık (solo_pro 500 / solo_elite 2000 kredi/dönem).
  **DİKKAT**: `process_renewals` GLOBAL çalışır → testte DAİMA gerçek `now` +
  hedef koç period_end'i geçmişe alınarak izole edilir (gelecek `now` YASAK —
  demo/gerçek koçları past_due yapar/düşürür).
- **Faz 4 ⏳ Stripe/iyzico** otomatik yenileme (kart + auto-charge) — kalan tek faz.

## Paket/Limit Revizyonu — kapaklı tier'lar + duvar (2026-05-23)

**Bağlam (kullanıcı 2026-05-23):** Süper admin paneldeki paket limitleri ile
/pricing ve gerçek sistem davranışı çakışıyordu. Tespit + kullanıcı kararları:
- **Solo**: free=3 (sert duvar, korundu). Eski "bant-fiyatlı sınırsız" → **3
  KAPAKLI paket**: Solo Başlangıç ≤10 @ 2.500₺/ay · Solo (öne çıkan) ≤25 @
  5.000₺/ay · Solo Sınırsız 25+ @ 7.500₺/ay. (kullanıcı "2.500/5.000/7.500 uygun")
- **Kurum**: koç kademe 10/50/50+ korundu; koç-başı fiyat (10×4000=40k kafa
  karıştırıcı) → **toplam-kademe**: ≤10 koç → 10.000₺/ay · ≤50 → 30.000₺/ay ·
  50+ → özel teklif (price_hidden). (kullanıcı onayı)
- **2 GERÇEK BUG bulundu+düzeltildi**: (a) kurum öğretmen-oluşturmada **duvar
  yoktu** (free 2'yi aşıp 3,4,5 ekleniyordu) → `institution_create_teacher_v2`'ye
  `check_quota_for_create(quota_key="teachers")` eklendi (422 quota_exceeded);
  (b) `quotas.PLAN_QUOTAS` + `credits.PLAN_ALLOCATIONS` anahtarları gerçek plan
  kodlarıyla eşleşmiyordu → ücretli kurumlar **free kotaya/krediye düşüyordu**
  (etut_standart/dershane_pro/enterprise eklendi).

**Backend (tek kaynak `pricing.py`):** `_DEFAULTS` solo_bands+over_cap → `solo_tiers`
[{code,label,max_students(null=∞),monthly}]; institution per_coach_monthly →
`monthly_total`(null=özel)+`price_hidden`. `solo_tier_for_students(n)` ·
`compute_solo_monthly(n)` (kapaklı) · `compute_institution_monthly(n)→int|None`.
`_marketing_cards` 5 kart (free + 3 solo + dark institution). `plans.py`
SOLO_UNLIMITED + SOLO_STUDENT_LIMITS {free:3, pro:10, elite:25, unlimited:-1};
PlanInfo solo 2500/5000/7500 + institution 10000/30000/-1 (eski 199/2999 + çift
"En Popüler" badge düzeltildi). `quotas`/`credits` gerçek-kod anahtarları.
schemas/admin `SoloTierIn`/`InstitutionTierIn`(monthly_total+price_hidden)/
`PricingConfigBody`. teacher `/plan` 4 seçenek + `recommended_plan` (öğrenci
sayısına uygun tier) + `is_recommended`/`max_students`.

**Frontend:** `lib/types/pricing.ts` SoloTier/InstitutionTier güncel · `/pricing`
**Bireysel/Kurumsal sekmeli** (PricingClient) + audience-filtreli `PricingCards`
(variant: landing özet-üçlü / solo 4-kart / institution); kapaklı fiyat "X ₺/ay"
(eski "'den" kaldırıldı) · teacher-plan-client **3-tier seçici** (recommended
ön-seçili, prop→state render deseni) · admin-pricing-client solo_tiers +
monthly_total editörü · admin user-detail activate-plan 4 solo seçenek ·
signup soloCard lookup düzeltildi (key "solo" → audience-bazlı).

**Canlı doğrulama (kullanıcı "çok önemli"):**
- `scripts/live_limit_enforcement.py` — **9/9**: solo free(3)/pro(10)/elite(25)
  limitte +1 → 422 plan_quota_exceeded · unlimited(30)→200 · kurum free(2)
  doğrudan öğretmen +1 → 422 quota_exceeded (DUVAR) · etut(10)→422 · limit-altı
  hepsi 201/200.
- `scripts/live_pricing_flow.py` — **19/19**: katalog 5-kart/3-tier yapısı +
  süper admin editör round-trip (değiştir→/pricing yansıdı→negatif 400→reset) +
  koç /plan tier önerisi (5→pro, 18→elite, 40→unlimited).
- Login limiter (10/dk per IP, sunucu içi-bellek) test sürecinden reset edilemez
  → live login() 429'da `retry_after_seconds` kadar bekleyip 1 kez yeniden dener.
- Verify: tsc ✅ · eslint ✅ · build ✅ · smoke pricing 8 + entitlement 13 +
  renewal 12 + trial_status 6 + contact 11 + paywall 5 + admin + tenant 29 GREEN.
- **Commit YOK** (kullanıcı henüz istemedi). Migration GEREKMEDİ (sadece config/
  kod). NOT: canlı tarayıcıda görsel smoke (sekme geçişi, kart görünümü) kullanıcı
  tarafında doğrulanmalı.

**Düzeltme — admin kurum planı dropdown'u + signup deneme metni** (2026-05-23,
kullanıcı bildirdi, migration YOK):
- **Admin "Yeni Kurum" + kurum detay düzenleme** plan dropdown'u eski "Free/
  Starter/Professional" sabit listesi gösteriyordu (gerçek kodlarla tutarsız,
  süper admin hangi pakete kaydettiğini bilemiyordu). Yeni paylaşılan
  `lib/institution-plans.ts` (`buildInstitutionPlanOptions` + `institutionPlanLabel`)
  → `/api/v2/pricing` kataloğundan türetir: **Kurum Tanıma (Ücretsiz) · Etüt
  Standart 2–10 koç · Dershane Pro 11–50 koç · Özel Okul/Enterprise 51+** +
  her seçenekte koç aralığı + açıklama + fiyat (özel teklif). Liste/detay
  tablolarında ham kod yerine okunur etiket (`institutionPlanLabel`). Mevcut
  kurum kataloğun dışı (legacy) plan kullanıyorsa dropdown'da korunur.
- **Signup `/signup/teacher?plan=X`** "Denemende hemen açık" listesinde "Sınırsız
  öğrenci" yazıyordu — seçilen pakete (Solo Başlangıç ≤10) aykırı. Düzeltildi:
  öğrenci sayısı listeden çıkarıldı (deneme tüm özellikleri açar, öğrenci sayısı
  PAKET bilgisi) → ayrı **"Seçtiğin paket: {ad} · {kapasite}"** rozeti (tier'in
  `max_students`'ından; sınırsız tier → "Sınırsız öğrenci"). Ayrıca yanlış AI
  notu düzeltildi: deneme AI'yı KAPSAR (50 kredi) — eski "denemede kapalı" metni
  gerçekle çelişiyordu → "yapay zekâ hazırlığı 50 kredi denemede açık" + "14 gün
  sonra yükseltmezsen free'ye düşer, AI kapanır" dürüst çerçeve.
- **NOT (kavram):** deneme (solo_trial) backend'de öğrenci sınırsız (-1) + AI açık
  (50 kredi); 14 gün sonra solo_free (3 öğrenci, AI kapalı). Signup artık paketi
  doğru yansıtır; deneme davranışı değişmedi (paket-bazlı deneme limiti istenirse
  ayrı iş). Verify: tsc/eslint/build ✅ · canlı HTML doğrulama (solo_pro→"10
  öğrenciye kadar", solo_unlimited→"Sınırsız", kurum tier'ları katalogdan) ✅.

## Öğretmen aktivite onboarding grace — "pasif" yanlış-pozitifi (2026-05-23)

**Bağlam (kullanıcı bildirdi):** `/institution/activity-heatmap`'te **yeni
oluşturulmuş** öğretmenler "pasif / hiç aktivite yok" işaretleniyordu (henüz
giriş yapmamış olanlar). Öğrenci tarafında çözülen onboarding-grace sorununun
öğretmen aktivite eşdeğeri. `teacher_activity.is_inactive = last_active is None
or ...` hesap yaşına bakmıyordu → bugün açılan koç anında "pasif" oluyordu.
- **Düzeltme** (`teacher_activity.py`, migration YOK): `ONBOARDING_GRACE_DAYS=3`
  + `TeacherHeatmap.is_new`. Yeni hesap (created_at < grace) + henüz aktivite
  yoksa **is_new=True / is_inactive=False** ("pasif" değil "yeni"). Eski hesap
  (≥grace) aktivitesiz → gerçekten pasif. `inactive_teachers` dashboard callout'u
  da aynı grace ile düzeltildi (yeni koç callout'a düşmez).
- Backend: `TeacherHeatmapRow.is_new` (schema) + endpoint mapping. Frontend:
  `activity-heatmap-client` + print-sheet → mavi **"yeni"** rozeti + "yeni hesap
  — henüz giriş yok" metni; `is_inactive` rose "pasif" yalnız gerçek pasifte.
- **Doğrulama:** birim testi (yeni→is_new, eski→is_inactive, callout ayrımı) +
  **canlı uçtan uca** (geçici kurum admin + yeni koç → endpoint is_new=True,
  inactive_count=0). institution 18/18 + p2 19/19 + alert_correctness 9/9 ·
  tsc/eslint/build temiz. **NOT:** id-reuse kirliliği (silinen test koçlarının
  LOGIN_SUCCESS audit'leri reused ID'ye miras kalır) → grace testleri test ID'leri
  için AuditLog temizler; ürün hatası DEĞİL.

## Kalemsiz (etkinlik) görev — video/özet/tekrar/diğer (2026-05-24)

**Bağlam (kullanıcı):** `/teacher/students/{id}/week` Pazar'a "Diğer" tipinde
başlık+açıklama ("Mebi Deneme 7") girip görev eklemeye çalışınca **"Görevde en az
bir kalem olmalı"** hatası. Sebep: backend `_create_task_with_items` HER görevde
≥1 kitap-kalemi (kitap+bölüm+soru) zorunlu kılıyordu. AMA frontend `add-task-form`
zaten video/özet/tekrar/**diğer** tiplerinde `items: []` gönderiyordu → bu tipler
**tamamen kırıktı** (hiç eklenemiyordu).
- **Kullanıcı kararı**: etkinlik tiplerine (video/özet/tekrar/diğer) kalemsiz
  görev izni; **"test" yine ≥1 kalem** ister (soru ataması).
- **Düzeltme (backend, migration YOK)**: `_create_task_with_items` — kalem
  zorunluluğu yalnız `ttype == TaskType.TEST` için. Etkinlik tipleri kalemsiz
  oluşturulur (reserve döngüsü boş items'ta no-op). Hata mesajı netleşti ("Test
  görevinde en az bir kalem… soru atamasız için Video/Özet/Tekrar/Diğer seç").
- **Model**: kalemsiz görev = "yap/yapma" görevi; öğrenci görev-bazında tamamlar
  (`complete_task` book_items boşsa sadece `status=COMPLETED`); planned=0 olduğu
  için "tamamlanan soru %" metriğine girmez (deneme/etkinlik için doğru olan bu).
  Frontend değişikliği GEREKMEDİ (form zaten items:[] gönderiyordu).
- **Doğrulama** `live_itemless_task.py` **5/5** (Diğer/Video kalemsiz→200, Test
  kalemsiz→422 no_items, öğrenci tamamla→COMPLETED). Regresyon: teacher_read 12 +
  weekly_plan 14 + paywall 5 + task_templates 11 + teacher_students 14 GREEN.

## Müdahale Merkezi doğrulama + crash bug fix (2026-05-24)

**Bağlam (kullanıcı):** /institution/action-center 0/0/0 gösteriyordu — "değerler
doğru mu? kritik/uyarı simüle et, değişiyor mu test et." `simulate_action_center.py`
(10 senaryo, compute_action_center'ı doğrudan çağırır; görev hacmi için kitapsız
deneme kalemi) yazıldı: boş kurum→0 · sağlıklı→0 · boş program 2→uyarı / 3→kritik ·
uyum %10→kritik / %30→uyarı · yeni öğrenci at_risk üretmez (grace) · eski+giriş
yok+düşük tamamlama+boş günler (skor ~75)→at_risk high · temizlik→tekrar 0.
- **GERÇEK BUG bulundu+düzeltildi**: `institution_action_center.py:99` `i.label`
  kullanıyordu ama RiskIndicator'da label YOK (alanlar code/title/detail/weight) →
  **kurumda high/critical at-risk öğrenci olunca Müdahale Merkezi 500 veriyordu.**
  `i.label`→`i.title`. Mevcut smoke (8/8) yakalamamıştı çünkü test verisinde high
  öğrenci yoktu; simülasyon yakaladı. **Sonuç**: kart değerleri DOĞRU + dinamik;
  kullanıcının 0/0/0'ı bu hafta gerçekten sağlıklı veri.
- **Bulgu (opsiyonel)**: compliance empty_program'da onboarding grace YOK — hafta
  ortasında eklenen yeni öğrenci hemen "boş program" sayılır (hafif yanlış-pozitif).
- Doğrulama: simulate_action_center 10/10 + action_center 8/8 + compliance 10/10 +
  scorecard 7/7 + tenant 29/29.

## Tam deneme (kitapsız, soru sayılı) görev — LGS/TYT — 2026-05-24 (migration `g4h7k9l0k88e`)

**Bağlam (kullanıcı):** Öğrenci gün içinde tam LGS/TYT denemesi çözüyor; bu tek
derse ait olmadığından "önce ders seç" akışına girmiyordu → programa eklenemiyordu.
Kullanıcı kararı: **kitapsız "Deneme" görev tipi** (ad + soru sayısı); programda
görünsün + çözülen soru hacmine saysın. Sonuç/net yine "Denemeler" sekmesinde.
- **Kısıt**: Book.subject_id + TaskBookItem.book_id/section_id NOT NULL → gerçek
  kitapsız kalem için **migration `g4h7k9l0k88e`** (down_revision f3g6j8k9j77d):
  task_book_items.book_id/book_section_id **nullable** + `label` kolonu. Additive/
  kısıt-gevşetme, mevcut satırlar dolu (etkilenmez), downgrade'li. Uygulandı.
- **Backend**: kitapsız kalem (book_id None + label + planned_count) rezerv/kapasite/
  atama ATLAR; `_create_task_with_items` + task_service complete/uncomplete/release/
  set_item_completion book_id None'da progress'i atlar (completed_count doğrudan).
  Serializer'lar (teacher+student) null-safe: book_name = label ("Deneme"). Şemalar
  book_id/section_id nullable. Hacim/tamamlanma toplamları DEĞİŞMEDİ (zaten
  planned_count topluyor) → deneme soruları otomatik sayar.
- **Düzeltme (hafta görünümü 500)**: `compute_day_subject_summary` (teacher_program.py)
  her kalemde `it.book.subject_id` yapıyordu → kitapsız denemede AttributeError →
  /teacher/students/{id}/week 500. Guard eklendi (it.book None → ders özetine girmez;
  deneme derse bağlı değil). Diğer task-item book/section erişimleri tarandı: sort
  key'leri (2450/2770) + request_service:440 zaten guard'lı; kalanlar StudentBook
  (sb.book, hep dolu) veya ölü Jinja. live_itemless_task'a hafta-fetch eklendi (10/10).
- **Frontend**: hafta add-task-form'a **"Deneme"** kutucuğu (ad + soru sayısı,
  LGS 90 / TYT 120 hızlı seç). Backend'e type="other" + kitapsız kalem gönderir
  (tasktype enum'una "deneme" EKLENMEDİ → ikinci migration yok). Gün-board form
  kapsam dışı (kullanıcı akışı hafta görünümü).
- **Doğrulama** `live_itemless_task.py` **9/9** (deneme 90 soru→200, kalem planned=90
  + label, öğrenci tamamla→completed=90). Regresyon: teacher_read 12 + weekly_plan 14 +
  students 14 + paywall 5 + task_templates 11 + exams 16 + student_read 11 +
  student_mutations 12 + tenant 29 GREEN. tsc/eslint temiz (pnpm build YOK — dev açık).

## Güvenlik Kamarası — Hata Tercümanı (sade dil + neden + ne yapmalı) — 2026-05-24

**Bağlam (kullanıcı):** Güvenlik Kamarası ham geliştirici hatalarını süper admine
olduğu gibi gösteriyordu — "2 cron 48 saattir çalışmıyor", "InvalidRequestError ...
Query.filter() being called on a Query which already has LIMIT or OFFSET applied"
gibi. Süper admin bunlardan bir şey anlamıyordu; her hata için **ne demek / neden
oldu / nasıl önlenir** bilgisini hatanın içinde görebilmeli. Onaylanan: **hibrit**
(kural kataloğu + AI yedeği) + **4 kapsam** (sistem hataları + cron/sistem sağlığı +
Dikkat Odası/alarmlar + gerçek bug). Migration YOK.
- **Gerçek bug bulgusu**: `/admin/revenue/users/{id}` "filter-after-limit" hatası
  **zaten düzeltilmiş** (`offers.py` filtreyi limit'ten önce uyguluyor); yakalanan
  21 kayıt **bayat** (eski Jinja route `admin.py:3542` + düzeltme öncesi koddan).
  Yani sorun, panonun bayat/ham hatayı korkutucu göstermesiydi → tercüman + bayat
  işareti çözer. (Stack trace `error_capture` tablosundan okunup tespit edildi.)
- **Yeni servis `error_translator.py`**: `explain_error(type, msg, endpoint)` kural
  kataloğu → `{kategori, sade özet, neden, ne yapmalı, şiddet, is_code_bug, source}`.
  Kapsam: DB (filter-after-limit kod-bug / kilit / bağlantı / IntegrityError),
  dış AI/e-posta, timeout, validation, yetki. Eşleşme yok → `source="none"`
  (frontend AI butonu). `CRON_LABELS_TR` (21 işin dostça adı + ne yaptığı) +
  `explain_cron/explain_dispatcher/explain_database_size`. **AI yedeği**
  `ai_explain_error` → `gemini.generate(personal_data=False, json_mode=True)`,
  imzaya göre BELLEKTE önbellekli (tekrar çağrıda kredi yanmaz).
- **Backend**: `/security-monitor/system` her hata grubunu `explanation` +
  `stale` (son görülme 3+ gün → muhtemelen çözülmüş) + `last_seen_label` ile
  zenginleştirir. Yeni `POST /security-monitor/system/{id}/explain` (AI, talep
  üzerine). `attention_engine` hata detektörü ham `exception_type` yerine sade
  başlık + `explain_error` tabanlı explainer + bayat notu; cron detektörü ham
  `job_key` yerine dostça ad + etkilenen görevlerin ne yaptığı.
- **Frontend**: `security-system-client` hata satırı sade açıklama (kategori +
  ne oldu/neden/ne yapmalı, şiddet renkli) + "kod düzeltmesi gerekir"/AI rozeti +
  **bayat** rozeti + "Yapay zekâ ile açıkla" butonu (source=none); ham
  exception/stack "Geliştirici detayı"na indi. `security-overview` Dikkat Odası
  kartlarına **"Bu ne demek? Ne yapmalı?"** açılır explainer (artık gösteriliyordu—
  YOKTU, eklendi).
- **Doğrulama** `test_error_translator.py` **14/14** (kural çıktıları + AI
  monkeypatch + önbellek + canlı endpoint enrich + /explain 404). Canlı: gerçek
  InvalidRequestError artık "Veritabanı · kod düzeltmesi gerekir · muhtemelen
  çözülmüş · son 6 gün önce" + sade ne oldu/neden/ne yapmalı. Regresyon: security
  overview 14 + activity 15 + sessions 17 + alarms_abuse 21 + admin + tenant 29 ·
  tsc/eslint/build temiz.

## Kurum yöneticisi plan YÜKSELTME TALEBİ (panel-içi) — 2026-05-24

**Bağlam (kullanıcı):** Bağımsız koçun `/teacher/plan`'da panel-içi "yükseltme
talebi" akışı vardı; **kurum yöneticisinde YOKTU** — kurum ancak public /pricing
iletişim formundan ya da süper admin elle değiştirerek yükselebiliyordu. Kullanıcı:
"kurum bir talepte bulunmak istesin (satın alma değil), süper admin bu talebi
görsün". Koç akışıyla **simetrik** kuruldu. Migration YOK.
- **Backend** (`institution.py`): `POST /institution/subscription-request`
  (satın alma değil — `contact_requests`'e source=subscription_request +
  mesajda `kurum_id=N` + `hedef={paket}` ile düşer; idempotent: bekleyen talep
  varsa tekrar yaratmaz). `GET /subscription` genişledi: `plan_label` +
  `available_plans` (pricing kataloğu kurum kademeleri, tek kaynak) +
  `pending_upgrade_request` + `requested_plan_label`. Helper'lar:
  `_institution_upgrade_options` / `_pending_institution_sub_request` (kurum_id
  Python'da tam-sayı eşleşme, substring çakışması yok) / `_institution_plan_label`.
- **Admin tarafı**: `_contact_item` artık `kurum_id`'yi de parse eder →
  `linked_institution_id` + etiket **"Abonelik talebi (kurum)"**. İletişim
  Talepleri dialog'una "Kurum sayfasına git (planı değiştir)" linki
  (`/admin/institutions/{id}` edit formundan plan değişir). Süper admin
  "İletişim Talepleri" badge'i (contact_new) bu talebi de sayar.
- **Frontend**: `/institution/subscription`'a en üstte **"Planını yükselt" kartı**
  (Gem ikon, "satın alma değil" vurgusu) — 3 kademe seçici (ad/koç/fiyat,
  purge-safe koyu metin) + not'lu talep dialog'u; bekleyen talep varsa amber
  "Talebin alındı" durumu (hedef paket). Tip + fetcher + `useRequestInstitutionUpgrade`.
- **Akış**: kurum yöneticisi panelden talep → süper admin İletişim Talepleri'nde
  "Abonelik talebi (kurum)" görür → kuruma gidip planı değiştirir (örn. ETUTKOC
  için yaptığımız gibi). Ödeme/aktivasyon manuel (koç akışıyla aynı).
- **Doğrulama**: `scripts/live_institution_upgrade_request.py` **11/11** (talep yok→
  gönder→bekliyor+hedef→idempotent→süper admin linki/etiket). Regresyon:
  institution 18 + p3 18 + contact 11 + subscription_request(solo) 11 + admin 13 +
  tenant 29 GREEN · tsc/eslint/build temiz.

## Kurum plan değişimi — kopuk akışın uçtan uca bağlanması (2026-05-24)

**Bağlam (kullanıcı — GÜÇLÜ süreç eleştirisi, [[feedback-holistic-change-propagation]]):**
Kurum yükseltme talebi dialog'una "Kurum sayfasına git (planı değiştir)" linki
koymuştum AMA gidilen kurum detay sayfasında plan değişimi belirgin değildi
(plan, "Kurum Bilgileri" formunun içinde gömülü bir alandı; çıpa yoktu). Kullanıcı:
"kopuk gidiyorsun, isteneni yapıp oradaki kodu değiştiriyorsun ama tıklama-yolunu
takip etmiyorsun." → memory kuralına **süreç/tıklama-yolu** boyutu eklendi.
- **Uçtan uca düzeltme (akış bir bütün):**
  - **Belirgin "Üyelik Planı" kartı** (`admin-institution-detail-client.tsx`,
    `id="plan"` çıpa + `scroll-mt-20`) — sağlık kartından hemen sonra, kademe
    seçici (free + 3 tier, "Mevcut" rozeti) + "Planı uygula". Plan, genel "Kurum
    Bilgileri" formundan ÇIKARILDI (tek net yer).
  - İletişim Talepleri dialog linki `/admin/institutions/{id}**#plan**`'a gider +
    "Planı değiştirdikten sonra talebi 'Kapatıldı' işaretle" ipucu (döngü kapanır).
  - **2 GERÇEK BUG (planSIZ edit planı sıfırlıyordu):** (a) edit endpoint
    `inst.plan = (body.plan or "free")` → plan gönderilmezse free'ye düşürüyordu;
    (b) `InstitutionEditBody.plan` Pydantic default **"free"** → alan omit edilse
    bile "free" geliyordu. İkisi de düzeltildi: schema `plan: str | None = None`
    + endpoint "yalnız açıkça gönderilince değiştir, yoksa KORU". Artık genel
    bilgi formu (ad/email/aktif) planı bozmaz.
- **Doğrulama** `live_institution_upgrade_request.py` **15/15** (talep→admin görür→
  link→planı Etüt Standart yapar→uygulandı→**planSIZ edit planı KORUR**). Regresyon:
  admin_institutions 23 + admin 13 + institution 18 + contact 11 + tenant 29 ·
  tsc/eslint/build temiz. Migration YOK.
- **Devam — talep edilen paket ÖN-SEÇİLİ gelir (kullanıcı 2026-05-24):** "kurum
  zaten paketi seçip gönderiyor, admin neden tekrar seçsin?" Akış tam bağlandı:
  istek mesajına `hedef_kod={code}` eklendi → `GET /admin/institutions/{id}`
  artık `pending_upgrade` (contact_request_id + requested_plan_code/label +
  note + tarih) döndürür (`_pending_institution_upgrade`; eski format hedef_kod
  yoksa etiket→kod pricing kataloğundan eşlenir). PlanCard talep edilen kademeyi
  **ön-seçer** + amber banner ("Bu kurum Etüt Standart için talep etti — seçili
  geldi, 'Planı uygula'ya bas") + kurumun notunu gösterir. Admin tek tık onaylar.
  `live_institution_upgrade_request.py` **19/19** (6a-6e: detayda pending_upgrade
  + kod/etiket/not + ön-seçili planı uygula). Regresyon admin_institutions 23 +
  admin 13 + contact 11 + institution 18 + tenant 29 · tsc/eslint/build temiz.
- **Devam — diğer paketleri gösterme + mevcut planı da göster (kullanıcı 2026-05-24):**
  (1) "kurum zaten seçti, neden diğer paketleri gösterip kafa karıştırıyorsun?" →
  PlanCard **context-aware**: talep belirli+farklı paket içeriyorsa ODAKLI ONAY
  modu (yalnız *Mevcut → Talep edilen* karşılaştırması + tek "yükselt" butonu;
  4'lü seçici GİZLİ; nadir override için küçük "başka plana geçir" bağlantısı).
  Talep yok / paket belirtilmemiş / admin elle yönetiyor → seçici modu. (2)
  "kurumun mevcut planını da görelim" → İletişim Talepleri dialog'unda kurum
  abonelik talebi için **Mevcut (CANLI, DB'den) → Talep edilen** rozet satırı
  (`_contact_item` artık `db` alır + `institution_current_plan_label` [linked
  institution'ın canlı planı] + `requested_plan_label` [mesajdan hedef=] döner).
  `live_institution_upgrade_request.py` **21/21** (5e-5f: canlı mevcut plan +
  talep edilen). Regresyon contact 11 + admin 13 + solo subscription 11 ·
  tsc/eslint/build temiz.
- **Devam — ücretsiz kurum planı adı her yerde "Kurum Tanıma" (kullanıcı 2026-05-24):**
  "farklı free paket isimleri görmek istemiyorum." Tutarsızlık vardı: `/institution/quota`
  ham kod `capitalize` → "Free"; `/institution/usage` `plan_code` mono+uppercase →
  "FREE"; `subscription` "Plan kodu: free"; quota karşılaştırma tablosu PLAN_QUOTAS'ın
  TÜM anahtarlarını dökerek **mükerrer "Kurum Tanıma"** (legacy `free` + `institution_free`)
  gösteriyordu. Düzeltme — tek kaynak `institutionPlanLabel`: quota header + karşılaştırma
  tablosu + usage header + usage Stat + subscription CurrentStatusCard (artık "Paket adı"
  gösterir, "Plan kodu" değil). Quota endpoint **kanonik 4 kademe** döndürür
  (institution_free/etut_standart/dershane_pro/enterprise; legacy free + trial HARİÇ) +
  mevcut planı kanonik koda normalize eder (free→institution_free) → header etiketi +
  tablo vurgusu tutarlı. Canlı: quota.plan=institution_free→"Kurum Tanıma", 4 kanonik
  (duplicate yok), subscription.plan_label="Kurum Tanıma", usage→"Kurum Tanıma".
  Regresyon institution 18 + p3 18 + admin 13 + contact 11 + tenant 29 + upgrade 21 ·
  tsc/eslint/build temiz.

## UI düzeltmeleri — /teacher/plan kontrast + heatmap renk eşiği (2026-05-23)

**Kullanıcı bildirdi, migration YOK:**
1. **`/teacher/plan` "Paketini seç" kartı koyu temada okunmuyordu** — tier
   butonları (`bg-white`/`bg-cyan-50`) + özet kutusu (`bg-slate-50`) tema
   token'ları (`text-muted-foreground`/`text-foreground`) kullanıyordu → koyu
   temada açık metin açık zeminde kayboluyordu (tekrarlayan dark-theme kontrast
   bug'ı). Düzeltme: açık-zeminli alt öğelere **explicit koyu renk** (text-slate-900/
   600/500) — purge-safe. Aylık/Yıl toggle inactive metni de `text-slate-500`.
2. **Aktivite heatmap renk eşiği yanlış kalibre** — `_compute_score` girişi
   **binary +1**, task/note ise 10+5 ile doyuyordu (max_score=16). "23 giriş +
   2 task" = 3/16 = 0.19 → level 1 (neredeyse beyaz). Çok aktif bir gün soluk
   görünüyordu. Düzeltme (`teacher_activity.py`): **erken doygunluk** —
   giriş VAR ise taban 0.25 + yoğunluk (≤5 girişte 0.15'e doğar); task 5'te /
   note 3'te doygun (0.40 / 0.20 ağırlık). Yeni: 1 giriş→level 2 (görünür),
   23 giriş+2 task→level 3 (koyu yeşil), tam aktivite→level 4, sıfır→beyaz.
   Level eşlemesi (scoreToLevel ceil(s*4)) değişmedi. Verify: tsc/eslint/build +
   institution 18/18 + p2 (heatmap) 19/19 GREEN.

## KRİTİK — Şifre değişiminden sonra oturum ölüyordu (/me/account dead-end) — 2026-05-23

**Bağlam (kullanıcı, sık yaşanan ciddi sorun):** Süper admin yeni kurum + kurum
yöneticisi oluşturuyor → yönetici ilk giriş (geçici şifre, must_change=True) →
zorunlu şifre değiştirme → değişimden sonra panele giremeyip **/me/account**
çıkmazına düşüyordu. "Yeni üye kayıt sonrası ilk login → sürekli /me/account".
- **Kök neden**: `POST /api/v2/me/password-change` şifreyi değiştirip `pwd_stamp`'i
  döndürüyordu (yeni password_hash) AMA **yeni cookie BASMIYORDU**. Tarayıcının
  elindeki access+refresh token eski pwd_stamp'li → bir sonraki istekte
  **401 token_revoked**. `(institution)/layout.tsx` /me 401/403'te /login'e,
  rol uyuşmazlığında /me/account'a yönlendiriyordu → kullanıcı çıkmaza düşüyordu.
- **Çözüm (en sağlıklı, `me.py` change_password)**: değişimden hemen sonra
  `_establish_bff_session(db, user, request, response)` (login/signup ile AYNI
  helper) → **taze access/refresh cookie (yeni pwd_stamp) + yeni ActiveSession**.
  Bu cihaz kesintisiz devam eder; diğer cihazlar pwd_stamp ile düşer (güvenlik:
  şifre değişince başka oturumlar kapanır — istenen davranış). Endpoint signature'a
  `request: Request, response: Response` eklendi.
- **Ek sağlamlaştırma**: `PasswordChangeResult.role` eklendi → frontend form
  değişim sonrası **doğrudan yanıttaki role** ile panele yönlenir (ikinci /auth/me
  çağrısı + yarış riski yok; eksikse /auth/me fallback). Tip + form güncellendi.
- **Doğrulama**: canlı (login→change→/me) **3 rol için GREEN** (institution_admin/
  teacher/super_admin; oturum sağ, doğru rol). :8081 + :3000 ikisinde de
  password-change 2 Set-Cookie basıyor. Regresyon: me 13/13 · auth 14/14 ·
  auth_p1..p5 · api_v1 47/47 · tsc/eslint/build temiz. Migration YOK.
- **KURAL**: Bir kullanıcının pwd_stamp'ini döndüren her uç (şifre değiştir/
  sıfırla) ya oturumu yeniden kurmalı (cookie re-issue) ya da kullanıcıyı login'e
  yollamalı — sessizce ölü token bırakmak yasak.

## Rol-bazlı Talep Sistemi (SupportRequest) — 2026-05-23, DEVAM EDİYOR

**Bağlam (kullanıcı 2026-05-23):** Koç↔öğrenci `TaskRequest` var ama (a) kurum
yöneticisi ↔ kuruma bağlı öğretmen, (b) süper admin ↔ (bağımsız koç + kurum
yöneticisi) arasında talep mekanizması eksikti. Yeni **genel** talep/iletişim
sistemi kuruldu (TaskRequest [programa özel] + ContactRequest [public form]
DOKUNULMADI).

**Kullanıcı kararları:** yön = yukarı yönlü oluşturma + çift yönlü thread ·
kapsam = önce backend+test, sonra frontend.

- **Backend ✅** (2026-05-23, **migration `b9c2f4g5f33z`** — additive, downgrade'li,
  uygulandı; alembic head = `b9c2f4g5f33z`):
  - 2 tablo: `support_requests` (requester_id, requester_role, audience
    [super_admin|institution_admin], institution_id, category, subject, status,
    handled_by_id/at, resolved_at, last_activity_at) + `support_request_messages`
    (thread). Model `app/models/support_request.py` (+ institution ilişkisi).
  - **Yön rolden türer** (`audience_for_requester`): bağımsız koç (TEACHER+inst
    NULL) → super_admin · kurum yöneticisi → super_admin (institution_id bağlam) ·
    kuruma bağlı öğretmen (TEACHER+inst) → institution_admin (kendi kurumu).
  - **Yaşam döngüsü**: open(Açık) → under_review(Değerlendiriliyor) →
    answered(Cevaplandı) → resolved(Çözümlendi) + withdrawn(Geri çekildi). Talep
    eden yanıt yazınca answered→under_review (yeniden). Terminal'de mesaj 400.
  - Servis `support_request_service.py` (create/list/inbox/get_for_requester/
    get_for_recipient/add_message/review/resolve/withdraw + sayımlar). **Tenant
    izolasyonu** get_for_recipient + list_inbox_institution_admin'de.
  - **TEK paylaşılan router** `api_v2/support.py` (`/support`, 8 uç) — 3 panele
    dağıtmak yerine rol-temelli: `GET/POST /requests` (talep eden) · `withdraw` ·
    `GET /inbox` (muhatap: süper admin→super_admin kuyruğu, kurum yöneticisi→kendi
    kurumu) · `review`/`resolve` (muhatap) · `GET /requests/{id}` + `reply` (ortak,
    by_recipient erişimden türer). Şema `schemas/support.py` (serileştiriciler +
    is_me/is_mine viewer'a göre).
  - `scripts/test_api_v2_support_requests.py` — **32/32** (1 süper admin + 5 kurum
    [5 yönetici + 5 öğretmen] + 5 bağımsız koç; 3 yön tam döngü + geri çekme +
    tenant izolasyonu + yetki + sayım + validasyon). Regresyon: tenant 29 + auth_p1
    10 + institution 18 temiz.
  - **Test notu**: 16 login testclient IP rate-limit'e (429) takılıyordu → login
    öncesi `get_login_limiter().reset()` (test artefaktı).
- **Frontend ✅** (2026-05-23): paylaşılan `components/support/support-center.tsx`
  (master-detail: liste + filtre chip'leri + thread + yanıt kutusu + rol-temelli
  aksiyonlar [talep eden: geri çek · muhatap: incele/çözümle] + yeni-talep dialog).
  `lib/types/support.ts` + `lib/api/support.ts` (supportKeys mine/inbox/detail) +
  `lib/hooks/use-support-mutations.ts` (create/reply/withdraw/review/resolve).
  4 route: `/teacher/support` ("Destek" — koç↔öğrenci `/teacher/requests`'ten
  AYRI) · `/institution/support` ("Taleplerim") · `/institution/support-inbox`
  ("Gelen Talepler") · `/admin/support` ("Talepler"). 3 shell'e nav (teacher
  "Destek"; institution yeni "Talepler" bölümü; admin "Sistem" grubu). Durum
  tonları purge-safe explicit (koyu temada okunur). invalidate: `support:mine` /
  `support:inbox`. Verify: tsc ✅ · eslint ✅ · build ✅ (4 route). **NOT: tarayıcı
  testi yapılmadı (ortam yok) — yalnız derleme doğrulandı; canlı smoke kullanıcıya.**
- **Yönlendirme (kurum yöneticisi → süper admin) ✅ + DÜZELTME** (2026-05-23,
  **migration `c0d3g5h6g44a`** — escalated_by_id/escalated_at, additive):
  kurum yöneticisi çözemeyeceği (teknik/şifre vb.) talebi süper yöneticiye
  yönlendirir. `POST /support/requests/{id}/escalate` (yalnız ilgili kurum yöneticisi
  + audience=institution_admin + kapanmamış): muhatap institution_admin → super_admin,
  status→Açık, üstlenen sıfırlanır, **escalated_by_id set**, thread'e "[Yönlendirme]"
  notu eklenir.
  - **KULLANICI BUG BİLDİRİMİ (2026-05-23)**: İlk "hand-off" tasarımı yanlıştı —
    yönlendirince talep kurum yöneticisinin kutusundan **tamamen kayboluyordu** ve
    süper adminin cevabı kurum yöneticisine **geri düşmüyordu**. DÜZELTİLDİ:
    `escalated_by_id` ile yönlendiren talebi GÖRMEYE + cevabı izlemeye devam eder
    (3 taraflı thread: talep eden + yönlendiren + süper admin).
  - `get_viewable` (talep eden | aktif muhatap | yönlendiren) GET detay + reply
    erişimi; `list_inbox_institution_admin` `or_(aktif kuyruk, escalated_by==admin)`
    → yönlendirilen talep kutuda KALIR; `is_active_recipient` eylem yetkisi (yönlendiren
    artık review/resolve YAPAMAZ — aktif muhatap süper admin). Schema +can_manage/
    escalated/escalated_by_name/is_escalator. Frontend: aksiyonlar `can_manage` bazlı,
    yönlendiren için "yönlendirildi — cevap burada görünür" notu + "Yönlendirildi" rozeti,
    yönlendirme sonrası seçim KORUNUR (kutu boşalmaz).
  - **CANLI TEST** `scripts/live_support_flow.py` (gerçek HTTP + cookie jar, tarayıcı
    yolu :3000 → rewrite → :8081): 3 akış (koç→süper admin cevap döner / öğretmen→
    kurum yöneticisi / öğretmen→yönlendir→süper admin) + 4 sayfa render → **17/17**
    kullanıcının canlı stack'inde. API smoke `test_api_v2_support_requests.py` **46/46**
    (ESC.4 kutuda kalır · ESC.8 yönlendiren cevabı görür · ESC.9 talep eden görür).
- **Dosya eki + rol-renk + tıklanabilir profil ✅** (2026-05-23, **migration
  `d1e4h6i7h55b`** — support_attachments, additive):
  - **Dosya eki**: ekran görüntüsü (jpg/png/webp/gif) + fatura (pdf). `support_attachments`
    (data LargeBinary **deferred** — liste/detayda yüklenmez; DB'de saklanır → dev
    SQLite + prod Postgres taşınabilir, volume/S3 yok). `POST /requests/{id}/attachments`
    (multipart, get_viewable + kapanmamış; 10 MB / 10 ek / tür beyaz liste) ·
    `GET /requests/{id}/attachments/{att_id}` (stream inline, get_viewable + request_id
    eşleşmesi → yetkisiz 404). Frontend: `uploadSupportAttachment` (multipart bare fetch
    — gerekçeli eslint-disable) + `useUploadAttachment` + "Dosya" butonu + "Ekler"
    bölümü (görsel önizleme / pdf ikon + indirme).
  - **Rol-renk**: mesaj balonu gönderen rolüne göre (koç/öğretmen sky · kurum yöneticisi
    amber · süper admin violet — purge-safe ROLE_TONE) + rol etiketi.
  - **Tıklanabilir profil**: `sender_profile_url` viewer-erişimli (süper admin→
    /admin/users/{id} · kurum yöneticisi→kendi öğretmeni /institution/teachers/{id} ·
    diğer→link yok). Koç/öğretmen başka profillere erişemez → rol etiketi 'kim bu'yu yanıtlar.
  - **Test**: API smoke **54/54** (ATT.1–5 + PROF.1–3) · CANLI `live_support_flow.py`
    :3000 **22/22** (D1–5 ek yükle/indir/yetkisiz-404 + profil/renk + 4 sayfa render).
    **Cleanup notu**: SQLite FK CASCADE devrede değil → smoke/live cleanup'a
    SupportAttachment silme eklendi (id-reuse ile yetim ek mirası — ürün hatası DEĞİL).

Migration head: `d1e4h6i7h55b`. Commit'ler: `97b8075` (M1) · `8ca4871` (M3) ·
`df60ec0` (M2 backend) · `b0926a8` (M2 UI) · `854b0ec` (M1-M3 docs) ·
`8530ecb` (M5 tek-kaynak kopya + kurumsal iletişim) · `9c013b9` (M6 pakete duyarlı signup) ·
`62c1d7f`/`3a6738e`/`4cb7363`/`4eb9c80` (trial yaşam döngüsü Faz 1-4) ·
`352e6fc`/`93bd059` (öğrenci detay Durum Özeti + kontrast/başarı kartları) ·
`0641ef9` (AI ücretli kapı FIRE + yükseltmede reaktivasyon) · `4369630` (paywall
mesaj güncellemeleri) · `b5749f5` (abonelik iptal akışı testi) ·
`38035b8` (rol-bazlı talep sistemi backend + 32/32 test) ·
`863aeed` (talep sistemi frontend 3 panel) · `268a967` (talep yönlendirme) ·
talep yönlendirme DÜZELTME (escalated_by izleme + cevap geri düşer, canlı 17/17) ·
talep dosya eki + rol-renk + tıklanabilir profil (54/54 + canlı 22/22).

## Uyarı Akışı tazelik + Gördüm/Ertele (alarm körlüğü) — 2026-05-23

**Bağlam (kullanıcı 2026-05-23):** Pano "Uyarı Akışı"ndaki kırmızı/sarı uyarılar
canlı veriden hesaplanıyor (koşul düzelince düşüyor) ama "müdahale edildi mi /
ne kadar taze" bilgisi yoktu → işlenen ama koşulu süren uyarı kırmızı kalıp
**alarm körlüğü** yaratıyordu. Karar (3 onay): **Gördüm/Ertele + tazelik etiketi** ·
**süreli + koşul-düzelince sıfırla** · **önce öğretmen panosu**.

- **Backend ✅** (**migration `e2f5i7j8i66c`** — warning_states, additive):
  - `warning_states` (actor_id + student_id + code unique; first_seen_at +
    snooze_until + acknowledged_at). Uyarı kimliği = `(student_id, code)`.
  - `warning_state_service`: `reconcile_states` (feed her yüklemede — yeni uyarıya
    first_seen yaz, **canlıda olmayan = koşul düzeldi → SİL** [tekrar ederse taze]),
    `set_snooze` (gördüm/ertele N gün), `clear_snooze` (geri al). DEFAULT 3 / MAX 30 gün.
  - `GET /teacher/dashboard/warnings-feed` artık reconcile yapar + commit eder
    (GET ama durum-izleme yan etkisi); response `rows` (aktif) + `snoozed_rows`
    (ertelenenler) + `total` + `snoozed_count`; her satır +code/age_days/snoozed/
    snooze_until. `POST .../warnings/ack` + `.../warnings/unack` (sahiplik 404).
  - **snooze_until > now → aktif akıştan gizli**; süre dolunca koşul sürerse otomatik
    geri döner. Tablo generic (actor_id) → kurum yöneticisi + süper admin sonra reuse.
  - `scripts/test_api_v2_teacher_warning_ack.py` **9/9** (feed+code+age · ack→
    ertelenenler · unack→aktif · sahiplik 404 · reconcile purge). CANLI
    `live_warning_ack.py` :3000 **6/6** (gerçek HTTP + pano render).
- **Frontend ✅** (yalnız öğretmen panosu): `dashboard-client.tsx` WarningRow yeniden
  yapı — yaş etiketi (Clock "N gündür") + hover'da **Gördüm** (3 gün) / **7g** butonları;
  yeni **Ertelenenler (N)** açılır bölümü (Geri al). types +code/age_days/snoozed/
  snooze_until + snoozed_rows/snoozed_count; `useAckWarning`/`useUnackWarning`.
  Verify: tsc ✅ · eslint ✅ · build ✅ · tenant 29 temiz.
- **NOT**: warnings-feed GET artık yazma yapıyor (reconcile commit) → SQLite'ta
  eşzamanlı pano polling ile nadiren kısa kilit (geçici). Kurum yöneticisi + süper
  admin panoları kapsam dışı (sonraki adım, aynı tablo reuse).

## Durum-bazlı satır renklendirme (kurum panosu + öğrenci listesi) — 2026-05-23

**Bağlam (kullanıcı):** Kurum yöneticisi sınıflara/koçlara odaklanır; risk bir
bakışta görünmeli. Tablo/liste satırları **orana/uyarı seviyesine göre zemin
tonu** alsın (D4 eşikleri: <%40 kırmızı acil · %40–69 turuncu dikkat · ≥%70 yeşil).
- **Kurum panosu** (`institution/dashboard-client.tsx`) "Öğretmenler — Bu Haftaki
  Performans": `rateRowClass(weekly_rate_pct)` ile satır zemini (saydam ton +
  sol şerit, koyu temada okunur) + başlıkta renk göstergesi (legend). Pasif
  öğretmen tonlanmaz (muted).
- **Öğrenci listesi** (`teacher/students-list-client.tsx`): `levelRowClass(
  worst_warning_level)` — **kırmızı + turuncu** satırlar belirgin tonlanır,
  **yeşil temiz** bırakılır (uzun listede gürültü/alarm körlüğü olmasın; sorunlar
  öne çıkar).
- **"Neden kırmızı?" görünürlüğü** (kullanıcı sordu): satır renginin SEBEBİ
  görünmüyordu (sadece nokta/renk). Örn. Yiğit %86 haftalık ama kırmızı —
  sebep `projection_shortfall` "Sınava yetişmeyecek" (ileriye dönük). List item'a
  `worst_warning_title`/`worst_warning_detail` eklendi (endpoint en kötü uyarıyı
  level-rank ile seçer); satırda e-postanın altında kırmızı/sarı **uyarı başlığı**
  gösterilir (detay hover). tsc/eslint/build temiz · students smoke 14/14.
  NOT: "Sınava yetişmeyecek" stratejik bir uyarı RED'tir; istenirse şiddeti
  (red→amber) ayrı tartışılır.

## Projeksiyon uyarı şiddeti + koç login yönlendirme (2026-05-23)

- **Projeksiyon uyarısı şiddeti** (`analytics.generate_warnings`): `projection_shortfall`
  ("Sınava yetişmeyecek") artık **her zaman amber (dikkat)** — yalnız `rate_per_day>0`
  iken (öğrenci AKTİF çalışırken) tetiklenir; acil hareketsizlikle (red) aynı şiddette
  değil. Tamamen durmuş öğrenci için ayrı `projection_zero_rate` **red** kalır.
  (Eski: deficit>%20 → red.) Gerekçe: aktif ama tempoca geride olan öğrenci kritik
  değil, dikkat. Warning smokes (alert 9/9 · warn-ack 9/9) temiz.
- **Koç login yönlendirme bug fix**: bağımsız koç (TEACHER) login/signup/şifre-değiştir/
  kök sonrası boş `/teacher` index'ine düşüyordu (canlıda `/teacher`→`/teacher/dashboard`
  redirect'i tetiklenmiyordu → panele inemiyordu). 5 yön (login-form · page.tsx roleHome ·
  password-change · signup-teacher · signup-invite) artık **doğrudan `/teacher/dashboard`**.
  Canlı doğrulama: GET / → /teacher/dashboard (dashboard içeriğiyle).

## Sol menü "işleyince azalan" rozetler — koç paneli (2026-05-23)

**Karar (kullanıcı):** Rozet = ele alınmamış sayı; **sadece tıklayınca değil
İŞLEYİNCE azalır** (alarm körlüğü önleme — e-posta tarzı "görünce sıfırla" REDDEDİLDİ).
Kapsam: önce koç paneli.
- `GET /teacher/badges` rozet semantiği değişti (warning_states/ack altyapısına bağlandı):
  - **at_risk_count** ("Öğrenciler") artık = en az bir **AKTİF (ertelenmemiş)** uyarısı
    olan öğrenci sayısı → koç "Gördüm/Ertele" yapınca düşer (eski: risk-assessment).
    Hesap: student_snapshot + WarningState snooze anahtarları (muted hariç).
  - **support_answered_count** ("Destek", yeni) = koçun süper admine açtığı,
    **süper adminin cevapladığı (answered)** talep sayısı → koç yanıtlayınca/çözülünce düşer.
  - **pending_request_count** ("Talepler") değişmedi (cevaplayınca azalır — zaten işleyince-azalan).
- Frontend: teacher-shell "Destek" nav'ına `badgeKey: support_answered_count`; badgeKey
  union + tip güncellendi. Test: `test_api_v2_teacher_warning_ack.py` **11/11** (R1 ack
  öncesi at_risk≥1 · R2 tüm uyarılar ack'lenince at_risk=0 = işleyince azalır).
- **3 panele YAYILDI ✅** (2026-05-23, migration YOK):
  - **Kurum yöneticisi** (`GET /institution/badges`): "Gelen Talepler" =
    support_inbox_pending (öğretmenlerden bekleyen, cevapla/çöz→düşer) · "Taleplerim"
    = support_answered (süper adminin cevapladığı kendi talepleri).
  - **Süper admin** (`GET /admin/badges`): "Talepler" = support_pending · "İletişim
    Talepleri" = contact_new (yeni iletişim/abonelik talebi).
  - **Öğrenci** (site-header, mevcut badge'e ek): "Bugün" = today_open_count (bugünün
    tamamlanmamış görevleri, tikleyince düşer) · "Talepler" = pending_count (koç yanıtı).
  - institution-shell + admin-shell'e badge altyapısı eklendi (useQuery 60s + NavGroup/
    SidebarLink/MobileDrawer'a badge threading + NavBadge). Canlı: 3 endpoint 200 +
    doğru alanlar. Regresyon: institution 18 · admin 13 · contact 11 · support 54 ·
    tenant 29. tsc/eslint/build temiz.
  - **NOT:** koç + kurum badges poll'u student_snapshot/sorgu döngüsü yapıyor (60s) —
    çok öğrencide maliyet; gerekirse paylaşılan cache ile optimize edilir.

## Görev şablonları (TaskTemplate) — 2026-05-23

**Bağlam (kullanıcı):** Kütüphanedeki "Görev şablonları" kartı yanlış etiketliydi —
`/teacher/library/templates`'e (BookTemplate = kitap bölüm yapısı) gidiyordu ama
"sık kullandığın görev kalıpları, planda tek tıkla uygula" diyordu. Yani **gerçek
görev şablonu özelliği yoktu**; kullanıcı kitap şablonu oluşturup "neden görev
eklerken görünmüyor?" dedi. Karar: gerçek özelliği inşa et + kartı düzelt.
Kaydetme: mevcut görevden + ayrı form (ikisi).

- **Backend ✅** (**migration `f3g6j8k9j77d`** — task_templates + task_template_items,
  additive; tasktype enum `create_type=False` Postgres-güvenli):
  - `TaskTemplate` (teacher_id, name, type) + `TaskTemplateItem` (book+section+
    planned_count). Öğretmen-düzeyi; uygulama anında normal görev doğrulamaları
    (kitap sahipliği + bölüm + öğrenci ataması + rezerv + paywall).
  - Uçlar (`teacher.py`): GET/POST `/task-templates` · POST `/task-templates/
    from-task/{id}` (mevcut görevi şablona çevir) · DELETE `/task-templates/{id}` ·
    POST `/students/{id}/tasks/from-template` (tek tıkla uygula → `_create_task_with_items`
    reuse). Sahiplik 404.
  - `scripts/test_api_v2_teacher_task_templates.py` **11/11**.
- **Frontend ✅**: types + api (`taskTemplates` key + `getTaskTemplates`) + 4 hook
  (create/from-task/delete/apply). Yeni sayfa `/teacher/library/task-templates`
  (liste + "Yeni görev şablonu" formu: kitap→bölüm→sayı çok-kalemli + sil) +
  `task-templates-client`. Kart düzeltmesi: eski kart "Kitap şablonları" oldu
  (BookTemplate), yeni "Görev şablonları" kartı → task-templates. **Day-board
  entegrasyonu**: "Şablondan" butonu → picker (tek tıkla uygula) + her görev
  kartında "Şablon olarak kaydet" (BookmarkPlus → from-task). Canlı (:3000):
  oluştur 200 · uygula 200 (görev oluştu) · sayfa render 200. Regresyon: teacher_read
  12 · paywall 5 · tenant 29. tsc/eslint/build temiz.
- **NOT (kavram ayrımı):** Kitap şablonu = kitabın bölüm/ünite yapısı (başka kitaba
  uygulanır, kütüphane). Görev şablonu = görev kalıbı (kitap+bölüm+test sayısı,
  plana uygulanır). İkisi AYRI.

## "Koça ilet" — risk/tükenmişlik panosundan koça müdahale + tutarsızlık analizi (2026-05-24)

**Bağlam (kullanıcı):** Kurum Tükenmişlik/Risk panoları yalnız LİSTELİYOR; yönetici
"bu öğrenci için ne yapabilir?" diye sordu. Gizlilik gereği yönetici öğrenci
detayına inemez → tek müdahale kolu KOÇtur. Seçenek A onaylandı: panoya koç adı +
"Koça ilet" butonu (ilgili koça müdahale talebi).

**İki tanı sorusu (gerçek veriden yanıtlandı):**
- **Yiğit tutarsızlığı**: Tükenmişlik panosu `compute_burnout` (yük/düşüş metriği),
  Müdahale Merkezi `risk_analysis` kullanır — FARKLI metrikler. Yiğit burnout
  "Uyarı 50" ama risk_analysis "ok (15)", programı var (%66) → Müdahale Merkezi'nde
  yok. Bug değil, farklı ölçüm.
- **Programsız/düşük-uyum uyarısı**: `simulate_action_center.py` 10/10 kanıtladı
  (boş 2→uyarı/3→kritik, uyum %10→kritik/%30→uyarı). ETUTKOC'ta tek aktif öğrenci
  (programı var) olduğu için Müdahale Merkezi 0; boş/düşük öğrenci eklenince çıkar.

**Uygulama (aşağı yönlü SupportRequest):**
- **Migration `h5i8l0m1l99f`** (down_revision g4h7k9l0k88e): `support_requests.target_user_id`
  (nullable FK→users, SET NULL). **Additive**, downgrade'li, uygulandı. **Migration
  head = h5i8l0m1l99f.**
- Model: yeni `SUPPORT_AUDIENCE_TEACHER="teacher"` (audience String, enum migration
  yok) + `target_user_id` + `target_user` relationship + `student_risk` kategori.
- Servis `support_request_service`: `notify_coach(admin, teacher, ...)` (audience=
  teacher, target_user_id=koç; tenant: koç yöneticinin kurumuna bağlı olmalı) +
  `list_inbox_teacher` + `list_inbox` dispatcher + `pending_count_teacher` +
  `is_active_recipient`'a TEACHER dalı (koç kendi hedefli talebinin aktif muhatabı).
- **Yön asimetrisi**: support sistemi artık çift yönlü — yukarı (koç/öğretmen→
  yönetici→süper admin) + aşağı (yönetici→koç). Koç hem talep eden hem muhatap olabilir.
- Endpoint `POST /api/v2/institution/notify-coach` (`_require_institution_admin`;
  koç kurum-dışıysa 404). `/support/inbox` + review/resolve TEACHER'ı kapsar
  (`_is_recipient_role`'a TEACHER eklendi; yetki `get_for_recipient` ile).
- Frontend: paylaşılan `notify-coach-dialog.tsx` (NotifyCoachTarget + not + KVKK
  notu; setState-in-effect yerine "prop değişince render'da sıfırla" deseni) ·
  burnout-client + at-risk-client'a "Sorumlu koç" sütunu + "Koça ilet" butonu +
  güncellenmiş gizlilik notu · `useNotifyCoach` hook · yeni `/teacher/support-inbox`
  sayfası (SupportCenter view="inbox" reuse) · teacher-shell "Gelen Talepler" nav +
  `support_inbox_pending` rozeti (işleyince azalır — cevaplayınca düşer).
- **Test**: `test_api_v2_notify_coach.py` **13/13** + `test_api_v2_support_requests.py`
  **54/54** (YET.1/3/4 yeni davranışa güncellendi: koç inbox 200-boş; öğretmen kendi
  talebini yönetemez → 404) + CANLI `live_notify_coach_flow.py` :3000 **13/13**
  (notify→inbox→rozet→cevap→rozet düşer→çözüm + 3 sayfa render). Regresyon: teacher
  badges 11 · institution_p2 19 · action_center 8 · compliance 10 · tenant 29 GREEN.
  tsc/eslint temiz (build YOK — :3000 dev çalışıyor).
- **NOT (bağımsız koç)**: institution_id NULL koç hedef alınamaz → gelen kutusu
  her zaman boş (200, items=[]). notify_coach yalnız kurum yöneticisi → kendi
  kurumunun koçu.

## Kurum logosu / co-branding (2026-05-24, migration `i6j9m1n2m00g`)

**Bağlam (kullanıcı):** Kurumların kendi logoları olsa; kurum yöneticisi + bağlı
öğretmen panellerinde "hangi kuruma aitim" logoyla görünse. Bağımsız koçun
kurumsal kimliği yok → onlar değişmez. Kullanıcı kararları (AskUserQuestion):
**süper admin yükler · yönetici + öğretmen panellerinde göster · bağımsız koç =
sadece platform markası**. Tam müşteriye-dönük white-label zaten Enterprise satış
vaadi (pricing) — solo koça verilmedi (konumlandırma korunur).
- **Migration `i6j9m1n2m00g`** (down_revision h5i8l0m1l99f): `institutions.logo_data`
  (LargeBinary **deferred**) + `logo_content_type` + `logo_updated_at`. **Additive**,
  downgrade'li, uygulandı. **Migration head = i6j9m1n2m00g.** Logo DB'de saklanır
  (support-attachment deseni — S3/volume yok, SQLite/Postgres taşınabilir, KVKK
  açısından kişisel veri değil).
- Model `Institution.has_logo` property (logo_content_type dolu mu — data yüklemez).
- **Backend**: serve `GET /api/v2/institution/logo/{id}` (`get_current_user_v2`;
  süper admin VEYA kurumun üyesi — img src cookie ile; aksi 404, anonim 401) ·
  süper admin `POST /admin/institutions/{id}/logo` (multipart, PNG/JPEG/WebP ≤2MB,
  400 invalid_file_type/file_too_large) + `/logo/delete` (INSTITUTION_UPDATE audit) ·
  `/me` InstitutionRef + admin kurum detayı `InstitutionDetailBrief`'e `has_logo` +
  `logo_url` eklendi.
- **Frontend**: paylaşılan `components/institution-brand.tsx` (logo varsa next/Image
  + ad; yoksa Building2 chip — emerald). `institution-shell` (sidebar chip + mobil)
  bunu kullanır; `teacher-shell`'e `institution` prop eklendi + teacher layout
  `data.institution` geçirir → bağlı öğretmen header'ında co-brand; bağımsız koç
  (institution null) → yalnız platform markası (değişmedi). Admin kurum detayına
  **logo kartı** (`LogoCard`: önizleme + yükle/değiştir/kaldır + cache-bust) ·
  `useUploadInstitutionLogo` (multipart bare-fetch, gerekçeli eslint-disable) +
  `useDeleteInstitutionLogo`.
- **Test**: `test_api_v2_institution_logo.py` **12/12** (403/401 + tür/boyut +
  yükle/serve/sil + cross-tenant 404 + /me + admin detay) + CANLI
  `live_institution_logo.py` :3000 **9/9** (yükle→/me logo_url→serve→3 sayfa
  render→sil). Regresyon: notify_coach 13 · me 13 · admin 13 · admin_institutions 23 ·
  institution 18 · institution_p3 18 · tenant 29 · api_v1 47 GREEN. tsc/eslint temiz
  (build YOK — :3000 dev). **NOT**: çoklu backend dosyası düzenlerken :8081
  WatchFiles ara reload'unda login geçici 500 verebilir; reload oturunca düzelir.

## Vitrin Kartları otomatik keşif — buton + cron + kopuk servis denetimi (2026-05-24, migration `j7k0n2o3n11h`)

**Bağlam (kullanıcı):** "Yeni özellik eklendikçe Vitrin'de kart açılır diyoruz ama
sonra eklenenleri görmüyorum — verimi analiz et + testler yap." Sonra: "başka
kopuk servisler var mı? derinlemesine test."

**Tanı (kanıtlı):** `feature_discovery` algılama motoru (migration docstring + git
commit tarar) KUSURSUZ çalışıyor — `discover_features.py --dry-run --since 2026-05-15`
**99 aday** buldu (logo/koça-ilet/deneme/hata-tercüman/pricing/KS/support…). AMA
tarama **hiç otomatik tetiklenmiyordu**: `discover_all`+`apply_candidates` yalnız
`scripts/discover_features.py` (elle CLI) + testten çağrılıyordu. Admin UI'da "tara"
butonu YOK, cron YOK. Keşif kartları 2026-05-08→05-14'te donmuştu; 66 kart
incelenmemiş bekliyordu. Verim ≈ %0.

**Çözüm (buton + cron):**
- `feature_discovery.run_scan(db, *, actor_id, days=120)` — tara+uygula tek adım
  (endpoint + cron paylaşır; idempotent — mevcut slug'ları atlar).
- `cron_jobs.feature_discovery_scan` + JOB_REGISTRY; **migration `j7k0n2o3n11h`**
  (down_revision i6j9m1n2m00g): `feature_discovery_scan` CronSchedule seed (haftalık
  Pzt 05:00 UTC, idempotent INSERT). **Migration head = j7k0n2o3n11h.**
- `POST /admin/feature-catalog/discovery-queue/scan` (`_require_super_admin`,
  `days` query, audit FEATURE_CARD_AUTO_DISCOVERED) → `DiscoveryScanResult`
  (created/skipped/candidates).
- Frontend: discovery-queue sayfası header'ına **"Şimdi tara"** butonu
  (`useScanDiscovery` + RefreshCw + invalidate `_fc_invalidate`).
- **Test**: `test_api_v2_admin_discovery_scan.py` **7/7** (rol + tara + idempotent +
  cron fonksiyonu doğrudan + schedule/registry eşleşmesi) + CANLI
  `live_discovery_scan.py` :3000 **6/6** (tara→created=50/candidates=95→kuyruk
  arttı→idempotent→sayfa render; testler delta'yı temizler). Regresyon:
  feature_catalog 25 + feature_discovery unit 31. tsc/eslint temiz.

**KOPUK SERVİS DERİNLEMESİNE DENETİMİ** (yeni `scripts/audit_orphan_triggers.py` +
reachability analizi):
- **Modül düzeyi**: 105/105 servis bir entrypoint'ten (route/cron/dep) erişilebilir
  — tamamen ölü servis dosyası YOK. Scheduler GERÇEKTEN çalışıyor (main.py lifespan
  + dispatcher `cron_tick`). Kapalı (disabled) schedule YOK.
- **3 KOPUK TETİKLEYİCİ bulundu** (kod var/çalışır ama canlı app'ten tetiklenmiyor):
  1. **feature_discovery scan** — ✅ bu oturumda DÜZELTİLDİ (buton + cron).
  2. **`health_snapshot_daily`** — JOB_REGISTRY'de ama **CronSchedule YOK** → hiç
     çalışmaz. `record_daily_snapshots` yalnız bu cron'dan çağrılıyor →
     `HealthScoreSnapshot` **2026-05-16'da donmuş (10 satır)** → sağlık trend/churn
     geçmiş karşılaştırması ölü. **Düzeltme bekliyor** (1-satır cron seed, trial_expire
     deseni).
  3. **`expire_old_offers`** — cron olarak tasarlanmış ama JOB_REGISTRY'de YOK +
     schedule YOK; yalnız script çağırıyor. Teklif görüntülenince lazy expire var
     (offers.py:351) → kısmen telafi; ama hiç açılmamış süresi-geçmiş teklifler SENT
     kalır (admin gelir/funnel sayımını şişirir). **Düzeltme bekliyor** (JOB_REGISTRY +
     cron seed).
- NOT: #2 ve #3 düzeltmeleri kullanıcı onayı bekliyor (migration içerir).

## Vitrin stratejisi — hizmet→değer haritası + anasayfa kartları (2026-05-25)

**Bağlam (kullanıcı):** Asıl hedef = kurum (özel okul/etüt/dershane/elit kurs) +
bağımsız koçların ÜYE olması; bu da sorunlarına çözüm vaadiyle olur. İstenen:
hizmetleri rol kategorisinde grupla → kime ne fayda → ticari değerlileri anasayfa
vitrinine yansıt. Sonra: "vitrin kartları zaten bunun için var, sistemden fazla mı
bekledik?" → **Hayır.** feature_catalog birebir "içerik hazırla → anasayfada yayınla"
CMS'i; sadece kartları üretip yayına almak + segment filtresi eklemek kaldı.

**Vitrin kartı çalışma mantığı:** admin `/admin/feature-catalog`'tan kart oluşturur/
düzenler → `status=published` + `mockup_type` dolu (5 geçerli: daily_schedule/
fsrs_rating/burnout_gauge/books_progress/whatsapp_chat) → landing `/api/v2/landing`
yayın kartlarını çeker (pin'liler tepede, gerisine A/B + fuzzy skor + MMR çeşitlilik)
→ anasayfada gösterir; telemetri (impression/view/demo_click) skoru besler.

**Strateji (onaylandı, koç-öncelikli):** 11 fayda-odaklı yayın kartı —
- **Koç (6, ana akış · audience=teacher):** erken-uyarı (hero) · AI seans hazırlığı
  (premium) · sesli/foto not (premium) · sürdürülebilir plan · veli bilgilendirme ·
  tahsilat. target_roles=['teacher'].
- **Kurum (5, #kurumlar bandı · audience=institution_admin):** program uyumu ·
  müdahale merkezi · akademik çıktı · öğretmen karnesi · veli güveni.
  target_roles=['institution_admin'].

**Uygulama:**
- Backend: `_build_landing_cards`/`get_for_landing_with_variant` + `/api/v2/landing`'e
  **`audience` filtresi** (target_roles'a göre; "teacher"=koç vitrini,
  "institution_admin"=kurum bandı). Geçersiz audience → boş (hata değil).
- `scripts/seed_landing_cards.py` — 11 kartı **idempotent** yayınlar (slug `kesfet-*`;
  slug varsa ATLAR → admin'deki sonraki düzenlemeler korunur). Eski 5 genel kart
  (daily-plan/aralikli-tekrar/dna-risk/soru-bankasi/veli-kanali) yeni kartlar öne
  çıksın diye **HIDDEN** (silinmez; `--delete` ile geri PUBLISHED + yeni kartları siler).
- Frontend: anasayfa ana feed `audience=teacher`; `#kurumlar` bandının alt mini-kartları
  artık **feature_catalog-güdümlü** (`audience=institution_admin`, statik değil) —
  ısı haritası görseli + CTA korundu.
- **Kart metinleri admin'den düzenlenebilir** (kullanıcı sonra düzeltecek):
  `/admin/feature-catalog` → kart → düzenle formu.
- **Premium (AI) kartları:** category_label "Yapay Zekâ" + "Ücretli pakette" benefit
  (şema değişikliği yok; AI gerçekten ücretli pakette).
- Test: `test_api_v2_landing_audience.py` **8/8** + landing_public regresyon 8/8 +
  canlı :3000 (koç 6 / kurum 5 / anasayfa 200). tsc/eslint temiz (build YOK — :3000 dev).
- **Commit YOK** (kullanıcı henüz istemedi). Migration GEREKMEDİ (sadece veri/kod).

**"Nasıl Çalışır?" — uçtan uca koçluk döngüsü (2026-05-25):** Anasayfa
`#nasil-calisir` bölümü genel 5-adımdan **rol-renkli 7-adım koçluk akışına**
yeniden kurgulandı (`HowItWorks` + `ROLE_TONE` purge-safe ton map): ①Koç kütüphaneyi
kurar (kitap ünite/test sayıları) →②Koç günlük/haftalık program hazırlar (**rezerv**
açıklanır: atanan soru kitaptan düşülür, kalan kapasite görünür) →③Öğrenci günlük
uygular (tamamladım işareti + doğru/yanlış) →④Sistem ölçer →⑤Veli bilgilenir →⑥Koç
erken müdahale (döngü başa sarar) →⑦Kurum tek panelden görür. Her adımda aktör
rozeti + "→ çıktı" satırı + aktör lejantı + döngü kapanış bandı.
- **Konumlandırma:** bölüm güven şeridinin (`Reassurance` — 14 gün ücretsiz…) HEMEN
  ALTINA taşındı (Hero→Reassurance→**HowItWorks**→Features→…).
- **Kullanıcı geri bildirimi:** eski açıklamalar jargonluydu ("anlık kaynak durumu" —
  ziyaretçi "kaynak"ı bilmiyor); süreci anlatan sade cümlelere çevrildi + kütüphane
  kurulumu + **rezerv** özelliği + öğrencinin günlük "tamamladım" işaretlemesi tanıtıldı.
- `cn` import edildi, kullanılmayan `Users` ikonu kaldırıldı. tsc/eslint temiz · canlı
  :3000 render doğrulandı.

## Hata düzeltme — yeni görev başlığı "Görev" placeholder'ı (2026-05-25)

**Kullanıcı bulgusu:** Hafta/gün görünümünde görev ekleyince satır **"Görev"**
yazıyordu; ama görevi düzenle→güncelle yapınca **"Kitap — Bölüm: N test"** oluyordu
(tutarsız). Kök neden: tek-kalem düzenleme (`teacher_patch_task_single_item_v2`)
başlığı kalemlerden besteliyordu ama **oluşturma (`_create_task_with_items`)
frontend'in gönderdiği sabit `title:"Görev"`'i kullanıyordu** (add-task-form
placeholder). Satır her zaman `task.title` gösterdiği için yeni görevde "Görev"
kalıyordu.
- **Düzeltme (backend, migration YOK):** paylaşılan `_compose_single_item_title(book,
  section, planned)` helper'ı çıkarıldı; `_create_task_with_items` tek kitap-kalemli
  görevde başlığı otomatik üretir (oluşturma = düzenleme tutarlı). Kitapsız deneme/
  etkinlik kalemleri kendi label/başlığını korur. Single-item patch de aynı helper'ı
  kullanır (DRY). Frontend değişmedi (backend tek kaynak).
- **Doğrulama:** `test_task_title_autocompose.py` **3/3** (oluştur→otomatik başlık ·
  düzenle→tutarlı · kitapsız deneme→label korunur). Regresyon: weekly_plan 14 +
  teacher_read 12 + task_templates 11 + paywall 5 + itemless 10 GREEN.

## Deploy hazırlığı — repo-içi eksikler kapatıldı (2026-05-25)

Deploy hazırlık denetiminde bulunan 4 repo-içi eksik giderildi (sunucuya
dokunulmadı; canlı deploy + secret'lar kullanıcının sorumluluğunda):
- **`deploy/docker-compose.yml`** (web env): **GEMINI** (`GEMINI_API_KEY`/paid/free
  + model) + **Turnstile** (`TURNSTILE_SITE_KEY`/SECRET/ENABLED) env eklendi —
  yoksa AI prod'da ölü kalır / CAPTCHA açılamazdı. Boş bırakılabilir (AI panelden
  de girilebilir; Turnstile boşsa otomatik kapalı).
- **`deploy/.env.example`**: Gemini + Turnstile bölümleri eklendi + WhatsApp'a
  "token yoksa false yap" notu.
- **`start.sh`**: `python -m scripts.seed_landing_cards` eklendi (anasayfa vitrin
  kartları prod'da otomatik yayınlanır; idempotent — admin düzenlemeleri korunur).
- **`deploy/redeploy.sh`** (yeni): düzelt→tekrar gönder döngüsü için tek komut —
  git pull + migration öncesi DB yedeği (pg_dump) + `up -d --build` + web log takibi.
- Doğrulama: compose YAML geçerli (5 servis, GEMINI/Turnstile web env'de) +
  seed_landing_cards idempotent (11 atlandı). **Kullanıcının sağlayacağı**: sunucu
  + Static IP + alan adı/DNS + güçlü secret'lar (`openssl rand -hex 32`) + SMTP.
  **Karar**: temiz prod DB (dev verisi taşınmaz), WhatsApp ilk açılışta `false`.

## Dalga 7 — KAPANIŞ (2026-05-20)

**5 rolün tamamı + auth/güvenlik Next.js'e taşındı. Strangler Fig tamamlandı.**
Caddy'de Next.js'e yönlenen path'ler: `/me` `/student` `/teacher` `/institution`
`/parent` `/admin` `/login` `/password/*` `/signup/*` `/verify-email/*` `/offers/*`
+ `/legal/kvkk-veli`. Jinja'da kalan: `/logout` (BFF logout kullanılıyor), `/kvkk`
`/privacy` `/legal/*` (hibrit), webhooks, /static, /healthz.

**D7 migration kayıtları:** `o6p8s1t2s00m` (P2 password_reset_tokens) ·
`p7q9t2u3t11n` (P3 email_verification + users.email_verified_at) ·
`q8r0u3v4u22o` (P4 totp + backup codes). Hepsi additive + downgrade'li, uygulandı.

**Yeni bağımlılıklar:** `pyotp` (backend, requirements.txt) · `qrcode.react`
(frontend, package.json).

## WhatsApp İletişim Sistemi — Faz 1 (Click-to-WhatsApp) — DEVAM EDİYOR (2026-05-30)

**Strateji (kullanıcı 2026-05-30):** Yol A — önce **Click-to-WhatsApp** (manuel,
wa.me deep link, koçun kendi telefonu) Faz 1; sonra **Cloud API otomatik bildirim**
(merkezi etütkoç hattı) Faz 2. Otomatik bildirimler **bilgi bombardımanı YAPMAZ**;
her kullanıcı türü için kapsamlı + ölçülü.

**Onaylanan kararlar:** (1) Toplu hibrit (≤20 sıralı / 20+ broadcast) · (2) 2 telefon
birincil seç · (3) SMS doğrulama (Netgsm önerildi) · (4) Test modu (her şablon)
· (5) Karakter sayaç YOK · (6) Spam uyarısı (haftalık + günlük 100 üstü) · (7) AI
ton önerisi Faz 1.5 (Gemini) · (8) Şablon editörü süper admin paneli (35 şablon DB'de)
· (9) **Otomatik bildirim aktif/pasif yetkisi**: bağımsız koç + kurum yöneticisi
yapabilir, kuruma bağlı öğretmen YAPAMAZ (kurum politikası yöneticide).

- **P0 ✅ Notification preference altyapısı + Veli aktivasyon KVKK ekranı**
  (**migration `r5s8w0x1w99q`** — additive, downgrade'li, uygulandı):
  - **Migration**: `parent_notification_prefs` tablosuna 7 yeni `*_wa_enabled`
    kolonu (varsayılan False — opt-in/KVKK) + `child_whatsapp_consent` bool
    (18 yaş altı çocuk için doğrudan WA gönderim için veli onayı). Mevcut
    `*_enabled` kolonları **e-posta tarafı için** korunur (default True,
    eski davranış değişmez).
  - Backend: `ParentNotificationPref` model genişletildi (7 WA + child consent) ·
    `schemas/parent.py` `ParentPreferencesInfo` + `ParentPreferencesBody` +
    `ParentInvitationAcceptBody` (yeni opsiyonel: notification_preferences dict +
    quiet_start/end + child_whatsapp_consent) · `parent.py` `_build_preferences`
    + `update_preferences_v2` + `parent_invitation_accept_v2` (yeni veli kurulurken
    aktivasyon matrisindeki tercihler pref'e yansır; mevcut velide yalnız
    child_consent KVKK güncelleme olarak işlenir) · audit `kvkk_consent_v2`
    (yeni hesap veya child_consent=True).
  - **Producer kanal-aware** (`notification_producer.py`): `_KIND_TO_PREF_FIELD`
    (EMAIL → `*_enabled`, default=True/opt-out) + yeni `_KIND_TO_PREF_FIELD_WA`
    (WHATSAPP → `*_wa_enabled`, default=False/opt-in). Adım 2 kanala göre alanı
    seçer; SMS (yalnız OTP) bypass. Geriye uyum: eski EMAIL çağrıları aynen çalışır.
  - **KVKK metni** `/legal/kvkk-veli` 3 yeni alt-madde: **4.1 İletişim Kanalları**
    (her tür ayrı, Meta gizlilik) · **4.2 18 Yaş Altı Çocuk için WhatsApp**
    (veli onayı zorunlu) · **4.3 İletişim İptali** (her tür ayrı kapatma + "DUR" +
    tek-tıkla unsub).
  - **Frontend aktivasyon ekranı** (`parent-invitation-client.tsx`) 3 bölüme
    bölündü: ① Hesap bilgileri (ad/şifre) ② **İletişim tercihleri** (7×2 matris
    + sessiz saat + "Çocuğum WhatsApp alabilir" onayı + amber bilgi notu "WA için
    Bildirim Tercihleri'nden telefon doğrulayın") ③ KVKK onayı.
  - **Frontend ayarlar sayfası** (`parent-settings-client.tsx`) PreferencesForm
    matris düzenine geçti: 7 satır × E-posta/WhatsApp 2 sütun + toplu işlem
    butonları (E-posta/WA hepsini aç/kapat) + çocuk WA onayı kartı. WhatsAppCard
    (telefon doğrulama akışı) ve ChildrenMuteCard değişmedi.
  - `scripts/test_api_v2_parent_wa_channel.py` — **14/14 yeşil** (settings GET +
    POST yeni body + eski body geriye uyum + 4 aktivasyon senaryosu [yeni body /
    child_consent True / child_consent False / eski istemci] + 5 producer
    kanal-aware senaryosu). Regresyon: parent 20 + parent_invitation 17 GREEN.
    Verify: tsc ✅ · eslint ✅.

- **P1 ✅ Telefon altyapısı (User.phone) + Netgsm SMS doğrulama + `/me/phone/*`**
  (**migration `s6t9x1y2x00r`** — additive, downgrade'li, uygulandı):
  - **Politika kararı (kullanıcı 2026-05-30):** sisteme kim üye olursa olsun
    signup/davet sırasında cep telefonu zorunlu istenir + SMS ile doğrulanır.
    Kullanıcının cep telefonu = WhatsApp numarası (ayrı tutulmaz).
  - **Migration**: `User.phone/_verified_at/_secondary/_secondary_verified_at`
    (yalnız PARENT secondary kullanır — anne+baba ayrımı) + generic
    `phone_verifications` tablosu (user_id FK + slot primary|secondary +
    channel sms|whatsapp, varsayılan sms). **Veri taşıma**:
    `parent_notification_prefs.whatsapp_phone` (verified_at dolu olanlar)
    → `User.phone` + `User.phone_verified_at`. Eski pref kolonları boş
    bırakıldı (deprecated, geriye uyum için silinmedi).
  - **SMS provider** (`sms_provider.py`): Netgsm REST API "SMS GET" endpoint'i.
    `settings.sms_enabled=False` → log-only (dev); kullanıcı paneline kod
    `phone_dev_test_code` olarak yansır. `.env`: `SMS_ENABLED`,
    `NETGSM_USER/PASSWORD/HEADER/BASE_URL`.
  - **Phone servisi** (`phone_service.py`): `normalize_e164_tr()` — Türkiye
    cep formatı (5XX), 0/+90/90/0532/+905321234567 hepsini E.164'e
    ("905321234567"); 60sn cooldown + 10dk TTL + 5 max attempts.
    `start_phone_verification` / `verify_phone` / `delete_phone` /
    `pending_verification_for`.
  - **6 yeni endpoint** (`/me/phone/*`): start/verify/delete birincil +
    secondary (`secondary_slot_parent_only` 403 diğer rollere). `/api/v2/me`
    yanıtına `phone: MyPhoneInfo` eklendi (her iki slot durumu + dev kod +
    `secondary_slot_available` UI flag'i). Signup endpoint'lerinde
    (ParentInvitationAccept + SignupTeacher + SignupInvite) `phone` opsiyonel
    alan — verilirse normalize edilip User.phone'a yazılır, `verified_at=None`
    (panelde banner'la doğrulanır).
  - **Producer kanal=WHATSAPP** kontrolü P0'daki `pref.whatsapp_*` yerine artık
    `User.phone + User.phone_verified_at` bakar — tek doğruluk kaynağı.
    Dispatcher `_send_whatsapp` da `user.phone`'a geçti.
  - **Frontend**: `MyPhoneInfo` tipi + 6 mutation hook (Start/Verify/Delete ×
    primary+secondary, 9 error code TR etiketi). `/me/account` sayfasına
    `PhoneCard` (3 durum: kapalı / kod bekleniyor / doğrulandı, dev modda
    test kodu UI'da görünür). Veli için ek "İkinci Telefon" kartı (otomatik
    `secondary_slot_available=true` durumunda görünür).
  - `scripts/test_api_v2_phone_verification.py` — **14/14 yeşil** (normalize 7
    senaryo + start/verify/cooldown/wrong_code/delete + secondary 403 +
    parent secondary OK + unauth 401 + **signup invalid_phone 400** +
    **signup valid phone → User.phone normalize, verified_at NULL**). P0
    regresyon `parent_wa_channel` 14/14 + `me` 13/13 + `parent` 20/20 +
    `parent_invitation` 17/17 + `auth_p3` 13/13 GREEN. Verify: tsc ✅ ·
    eslint ✅.
  - **Üst banner** (`phone-verify-banner.tsx`): `user.phone_verified=false`
    iken her panelin üstünde kapatılamaz uyarı. "Şimdi Doğrula" tıklanınca
    inline Dialog açılır (panelden ayrılma yok, güvenlik algısı sorunu
    çözüldü) → içinde PhoneCard reuse → telefon ekle/kod gönder/doğrula tek
    dialog'ta. Doğrulama anında banner anlık kaybolur (live /me query),
    dialog kapanışında router.refresh(). 5 shell'e (teacher / parent /
    institution / admin / student layout) yerleştirildi. `/me/account`'a
    rol-bazlı "← Panele Dön" linki eklendi (eski tip standalone gezinti
    sorunu giderildi).
  - **Signup form'larına cep telefonu zorunlu alan** eklendi: bağımsız koç
    signup (`signup-teacher-form.tsx`), davet öğretmen signup
    (`signup-invite-form.tsx`), veli aktivasyon (`parent-invitation-client.tsx`).
    Her formda placeholder + açıklama (SMS ile doğrulanır) + invalid_phone
    backend hata kodu set-error. UserPublic.phone_verified flag'i SSR'a yansır
    → kayıt sonrası kullanıcı paneline geçince banner zaten beklemekte.

- **P2 ✅ Şablon registry + 35 seed + süper admin CRUD paneli**
  (**migration `t7u0y2z3y11s`** — additive, downgrade'li, uygulandı):
  - **Migration**: `whatsapp_templates` tablosu (key unique + category +
    target_role + name_tr + content_template + variables_json + requires_date +
    allow_bulk + allow_freeform_note + sort_order + is_active +
    created_at/updated_at + updated_by_id FK SET NULL). 2 index: kategori+sort
    ve target_role.
  - **35 şablon seed** (`scripts/seed_whatsapp_templates.py`, **idempotent** —
    key varsa atlar; `--reset` zorunlu silme+yeniden yazma): 10 veli (koç→veli)
    + 5 ogrenci (koç→öğrenci) + 5 kurum_ogretmen + 5 kurum_veli + 3 kurum_ogrenci
    + 5 admin_yonetici + 2 admin_sistem. Değişken sözdizimi `{{key}}` (Jinja
    deseni); 25+ ortak değişken tanımı (V_VELI, V_OGRENCI, V_KOC, V_TARIH vb.).
    Bayraklar: requires_date (toplantı/etkinlik), allow_bulk (bayram/duyuru),
    allow_freeform_note (tebrik/serbest mesaj).
  - **Backend**: `schemas/whatsapp_template.py` (8 model) ·
    `services/whatsapp_template_service.py` (render_preview + extract_keys +
    parse/serialize JSON) · `admin.py` 7 endpoint:
    - `GET /whatsapp-templates` (filter: category/target_role/include_inactive +
      categories+target_roles meta dict)
    - `GET /whatsapp-templates/{id}` (detay)
    - `POST /whatsapp-templates/preview` (preview — DİKKAT: `{id}` route'undan
      ÖNCE tanımlı; FastAPI route çözümleyicide string "preview"i int olarak
      yakalamasın diye)
    - `POST /whatsapp-templates` (create — key unique check 409 key_taken)
    - `POST /whatsapp-templates/{id}` (update — key haricinde her şey)
    - `POST /whatsapp-templates/{id}/toggle-active` (aktif/pasif)
    - `POST /whatsapp-templates/{id}/delete` (yalnız pasif — aktif şablon
      400 template_active, defensive)
  - `scripts/test_api_v2_admin_whatsapp_templates.py` — **15/15 yeşil** (liste +
    3 filter + invalid_category + create + key_taken + update + toggle + delete
    aktif/pasif + preview rendered + unknown_keys warnings + TEACHER 403).
    Regresyon: admin 13/13 + phone 14/14 GREEN.
  - **Frontend**: `lib/types/whatsapp-template.ts` (10 tip) · `lib/api/admin.ts`
    +3 fetcher + 2 queryKey (`whatsappTemplates(category,role,active)` +
    `whatsappTemplate(id)`) · `use-admin-mutations.ts` +4 mutation hook
    (Create/Update/Toggle/Delete) + 5 error code TR etiketi.
    `/admin/whatsapp-templates` sayfa + client component:
    - Header: KPI (toplam/aktif/pasif) + kategori filter chip-bar + "Pasifleri göster"
      toggle + "Yeni Şablon" CTA
    - Kategori bazlı gruplu liste (statik ton map): satır = ad + key + bayrak
      rozetleri (Toplu/Tarihli/Serbest not) + içerik preview (line-clamp-2) +
      hedef rol + değişken sayısı + Düzenle/Toggle/Sil aksiyonları
    - Form Dialog (create + edit ortak): key (yalnız create) + ad + kategori
      select + hedef rol select + sıralama + açıklama + içerik textarea +
      **dinamik değişken editörü** (3-kolon: key/etiket/örnek + ekle/sil) +
      4 bayrak checkbox + canlı **Önizleme** bloğu (POST /preview, örnek
      değerlerle render edilmiş yeşil kutu + warnings amber liste)
  - Admin sidebar "Sistem" grubuna **"WhatsApp Şablonları"** nav linki
    (MessageSquare ikon, AI Ayarları + Ücretlendirme'den sonra).
  - Verify: tsc ✅ · eslint ✅ (preview mutation için `lgs/missing-invalidate`
    gerekçeli disable — preview saf okuma).

- **P3 ✅ Click-to-WA URL üretici + yetki + dispatch log**
  (**migration `u8v1z3a4z22t`** — additive, downgrade'li, uygulandı):
  - **Migration**: `whatsapp_dispatch_logs` tablosu (sender CASCADE +
    target SET NULL + template_key + template_id SET NULL +
    params_json + character_count + created_at). 2 index:
    sender+created, target+created. P3'te yalnız yazılır, P6 spam guard
    okur.
  - **Servis** `whatsapp_link_service.py`:
    - `mask_phone_e164()` — "+90 532 *** ** 67" deseni
    - `build_wa_url()` — `https://wa.me/{e164}?text={percent_encoded}`
      (UTF-8 RFC 3986 quote; Türkçe `ş` → `%C5%9F` doğru encode)
    - `can_send_wa_to(db, sender, target)` — yetki matrisi:
      - SUPER_ADMIN → herkese
      - INSTITUTION_ADMIN → aynı kurum içi
      - TEACHER → kendi öğrencisi + öğrencisinin velisi (ParentStudentLink join)
      - Kendine her zaman serbest (test gönderimi)
    - `build_wa_dispatch(...)` ana fonksiyon: şablon doğrula + hedef yetki +
      telefon kontrolü + render + freeform_note (allow_freeform_note guard) +
      URL üret + dispatch log yaz. Uzunluk uyarısı (2000+ karakter).
  - **Endpoint** `POST /api/v2/messaging/wa-link`:
    - Auth: TEACHER + INSTITUTION_ADMIN + SUPER_ADMIN (PARENT/STUDENT 403
      role_not_allowed)
    - Body: template_id + target_user_id + variables + freeform_note (opsiyonel)
    - 404 hataları (template_not_found, target_not_found) → yetki sızıntı
      önleme (yetki yoksa "yok" der, "yasak" demez)
    - 400 hataları: target_phone_not_verified + freeform_not_allowed
    - Yanıt: wa_url + rendered_text + target_name + target_phone_masked +
      character_count + long_text + warnings + log_id
  - Yeni router `messaging.py` (api_v2/__init__'e kayıt).
  - `scripts/test_api_v2_messaging_wa_link.py` — **13/13 yeşil** (anon 401 +
    PARENT 403 + template 404 + target 404 + phone_not_verified 400 + yabancı
    koç 404 sızıntı önleme + happy [coach→öğr/veli + admin→herkes] + freeform
    note guard + maskeleme deseni + Türkçe percent-encoded URL).
  - Regresyon: admin_wa_templates 15/15 + phone 14/14 + parent_wa_channel 14/14.

- **P4 ✅ Tekli gönderim dialog (WaSendDialog) + kapsamlı 5-kullanıcı test**
  (migration YOK — P3 altyapısını UI'a bağlıyor):
  - **Backend ek 2 endpoint**:
    - `GET /api/v2/messaging/templates` — kullanıcının rolüne uygun aktif
      şablonlar (TEACHER → teacher+any; INSTITUTION_ADMIN → institution_admin+any;
      SUPER_ADMIN → hepsi). admin CRUD endpoint'inden farklı: kompakt brief
      model (target_role UI'da gösterilmez, zaten filtreli).
    - `GET /api/v2/messaging/target/{user_id}` — hedef özeti + yetki check
      (sızıntı önleme: 404 target_not_found). Phone_masked + phone_verified flag.
  - **Frontend**:
    - `lib/types/messaging.ts` — 7 tip · `lib/api/messaging.ts` 3 fetcher +
      messagingKeys
    - **`WaSendDialog` paylaşılan bileşen** — 7 bölüm:
      1. Hedef header (isim + maskeli telefon + Shield ikon emerald/amber)
      2. "🧪 Önce kendime test gönder" toggle (sender verilirse)
      3. Kategori chip-bar (filter)
      4. Şablon select (rol filtreli liste)
      5. Değişken alanları (otomatik example pre-fill — useEffect değil
         event handler içinde, React önerisi)
      6. Freeform note alanı (yalnız allow_freeform_note=True şablonlarda)
      7. Önizleme paneli (gerçek render, "Önizle" butonu) + karakter sayım +
         uzun mesaj uyarısı
    - "WhatsApp'ı Aç" → POST /wa-link + `window.open(wa_url, "_blank")` +
      toast bilgilendirme ("son gönder tuşunu siz basacaksınız")
  - **Entegrasyonlar**:
    - `/teacher/students/[id]` QuickActions'a **"WA Gönder"** emerald-tonlu
      buton (öğrenci hedefli, defaultCategory="ogrenci")
    - Veliler panelindeki her satıra **MessageSquare ikon** (parent_id hedefli,
      defaultCategory="veli")
  - `scripts/test_api_v2_messaging_p4_comprehensive.py` — **21/21 yeşil
    (KULLANICI İSTEĞİ: kapsamlı 5-kullanıcı testi)**:
    - **K1 Bağımsız koç (5 test)**: şablon filtresi + kendi öğrencisine WA +
      velisine WA + başka kurum öğrencisine 404 sızıntı önleme
    - **K2 Kuruma bağlı öğretmen (3 test)**: kendi öğrencisi → 200 / aynı
      kurum başka öğretmenin öğrencisi → 404 (koç yetkisi yalnız teacher_id) /
      başka kurum → 404
    - **K4 Kurum yöneticisi (4 test)**: şablon filtresi + aynı kurum öğretmen/
      öğrenci → 200 / başka kurum → 404
    - **K5 Süper admin (3 test)**: tüm şablon tipleri görünür + her hedefe WA
    - **V1 Veli yetki yok (3 test)**: 403 role_not_allowed × 3 endpoint
    - **Dispatch log içgörü (3 test)**: kayıt sayısı + template_key + char_count
  - Regresyon: messaging_wa_link 13/13 + admin_wa_templates 15/15 + phone 14/14
    GREEN. Verify: tsc ✅ · eslint ✅.

- **P5 ✅ Toplu gönderim sihirbazı (hibrit ≤20 sıralı / 20+ broadcast)**
  (migration YOK — P3 altyapısı + P4 dialog deseni reuse):
  - **Backend `whatsapp_bulk_service.py`**:
    - `GROUPS_BY_ROLE` matrisi: TEACHER → my_parents/my_students;
      INSTITUTION_ADMIN → inst_parents/inst_teachers/inst_students;
      SUPER_ADMIN → hepsi
    - `list_bulk_targets(sender, group_key)` → eligible (telefon doğrulu) +
      no_phone (doğrulanmamış) ayrı. Yetkisiz grup → boş + available_groups
      (UI hangi grupları gösterebileceğini bilir)
    - `build_bulk_dispatch(sender, template_id, target_user_ids, ...)` →
      yetki + telefon kontrolü → eligible için URL üret + dispatch log yaz,
      yetkisiz/telefonsuz hedefler `skipped[]`'a düşer (sızıntı önleme: yetki
      yoksa "no_permission", görünür değil)
    - MAX_BULK_TARGETS = 200 (güvenlik). allow_bulk=False şablon →
      400 bulk_not_allowed
  - **2 yeni endpoint**:
    - `GET /messaging/bulk-targets?group=...` → hedef adayları + UI için
      available_groups menu
    - `POST /messaging/bulk-link` → toplu URL üret (mode=sequential|broadcast)
  - **Frontend** `BulkSendWizard` (4 adım, "use client" sayfa):
    1. **Şablon seçici** — allow_bulk=True şablonlar kategori başlığı ile gruplu
       (tıkla → otomatik example pre-fill + step 2)
    2. **Değişkenleri doldur** — tüm hedeflere aynı değer (Adım 2'ye geç)
    3. **Hedef grubu seç** — chip-bar (rolüne göre available_groups) +
       hedef listesi (eligible + no_phone ayrı, "Tümünü seç" / "Temizle"
       toplu işlem)
    4. **Gönderim modu** — `<20` hedef "Sıralı (önerilen)" otomatik seçili,
       `≥20` "Broadcast (önerilen)". `> ~100` sıralı disabled.
       - **Sıralı görünüm**: 1/N current target gösterimi, "WhatsApp'ı Aç"
         → window.open + tamamlanan rozeti, "İleri/Geri" nav
       - **Broadcast görünüm**: 2 panoya-kopyala kutusu (mesaj + telefon
         listesi) + "WA Business broadcast list" talimat banner
  - Sayfa: `/teacher/bulk-wa` + `/institution/bulk-wa` (ortak `<BulkSendWizard />`).
    Teacher-shell ve institution-shell sidebar'larına **"Toplu WhatsApp"**
    nav linki (MessageSquare ikon).
  - `scripts/test_api_v2_messaging_bulk.py` — **15/15 yeşil**:
    - 5-kullanıcı: anon 401, koç my_students/my_parents (2 eligible+1 no_phone),
      koç yetkisiz inst_teachers (boş+available_groups dolu), kurum yön. inst_teachers/
      inst_parents (kendi kurumu), süper admin tüm grup keys görünür
    - Mutation: allow_bulk=False 400, MAX 200 sınırı, boş hedef 422, 3 hedef
      [2 OK + 1 telefonsuz] → 2 dispatched + 1 skipped phone_not_verified,
      yabancı hedef karışık → no_permission skipped, log her başarılı için yazıldı,
      mode=broadcast rendered_text üretildi, invalid_mode 400
  - Regresyon: messaging_p4_comprehensive 21/21 + wa_link 13/13 +
    admin_whatsapp_templates 15/15 + phone 14/14 GREEN. **Toplam WA test
    78/78 GREEN.**
  - Manuel test setup'larına `sys.path.insert` patch eklendi
    (PYTHONPATH=. olmadan çalışsın).
  - Verify: tsc ✅ · eslint ✅.

- **P6 ✅ Audit + Spam Guard** (migration YOK — P3 dispatch_log altyapısını
  okuyor):
  - **Backend `whatsapp_spam_guard.py`**:
    - `compute_dispatch_stats(sender)` → today_count + week_count (Pazartesi
      00:00 UTC haftası) + warning_level
    - Eşikler: `<50/gün` → "ok" (sessiz) / `50-99` → "yogun" (amber uyarı) /
      `≥100` → "cok_yogun" (rose). **Engelleme YOK** — Faz 1 manuel akış,
      koçun sorumluluğu; sistem yalnız bilgilendirir
  - **2 yeni endpoint**:
    - `GET /messaging/dispatch-stats` (koç görür: bugün+hafta sayım + uyarı)
    - `GET /admin/whatsapp-dispatch-log?days=N&sender_id=...&limit=50` (süper
      admin: log liste + summary{today/week/period/top_senders[5]})
  - **Frontend `SpamGuardBanner`**:
    - "ok" + hafta_count==0 → tamamen sessiz
    - "ok" + hafta varsa → küçük gri özet ("Bu hafta N mesaj")
    - "yogun" → amber AlertTriangle banner
    - "cok_yogun" → rose Flame banner
    - 60s polling + refetch on focus
    - `/teacher/bulk-wa` ve `/institution/bulk-wa` sayfalarının üstüne yerleştirildi
  - **Frontend `/admin/whatsapp-dispatch-log` sayfası**:
    - 4 KPI kartı (Bugün/Hafta/Period/En aktif sender)
    - Filtre: süre chip-bar (1/7/30/90g) + sender_id input
    - Top 5 sender tablosu (tıkla → filter)
    - Log tablosu (zaman / sender / target / şablon / karakter)
    - Silinmiş şablon → "(silinmiş şablon)" / Silinmiş target → "(silindi)"
  - Admin sidebar "Sistem" grubuna **"WhatsApp Audit"** nav (Activity ikon)
  - `scripts/test_api_v2_messaging_p6_spam_audit.py` — **12/12 yeşil**:
    - 5-kullanıcı: anon 401, veli 403, koç (0/30/60/110 log) → uyarı seviyesi
      doğru hesaplandı + 14 gün önceki log bu hafta sayım'a girmedi
    - Admin endpoint: veli 403, koç 403, süper admin 200 + items + summary +
      top_senders + sender_id filter + days clamp
  - **`days=0 or 7 == 7` bug** giderildi (clamp doğrudan max/min ile).
  - Regresyon: bulk 15/15 + p4 21/21 + wa_link 13/13 + admin_templates 15/15 +
    phone 14/14 GREEN. **Toplam WA test 90/90 GREEN.**
  - Verify: tsc ✅ · eslint ✅.
  - **UI kontrast düzeltmesi** (kullanıcı bildirdi): aktif top-sender butonunda
    `bg-emerald-100` zemin + default `text-foreground` → koyu temada beyaz
    metin + açık zemin = okunmaz. CLAUDE.md "kontrast iyileştirme" kuralı:
    açık-zemin durumda **explicit koyu emerald** (text-emerald-900/800/700)
    purge-safe. Log tablosunda aktif satır vurgulaması zemin yerine
    `border-l-4 border-l-emerald-500` (zemin müdahalesi yok, her iki temada
    belirgin). Tablo metinleri `text-emerald-800/900` yerine `text-foreground`
    (semantic tema değişimine duyarlı).

- **P7 ✅ Faz 1 KAPANIŞ — smoke runner + tam setup + manuel rehber**:
  - `scripts/run_faz1_smokes.py` — tüm P0-P6 smoke'larını sırayla çalıştırır,
    her paket başına PASS/FAIL özet + toplam. Çıktı:
    **🎉 Faz 1 — 104/104 passed · 0 failed** (P0 14 + P1 14 + P2 15 + P3 13 +
    P4 21 + P5 15 + P6 12).
  - `scripts/faz1_full_setup.py` — tek komutla 5 rol ekosistemi (süper admin +
    bağımsız koç A + kurum yön. + kuruma bağlı öğretmen B + 2 öğrenci +
    3 veli [1 telefonsuz "skipped" senaryo için]) + kurum X. Tüm telefonlar
    önceden doğrulu, dispatch_log temiz. `--inject-busy` 70 log (amber banner)
    veya `--inject-heavy` 120 log (rose banner) opsiyonu.
  - `scripts/faz1_full_cleanup.py` — tüm `faz1_*` kullanıcı + kurum + bağımlı
    kayıtları siler.
  - `scripts/faz1_manuel_test_rehberi.md` — adım-adım her panel için tarayıcı
    senaryosu (P0 aktivasyon · P1 telefon · P2 admin şablon · P3-P4 tekli
    dialog · P5 toplu sihirbaz · P6 spam banner + admin audit · F3 koyu tema
    kontrast).
  - P0 smoke testine `sys.path.insert` patchi eklendi (PYTHONPATH=. olmadan
    çalışabilsin).

## Faz 1 — KAPANIŞ ÖZETİ (2026-05-31)

**Click-to-WhatsApp Faz 1 tamamlandı.** Tüm akış: koç/yönetici/süper admin
şablon havuzundan seçer → değişkenler doldurulur → URL üretilir → koç wa.me
linkini yeni sekmede açar → WhatsApp Web/uygulamasında metin hazır → koç son
gönder tuşunu basar. Sistem audit altında: her tetik dispatch_log'a yazılır;
koç günde 50+/100+ mesaj atınca banner uyarı; süper admin tüm aktiviteyi
panelden izler.

**Migration sayım (Faz 1):**
- `r5s8w0x1w99q` — parent_notification_prefs WA kanal toggle'ları (P0)
- `s6t9x1y2x00r` — User.phone + phone_verifications generic tablo (P1)
- `t7u0y2z3y11s` — whatsapp_templates tablosu (P2)
- `u8v1z3a4z22t` — whatsapp_dispatch_logs tablosu (P3)
- Toplam: **4 additive migration**, downgrade'li, prod-uyumlu.

**Yeni endpoint sayım (Faz 1):**
- Veli: 0 yeni (mevcut /settings genişletildi)
- /me/phone/*: 6 (start/verify/delete × primary+secondary)
- Admin /whatsapp-templates: 7 (CRUD + preview)
- /messaging/*: 5 (templates/target/wa-link/bulk-targets/bulk-link/dispatch-stats)
- Admin /whatsapp-dispatch-log: 1
- Toplam: **~19 yeni endpoint**.

**Veri akışı:**
- Şablon kaynağı: süper admin DB tabanlı (CRUD), 35 idempotent seed.
- URL üretici: `wa.me/{phone}?text={percent_encoded}` (RFC 3986 UTF-8).
- Yetki: koç → kendi öğrencisi+velisi; kurum yön. → kurum içi; süper admin → herkes.
- Sızıntı önleme: yetkisiz hedef → 404 target_not_found (varlık ifşası yok).
- Spam guard: 50/gün amber, 100/gün rose, hafta sayım. **Engelleme YOK** —
  Faz 1 manuel akış koç sorumluluğu.
- Audit: dispatch_log her tetikte yazılır; admin panelden tüm aktivite görünür.

**Faz 1'in sınırı (Faz 2 yapacaklar):**
- Otomatik bildirimler hâlâ **e-posta + producer** kanalında; WhatsApp Cloud API'ye
  bağlanmadı (Meta Business hesabı + onaylı şablonlar + kredi sistemi gerek).
- **Mobil app push notification** — yapıldığında otomatik bildirimler buraya
  kayar (Click-to-WA manuel olarak değerli kalır; koç-veli bireysel akış için).
- SMS sağlayıcı **dev stub**; prod'da `SMS_ENABLED=true` + Netgsm `.env` ile
  gerçek SMS gider.

## Faz 2 — Yol Haritası (yapılacaklar listesi)

**Önerilen sıra (kullanıcı onayına bağlı):**

1. **Mobil App — iOS+Android** (Önerilen ilk)
   - React Native veya Capacitor (Next.js → mobil)
   - Push notification altyapısı (FCM + APNs)
   - Veli/öğrenci/koç paneli mobil-optimized
   - **Otomatik bildirim ana kanalı** olur: e-posta + push (WhatsApp opsiyonel)

2. **WhatsApp Cloud API entegrasyonu (otomatik bildirimler)** — opsiyonel
   - Meta Business hesabı + WABA + Phone Number ID
   - Onaylı şablonlar (Meta inceleme süreci)
   - Webhook (gelen mesajlar — Faz 3 inbox için)
   - Kredi sistemi (mesaj başı maliyet, kullanıcı paketine bağlı)
   - **Faz 1 click-to-WA değişmez** — koç-veli bireysel akış için tutulur

3. **Çift yönlü WA inbox** — koç paneline gelen veli mesajlarını yansıtır
   (Cloud API webhook'u + UI inbox)

4. **AI ton önerisi (Faz 1.5)** — bayram/duyuru şablonlarında Gemini ile
   3 ton (Sıcak/Resmi/Esprili). Mevcut AI altyapısına bağlanır.

5. **Netgsm SMS prod** — `.env`'e kimlikler + SMS_ENABLED=true.

**Sırada:** kullanıcı kararıyla; manuel test ✅ ise mobil app veya Cloud API.

**🎯 Mimari karar (kullanıcı 2026-05-30):** **Mobil app (iOS/Android) yapıldığında
otomatik bildirimler push notification ile gönderilecek** → bu durumda **Faz 2
(WhatsApp Cloud API otomatik bildirim) büyük ölçüde gereksiz** olabilir.
Faz 1 (manuel Click-to-WhatsApp, koçun kendi telefonu) yine de **değerli kalır**
— koç-veli/öğrenci bireysel mesajları + toplu duyurular için push yetmez.
**Sıralama:** Faz 1 (yapılıyor) → mobil app + push (otomatik bildirim ana kanalı)
→ Faz 2 (Cloud API) **yeniden değerlendirme** (belki sadece push'a ulaşmayan
acil sinyaller için tutulur). E-posta otomatik bildirim altyapısı zaten var, kalır.

## Sırada

**Açık iş kalmadı — tüm dalgalar (D0-D7) tamamlandı.** Olası sonraki adımlar
(kullanıcı onayına bağlı):
- **Canlı deploy doğrulama**: Caddy reload + manuel smoke (login/2FA/signup/
  forgot/oturum/teklif akışları canlı ortamda) — kullanıcının sorumluluğunda.
- **2FA zorunlu kılma** (şu an opsiyonel): istenirse admin rolleri için login
  duvarı eklenebilir.
- **Turnstile + SMTP prod yapılandırması**: `.env`'e `TURNSTILE_*` + `SMTP_*` +
  `EMAIL_ENABLED=true` (şu an log-only / CAPTCHA kapalı).
- **Jinja dead-code temizliği** — "Jinja'ya dokunma, kalsın" gereği yapılmıyor.

**Jinja dead-code** (teacher/institution/parent/admin route + template) — "Jinja'ya
dokunma, kalsın" gereği yapılmıyor.

## Canlı Yayın (Production) — 2026-05-26

**Sistem CANLI:** https://rotam.etutkoc.com
- **Sunucu:** Hetzner Cloud CPX22 (178.105.221.223), Docker Compose 5 servis
  (db/web/worker/next/proxy). Caddy otomatik HTTPS (Let's Encrypt).
- **DNS:** Cloudflare — `rotam` A kaydı → 178.105.221.223 (DNS-only/gri bulut,
  Caddy LE için). Kök alan `etutkoc.com` GoDaddy'de kayıtlı, DNS Cloudflare'de.
- **Kod yolu:** sunucuda `/opt/etutkoc`; güncelleme `deploy/redeploy.sh`
  (git pull + DB yedek + `docker compose up -d --build`). SSH anahtarı
  kullanıcının yerel Windows makinesinde.
- **DB:** prod Postgres. Gerçek veri `scripts/migrate_subset.py` ile taşındı
  (KEEP_USERS={1,2,4,6,7}, KEEP_INST={1}; FK-closure ile test/demo junk dışlandı;
  operasyonel log tabloları SKIP). `scripts/init_db.py` (users yoksa create_all+
  stamp / varsa upgrade head) initial-migration alfabetik FK-sırası çökmesini çözer.
  alembic head = `l9m2p4q5p33j`.
- **Yedekleme (2 katman):** (1) sunucuda günlük `pg_dump -Fc` cron (03:00 UTC,
  14 gün rotasyon, `deploy/backup.sh` → `deploy/backups/*.dump`, .gitignore'da);
  (2) Hetzner otomatik snapshot AÇIK (disk-dışı felaket kurtarma). Geri yükleme:
  `cat backups/X.dump | docker compose exec -T db pg_restore -U lgs -d lgs --clean --if-exists`.
- **E-posta CANLI:** Zoho SMTP (`smtp.zoho.com:587` STARTTLS, gönderim
  `rotam@etutkoc.com`). `.env`: EMAIL_ENABLED=true + SMTP_HOST/PORT/USER/PASSWORD/
  FROM (compose'da TLS=true/SSL=false sabit). Uçtan uca doğrulandı (raw smtplib +
  app `send_email` APP_SEND_OK). SPF/DKIM zaten Zoho için Cloudflare'de tanımlı
  (yeni DNS gerekmedi). Hacim artarsa ZeptoMail'e geçilir (aynı domain).
  **NOT:** kurulumda kullanılan app şifresi sohbete sızmıştı → Zoho'dan iptal
  edilip yeni app şifresiyle değiştirildi (`deploy/rotate_smtp.sh` ile, 2026-05-26;
  gönderim yeni şifreyle doğrulandı).
- **Gemini AI CANLI:** süper admin panelden ücretli (gemini-2.5-pro) + ücretsiz
  (gemini-2.5-flash) anahtar girildi; gerçek `generate()` çağrısıyla ikisi de
  doğrulandı (2026-05-26). AI özellikleri (foto/ses not, koçluk içgörüsü, kitap
  şablonu) artık çalışır. Anahtarlar `system_secrets`'te (Fernet şifreli).
- **Bekleyen (kullanıcı aksiyonu):**
  - **Gemini AI anahtarları** — süper admin panel → Sistem → AI Ayarları'ndan
    girilecek (Fernet anahtarı farklı olduğu için `system_secrets` taşınmadı;
    girilene kadar AI özellikleri 502 ai_unavailable verir, diğer akışlar etkilenmez).
  - **Ödeme** (iyzico/PayTR) — ticari üyelik/şirket gerektirir; sonraya bırakıldı.
  - **Mobil** (iOS/Android) — en son.
- **Güvenlik notları:** GitHub repo PUBLIC (ticari kod açıkta — private yapılmalı);
  `/opt/etutkoc/deploy/.env` güvenli kopyası alınmalı (DB parolası + JWT/SESSION
  secret'ları).
- **Turnstile CAPTCHA prod'da AÇIK (2026-06-01):** sunucu `/opt/etutkoc/deploy/.env`'e
  gerçek `TURNSTILE_SITE_KEY` + `TURNSTILE_SECRET_KEY` girildi (`TURNSTILE_ENABLED=1`),
  `docker compose up -d web` ile recreate. Önceden anahtarlar BOŞ olduğu için
  `turnstile.is_enabled()` False → login/signup/forgot CAPTCHA'sı tamamen bypass
  ediliyordu (sınırsız hesap açılabiliyordu). Artık `/login` · `/signup/teacher` ·
  `/forgot-password` token zorunlu (token'sız → 401 captcha_failed, hesap oluşmaz).
  `/signup/invite/{token}` bilinçli kapsam dışı (geçerli tek-kullanım davet token'ı
  zaten kapı). **Kod zaten doğruydu** (frontend widget + backend verify); sorun salt
  config'di. **Rollback:** `.env`'de `TURNSTILE_ENABLED=0` + `docker compose up -d web`
  (<60sn). **NOT:** secret sohbete yazıldı → Cloudflare'den döndürülmesi (rotate)
  önerildi. Widget'ın Cloudflare'deki izinli domain listesinde `rotam.etutkoc.com`
  olmalı; tarayıcı testi kullanıcıda.
  - **Ek (2026-06-01) — /pricing kurumsal teklif formu da Turnstile'a bağlandı:**
    `POST /api/v2/contact` (`contact_public.py`) artık `turnstile.is_enabled()` ise
    token doğrular (token yok → 401 captcha_failed; public form → contact_requests +
    satışa e-posta spam koruması). Frontend: `pricing/page.tsx` config'i çeker →
    `pricing-client` → `institution-contact` widget'ı basar (dark tema; sekme
    remount'unda da render). `test_api_v2_contact.py` 13/13 (12-13 monkeypatch
    enforcement). Kod commit + `web`/`next` rebuild ile deploy. Kapsam dışı kalanlar:
    `/signup/invite` (token kapı), `/api/v2/landing/telemetry` (anonim ölçüm).
- **OpenAPI docs prod'da KAPALI (2026-06-01):** `app/main.py` FastAPI artık
  `docs_url/redoc_url/openapi_url`'i yalnız `DEBUG=true` (dev) iken açar; prod
  (`DEBUG=false`) → `/docs` · `/redoc` · `/openapi.json` 404. Tüm API saldırı
  yüzeyinin ifşası önlendi. Canlı doğrulandı (üçü de 404, /healthz + /api/v2 +
  / 200). Commit `9cb602b`, sunucuda `git pull` + `web`/`worker` rebuild ile
  deploy edildi.
- **Soft telefon doğrulama modu (2026-06-01):** Türkiye'de SMS başlığı (sender ID)
  şirket + operatör onayı gerektirdiğinden SMS henüz canlı değil. Eskiden
  `SMS_ENABLED=false` iken: (a) "Cep telefonunuzu doğrulayın" banner'ı her panelde
  **kapatılamaz** çıkıp kullanıcıyı doğrulayamayacağı bir akışa zorluyordu; (b)
  `_is_dev_sms_stub() = not is_sms_enabled()` olduğu için **OTP kodu prod'da
  `/me` yanıtında sızıyordu**. Düzeltme: `MyPhoneInfo.verification_available =
  is_sms_enabled()` eklendi → frontend banner yalnız `verification_available===true`
  iken görünür; `PhoneCard` SMS kapalıyken doğrulama formu yerine "Yakında" bilgi
  paneli gösterir (numara kayıtlıysa görünür, dead-end yok). `_is_dev_sms_stub`
  artık `settings.debug AND not is_sms_enabled()` → prod'da (DEBUG=false) OTP kodu
  asla yanıta konmaz; yerelde (DEBUG=true) dev kodu görünmeye devam eder (smoke
  korunur). **Signup'ta telefon hâlâ toplanır** (SMS gönderilmediği için kayıt
  kilitlenmez); SMS açılınca herkesin numarası hazır. SMS canlıya alınınca
  (VatanSMS bireysel hesap → `SMS_ENABLED=true`) banner + doğrulama akışı
  **otomatik** geri gelir (kod değişikliği gerekmez). Smoke phone 15/15 (sc.15 =
  soft-mod sinyali) + me 13/13.

## KRİTİK fix — login returnUrl rol-uyuşmazlığı / /me/account dead-end (2026-05-26)

**Bağlam (kullanıcı bildirdi, localde de tekrar yaşanıyordu):** Süper admin
giriş yapınca `/me/account`'a düşüyordu (panele giremiyor). Tarayıcı linki ipucu:
`/login?returnUrl=%2Fteacher%2Fsettings` — kullanıcı giriş öncesi bir teacher
route'una gitmek istemiş (proxy `returnUrl` ekler), login bunu **rolden bağımsız**
uyguluyordu → süper admin `/teacher/settings`'e → teacher layout rol koruması onu
`/me/account` dead-end'ine atıyordu.
- **2 kök neden:** (a) `login-form.tsx` `returnUrlParam ?? defaultLandingFor(role)`
  — returnUrl her zaman tercih ediliyordu (rol kontrolü yok + **open-redirect**
  riski: `//evil.com`); (b) 5 panel layout rol-uyuşmazlığında `/me/account`
  catch-all'una düşürüyordu (admin layout hariç — o zaten her rolü kendi paneline
  yolluyordu).
- **Çözüm — tek kaynak `web/lib/role-home.ts`:** `roleHome(role)` (login landing +
  layout fallback; ASLA /me/account) + `safeReturnUrl(returnUrl, role)` (returnUrl
  yalnız kullanıcının kendi panel alanı veya paylaşılan `/me` altındaysa onurlandır;
  aksi halde null → open-redirect + rol-uyuşmazlığı koruması). login + 5 layout +
  kök sayfa bunu kullanır. Verify: tsc ✅ · eslint ✅ · canlıda `next` rebuild.
- **/me/account "güvenlik açığı" DEĞİL:** her kullanıcının kendi hesap sayfası;
  "Hesabımı sil" anlık silme değil — 30 gün gecikmeli + iptal edilebilir KVKK
  silme talebi, yalnız kendi hesabı (başkası süper admini silemez).
- **KURAL:** Bir rol koruması (layout/guard) kullanıcıyı yönlendirirken `roleHome`
  kullanır — boş sayfa veya `/me/account` dead-end bırakmak yasak. Yeni returnUrl
  tüketen her yer `safeReturnUrl`'den geçer.

## Proxy public path eksiği — şifre/doğrulama akışları kırıktı (2026-05-26)

**Bağlam (kullanıcı bildirdi):** Login sayfasındaki "Şifremi unuttum" butonuna
basınca form değişmiyordu; tarayıcı `/login?returnUrl=%2Fpassword%2Fforgot`'a
dönüyordu. Sebep: `web/proxy.ts` `PUBLIC_PATHS_PREFIX` listesinde **`/password/forgot`,
`/password/reset`, `/verify-email`, `/parent/unsubscribe` yoktu** — bu sayfalar
token ile / anonim erişilmesi gereken sayfalar; proxy onları "korumalı" sanıp
`/login`'e yönlendiriyordu (zaten login'desin → form değişmiyor).
- **Düzeltme** (`web/proxy.ts`): dört path public prefix listesine eklendi.
  `/password/change` listede YOK — auth gerekir (must_change flow).
- **KURAL:** Yeni public sayfa (token ile / anonim erişilir) eklenince `proxy.ts`
  PUBLIC_PATHS_PREFIX'e mutlaka eklenir; aksi halde proxy /login'e atar +
  ölü-bağlantı görünür.

## Mail akışı denetimi + dağıtık fix'ler (2026-05-26)

Kullanıcı şablon+SMTP testlerinin (Bölüm 1) yeterli olmadığını fark etti: şablon
render edilir + SMTP teslim eder ama **endpoint `send_email`'i çağırmazsa** mail
asla gitmez. Veli daveti bug'ı tam buradan kaçtı.
- **Sistematik kod denetimi** yapıldı (her şablon → helper → endpoint çağrı zinciri).
  Bulgular + düzeltmeler:
  - **API v2 veli davet**: `notify_parent_invitation` çağrısı eksikti → eklendi.
  - **publish-week** (haftalık program yayını): `event_triggers.on_program_published`
    hiç tetiklenmiyordu → eklendi (publish-day spam riski için manuel; mevcut
    `/program/notify-parents` butonu duruyor).
  - **Koç + Kurum abonelik talebi**: ContactRequest yazılıyordu ama admin'e mail
    gitmiyordu → `contact_request_admin` template'i ile satış adresine gönderim eklendi.
  - **Yeni signup → süper admin/satış bildirimi** (yeni özellik): `notify_new_signup_admin`
    helper'ı + `new_signup_admin.html` template'i. Bağımsız koç self-signup'ında
    satış adresine düşer.
  - **Placeholder mail temizliği**: `etutkocrotam.app` (yanlış, bounce eden) → `etutkoc.com`;
    `kvkk@etutkoc.com` → `destek@etutkoc.com` (kvkk@ alias'ı yok, destek'e yönlendir).
- **Yanlış pozitifler** (denetim incelmesi): student request açma + teacher response
  request_service'in içinde `_notify_new_safe`/`_notify_resolved_safe` zaten çağrılıyor.
  Endpoint'te bireysel çağrı eklemeye gerek yok.
- **KURAL**: Bir email-trigger endpoint eklendikten sonra **send_email çağrısı
  endpoint kodunda VEYA çağrılan service fonksiyonunda OLMALI** (her ikisi yoksa
  bug). Şablon+SMTP testi yeterli DEĞİL; endpoint integration için ayrı denetim.

## Proxy/Caddy operasyonel kurallar (2026-05-26)

- **`/parent/invitation/<token>`** Next.js'te yaşıyordu ama `proxy.ts`
  PUBLIC_PATHS_PREFIX'te `/parent/invite` (eski/404) vardı → login'e atıp form
  görünmüyordu. **Doğrusu `/parent/invitation`** (path eklenirken Next.js
  route'unun gerçek adına bak; varsayma).
- **Caddyfile bind-mount cache (kritik gizli bug)**: `deploy/Caddyfile`
  değiştirilip `docker compose exec proxy caddy reload --config /etc/caddy/Caddyfile`
  çalıştırılınca **Caddy aynı stale-FD'yi okumaya devam edebiliyor** — bind-mount
  güncellense bile reload eski içerikten beslenir (kernel/Docker mount cache).
  Belirti: yeni `reverse_proxy` satırları reload sonrası aktive olmaz, host'taki
  dosya doğru ama container içinde grep ile aranınca bulunmaz.
  - **KURAL**: Caddyfile değişikliklerinden sonra `caddy reload` YETMEZ →
    **`docker compose restart proxy`** kullan. Restart container'ı yeniden
    başlatır + bind-mount dosya tazece okunur. <60sn rollback (R-020).
- **Next.js public/ kök asset'leri (logo, mark vb.)** Caddyfile'a açıkça
  `reverse_proxy /etutkoc-logo.png next:3000` gibi yazılmalı — top-level statik
  asset'ler default'a düşerse FastAPI'den 404 alır. `/static/*` zaten FastAPI'de.

## Sistem sağlık paneli — yedek (pg_dump) takibi (2026-05-26)

- `/admin/system-health` sayfasına **BackupCard** eklendi: son yedek yaşı (saat/gün),
  boyutu, toplam dosya + disk kullanımı, sağlık eşiği (≤30h ok / 30-48h warn /
  >48h crit / dosya yok crit).
- Backend: `system_health.collect_backup_status()` + `BackupStatus` dataclass +
  `BackupStatusInfo` schema. Endpoint `/api/v2/admin/system-health`'e `backup` alanı.
- `BACKUP_DIR` env (varsayılan `/opt/etutkoc/backups`) — `backup.sh` aynı dizine yazar.
- **docker-compose**: web service'e read-only volume mount eklendi:
  `../backups:/opt/etutkoc/backups:ro`. Volume değişikliği `docker compose up -d --build web`
  yeniden oluşturma gerektirir.

## Üyelik & Aktivite Akışı — süper admin + kurum yöneticisi panelleri (2026-05-27, commit `dcee8a2`)

**Bağlam (kullanıcı):** Ticari değerli site için yeni üye/davet/satın alma akışı
mikro-bölünmüştü (audit log + contact_requests + users + invitations +
parent_invitations + plan_change_history hepsi ayrı yerlerde). Yöneticinin
"bugün kim katıldı / kim paket aldı / kim davet etti" sorusuna tek panelden yanıt
vermesi gerekiyordu. Migration YOK — mevcut tablolardan UNION query.

- **Backend** (`app/services/activity_stream.py`): `fetch_activity(institution_id,
  days, type_filter, limit)`. 5 kaynak chronological tek akışa birleşir:
  users (signup) + invitations (kurum→koç) + parent_invitations (koç→veli) +
  contact_requests (iletişim/abonelik talebi) + plan_change_history (UPGRADE öne
  çıkar). 4 kategori: **signup / invitation / commercial / change**. Sayımlar:
  total + signup + invitation + commercial + change + **purchases** (UPGRADE ayrı
  sayım — paket alımları). `institution_id=None` = süper admin (tüm sistem),
  INT = kurum yöneticisi (scoped: kendi öğretmenleri + öğrencileri + davetleri +
  plan değişimleri).
- **Endpoint'ler**: `GET /api/v2/admin/activity-stream` + `GET /api/v2/institution/
  activity-stream` (ikisi de aynı response şemasını döndürür, scope farkı backend'de).
  Schema `schemas/institution.py`'a 6 yeni model.
- **Frontend**: paylaşılan `components/activity-stream.tsx` (`ActivityStreamPage`)
  — 5 KPI kart + tarih (1g/7g/30g) + tip filter pills + chronological feed.
  `plan_upgrade` = yeşil highlight (PAKET SATIN ALMA), `is_commercial` = vurgulu kart.
  2 sayfa: `/admin/activity-stream` + `/institution/activity-stream` (server initial
  fetch + client TanStack Query). admin-shell + institution-shell sidebar'ına Panel
  altına **"Aktivite Akışı"** linki.
- **Durum**: commit + push (origin/main). Smoke testi YAZILMADI. Canlı tarayıcı
  doğrulaması kullanıcıya bırakıldı.

## Ödeme: TEK yöntem iyzico kart — havale/EFT kaldırıldı + CANLI (2026-06-25, commit `bc42453`)

**Bağlam (kullanıcı):** iyzico üyelik/üye-işyeri süreci tamamlandı → sistem tam açıldı.
İstek: sistemin HER noktasında ödeme yalnız iyzico kart; havale/EFT bilgilendirme/
linkleri kaldır.

- **Önce haritalandı** (KURAL: ödeme=para-kritik). Platform havale yüzeyleri tespit +
  3 karar (AskUserQuestion): koç↔öğrenci tahsilatı DOKUNMA · üyelik→iyzico checkout ·
  admin manuel activate-plan iç araç kalsın.
- **Kaldırıldı (platform havale/manuel):** `membership_offer_service` (get/set_havale_info,
  record_havale_claim, `_HAVALE_KEY`, public_view "havale") · `membership_public`
  `/havale-claim` ucu + HavaleInfo · `campaign_public`+`campaign_link_service` havale ·
  `payment.py`+schemas `PaymentLinkHavale` + link havale fallback ("ödeme geçici kapalı"
  olur, havale yok) · `admin_membership` `/havale` GET+POST ayar uçları. Frontend:
  /teacher/plan "Havale ile talep" → yalnız "Kartla Öde" · /membership/{token} → kart
  akışına yönlendirme (mevcut koç giriş→/teacher/plan · prospect→/signup/teacher?plan=;
  opsiyonel "bilgilerimi bırak" lead'i kaldı) · /payment/link havale fallback · /kampanya
  + admin Üyelik Teklifleri havale kartı · lib tip/api/hook havale.
- **KORUNDU (platform ödemesi DEĞİL):** `coach_billing` CoachPayment (koç KENDİ
  öğrencisinden Nakit/Havale/Diğer tahsilatı — iş modeli, dokunulmadı) · admin manuel
  `activate-plan` (iç override) · admin iyzico `payment-links` · `invoice` PaymentMethod
  enum (geçmiş kayıt).
- **Membership→kart nüansı:** iyzico checkout giriş yapmış kullanıcı (alıcı kimlik)
  gerektirir → public prospect doğrudan giremez; doğru bağlama = giriş/kayıt → /teacher/
  plan (mevcut Kartla Öde, iyzico init).
- **CANLI (2026-06-25):** kullanıcı prod `.env`'e CANLI anahtarları girdi
  (IYZICO_API_KEY/SECRET 32+32 · IYZICO_BASE_URL=https://api.iyzipay.com). Önce web yeni
  env ile yeniden başlatılıp **provider-status `available:true, sandbox:false`** doğrulandı
  (havale fallback hâlâ ağdayken = güvenlik ağı), SONRA kart-only kod deploy (git pull +
  DB yedek + web/worker/next rebuild, HEAD=bc42453). Canlı: provider available · healthz/
  pricing/anasayfa 200 · havale-claim+admin havale uçları 404.
- **Doğrulama:** tsc+eslint temiz · app boot 902 route · smoke membership_offer 18 ·
  whatsapp 13 · payment_iyzico 27 · campaign 17 · contact 13 · subscription 11+12 GREEN.
- **DERS:** API key/secret/IBAN sohbete YAZILMAZ → sunucu `.env` (kullanıcı SSH);
  ben yalnız maskeli uzunluk + provider-status ile doğrularım. Kart-only deploy'u
  provider available OLMADAN yapmak ödemeyi tümden durdurur → önce env+provider doğrula,
  SONRA kod deploy (güvenlik ağı havale hâlâ ağdayken keyleri test et).

## Iyzico ödeme sistemi (sandbox-first) — Paket Ö1-Ö3 (2026-05-28/29)

**Bağlam (kullanıcı):** Şirketsiz şahıs olarak Türkiye'de ödeme almanın yolları
tartışıldı (sanal POS / aggregator / TR Karekod). Karar: **Iyzico sandbox-first**
— SDK + akış kodlanır, gerçek üye işyeri başvurusu paralel; onay gelince tek
`.env` ile prod'a geçer.

- **Paket Ö1 — Iyzico backend altyapısı** (2026-05-28, **migration `p3q6u9v0u88o`**):
  - `requirements.txt` +`iyzipay>=1.0.46` (resmi SDK)
  - `config.py` +IYZICO_API_KEY/SECRET_KEY/BASE_URL + PAYMENT_CALLBACK_URL
  - **Migration `p3q6u9v0u88o`** (down_revision o2p5t7u8t77n): `payment_transactions`
    tablosu (user_id + provider + provider_reference + amount + currency + plan_code +
    cycle + status + status_reason + raw_request/response + completed_at). Additive.
  - Model `PaymentTransaction` + 6 status sabit + 3 provider sabit + status labels TR
  - `AuditAction` +4 (PAYMENT_INITIATED/SUCCEEDED/FAILED/REFUNDED) + TR etiket
  - `services/iyzico_service.py`: `is_provider_available` + `_iyzico_options`
    (HTTPSConnection scheme-strip) + `_iyzico_call_create`/`_call_retrieve`
    (mock-able helper'lar — smoke için monkeypatch) + `init_checkout`
    (Pydantic body → pricing.py'dan fiyat → conversation_id UUID → request body
    → SDK → paymentPageUrl + iyzico_token; pending tx satırı **ÖNCE** yaratılır,
    SDK fail olsa bile iz kalır) + `verify_callback` (token-bazlı arama —
    `provider_reference = iyzico_token` set edildi ki callback'te conversationId
    bağımlılığı olmasın; başarıda owner-aware `change_plan` reuse, kurum varsa
    institution, yoksa user; subscription_status/cycle/period_end doldurulur;
    cycle normalize **`annual` → `academic_year`** çünkü sistem geri kalanı bu
    standartı kullanır; PaymentLink varsa consumed işaretle) + `list_user_payments`
    + `PaymentError` (kod-mesaj-details)
  - `schemas/payment.py`: 6 Pydantic model
  - `routes/api_v2/payment.py`: **5 endpoint** — `GET /provider-status` (public,
    available + sandbox), `POST /init` (auth: koç/yön./süper admin),
    `POST /iyzico/callback` (auth YOK, Iyzico form-POST → 303 redirect),
    `GET /transactions/{id}` (sahibi), `GET /history`
  - `_require_teacher_or_admin` = TEACHER + INSTITUTION_ADMIN + **SUPER_ADMIN**
    (süper admin test için ödeme yapabilir + tx görüntüler; /history servis
    katmanında user_id ile filtrelenir)
  - `payment.py` import: payment router api_v2/__init__'e kayıt
  - Iyzico SDK email regex sıkı: `.local`/`.test`/`.example` reddediliyor →
    `noreply@etutkoc.com` fallback'i eklendi

- **Paket Ö2a — PaymentLink (kurumsal ödeme akışı)** (**migration `q4r7v0w1v99p`**):
  - Kurum self-serve ödeme yapamaz (Enterprise "Görüşme" fiyat); süper admin link
    oluşturur → kurum yöneticisine WhatsApp/email → linkten Iyzico checkout
  - **Migration `q4r7v0w1v99p`** (down_revision p3q6u9v0u88o): `payment_links`
    tablosu (token unique 64char hex + target_owner_type/id + plan_code + cycle +
    amount + description + status [active/consumed/expired/cancelled] +
    expires_at + consumed_at + consumed_by_user_id + consumed_transaction_id +
    created_by_admin_id) + `payment_transactions.payment_link_id` (FK SET NULL).
    Additive, downgrade'li.
  - Model `PaymentLink` + 4 status + 2 owner-type sabit + `is_usable` /
    `status_resolved` property (expires_at geçmişse otomatik 'expired')
  - Servis `payment_link_service.py`: `create_link` (token secrets.token_hex
    çakışma kontrolü 5 deneme + audit) + `get_by_token` + `list_links` (filter
    status/owner) + `cancel_link` (yalnız active) + `mark_consumed` (idempotent) +
    `expire_overdue_links` (cron için) + `can_user_pay_link` (süper admin daima
    OK, institution linki → o kurumun ADMIN'i, user linki → sahibi) +
    `PaymentLinkError`
  - `iyzico_service.init_checkout` genişletildi: `payment_link` opsiyonel
    parametresi (linkten gelirse fiyat/plan/cycle linkten alır, tx'e link_id bağlanır)
  - **5 yeni endpoint** (toplam 10 `/api/v2/payment/*`):
    - `POST /admin/links` (süper admin) — link oluştur
    - `GET /admin/links` (süper admin) — liste + status/owner filtre
    - `POST /admin/links/{id}/cancel` (süper admin)
    - `GET /link/{token}` (auth: yetkili) — link bilgisi (plan/tutar/kurum adı +
      can_pay flag + is_usable + requires_login)
    - `POST /link/{token}/checkout` (auth: yetkili) — iyzico init → paymentPageUrl

- **Paket Ö2b — Frontend (4 sayfa)**:
  - `lib/types/payment.ts` 12 tip · `lib/api/payment.ts` 5 fetcher + paymentKeys ·
    `lib/hooks/use-payment-mutations.ts` 4 hook (Create/CancelLink + InitCheckout +
    LinkCheckout) + 15 hata kodu TR etiketi
  - `/admin/payment-links` süper admin paneli (5 KPI + status filter chip-bar +
    tablo [Hedef · Paket · Tutar · Durum · Süre · İşlem]) + "Yeni Ödeme Linki"
    dialog (form-resetli `key`-remount; hedef tip radio Kurum/Bağımsız Koç + ID +
    plan select + cycle + tutar + açıklama + süre 1-365) + URL kopyala (DOM
    clipboard) + iptal confirm dialog · admin-shell "Sistem → Ödeme Linkleri"
    (Link2 ikon)
  - `/payment/result?tx=N` sonuç sayfası (SSR `apiServer.getTransaction(txId)`
    → succeeded/failed/pending 3 durum + büyük emoji + işlem özeti tablo +
    "Panele git"/"Tekrar dene" CTA; error param ise "Bir sorun oldu"). force-light.
    **Kontrast düzeltme**: koyu temada `bg-slate-50` üstüne `text-foreground` beyaza
    çözülüyordu → explicit slate-900/600 + Row toneCls (emerald/rose/amber tonlu)
  - `/payment/link/[token]` public sayfa (SSR + LinkInfo render; 4 durum:
    consumed → "Bu link daha önce ödendi" / not usable → "Artık ödenemez" /
    not can_pay → "Yetkili değilsiniz" / usable → büyük "Şimdi Öde" cyan buton →
    `useLinkCheckout` → window.location = paymentPageUrl). force-light + ShieldCheck +
    "Kart bilgileri ETÜTKOÇ'a iletilmez · PCI-DSS Iyzico 3DS" güvence notu
  - `/teacher/plan` "Üyeliği aktive et" dialog'a **"Kartla Öde"** butonu (provider
    available ise yan yana mevcut "Havale ile talep gönder" ile; sandbox modunda
    amber **TEST modu** rozeti)
  - `lib/role-home.ts` `safeReturnUrl` paylaşılan path'lere `/payment/*` eklendi
    (her rol ödeme sonucu/linki görür, returnUrl güvenli)
  - **Cycle çevirim bug (2026-05-29)**: `teacher-plan-client` "Kartla Öde" "Akademik
    Yıl" seçildiğinde `cycle="academic_year"` gönderiyordu, backend `monthly|annual`
    bekliyordu → 422. Düzeltme: dialog içinde `iyzicoCycle = cycle ===
    "academic_year" ? "annual" : "monthly"` çevirim. Manuel akış (subscription_
    request) `academic_year` kullanır, Iyzico `annual` — iki ayrı sözleşme. **KURAL**:
    bu çevirim yalnız kart akışında, manuel akışta DEĞİL.

- **Paket Ö3 — Smoke + Iyzico test kartlarıyla canlı doğrulama**:
  - `iyzico_service`'e mock-able helper'lar (`_iyzico_call_create`/`_retrieve`)
    ayrıldı → smoke'da monkeypatch ile gerçek Iyzico'ya istek yapmadan tüm
    state machine doğrulanır
  - `scripts/test_api_v2_payment_iyzico.py` — **27 senaryo** (auth + init mock +
    callback success/failure/idempotent + tx GET sahip/yabancı + history + admin
    link CRUD + public link can_pay yetki/yabancı + checkout başlat + callback →
    kurum aktive + link consumed + tek-kullanım koruması + cancel + cancel iki kez +
    SDK exception → 503 + **yıllık akış cycle=annual → subscription_cycle=
    academic_year normalize doğrulama**)
  - **Local canlı testler (kullanıcı tarayıcıdan):**
    - Demo Koç A `solo_pro` aylık 2.500 ₺ ödedi (Akbank `5528790000000008` + 3DS `a`)
      → callback OK → plan aktif (tx #7, daha sonra db'de gözden geçirme için).
      İlk denemede 503 `getaddrinfo failed` = geçici DNS — tekrar denemeyle düzeldi
    - Cycle bug fix sonrası `solo_unlimited` yıllık 75.000 ₺ akışı 422→200 OK
    - Kurum link akışı: admin → link → kurum yöneticisi login → linkten ödeme →
      kurum planı aktive + link consumed (yine başarılı)
  - **DB'de değişiklik (önemli)**: legacy `subscription_cycle="annual"` olan 1
    koç (`solo-b-yillik@g.com`) → `"academic_year"` migrate edildi (frontend
    "(aylık)" yazıyordu çünkü sistem `academic_year` standartını arıyordu)

**Sandbox kullanımı (kullanıcı önemli notu):**
- Iyzico Bireysel Üye İşyeri başvurusu **henüz yapılmadı** (Paket Ö4 — başvuru
  rehberi sonraya bırakıldı). Sandbox key ile test devam eder.
- Şu an gerçek müşteri YOK → canlıya alındığında para hareketi olmaz; sandbox
  test transaction'ları prod DB'sinde birikir (zararsız).
- Prod `.env` ayarları (kullanıcı dolduracak): `IYZICO_API_KEY` + `IYZICO_SECRET_KEY`
  + `IYZICO_BASE_URL=https://sandbox-api.iyzipay.com` + `APP_BASE_URL=https://
  rotam.etutkoc.com` + `PAYMENT_CALLBACK_URL=https://rotam.etutkoc.com/api/v2/
  payment/iyzico/callback`

## Ticari Pano — Owner-pattern + jargon + kapsamlı doğrulama (2026-05-28)

**Bağlam:** Kullanıcı `/admin/security-monitor/revenue`'da bir bug fark etti
("Yükselen 7" sayım var ama "Listeyi gör" 0 kayıt). Sebep: drill kurum-only
ama sayım kurum+koç. Kullanıcı "her şey hatasız" istedi → KAPSAMLI denetim.

**Bulgular (9 tutarsızlık) ve düzeltmeler:**

1. **Alt 4 KPI** `d.mrr` (kurum-only) → `d.mrr_combined` (segment-aware) — bağımsız
   seçince koç sayımları
2. **Plan Dağılımı tablosu** `d.plan_distribution` → `d.plan_dist_combined` —
   bağımsızda solo planları görünür; Hepsi'de 3 sütun (Toplam/Kurum/Koç)
3. **"Denemesi Bitmek Üzere" alt tablo** kaldırıldı (üst kart segment-aware
   zaten gösteriyor — tekrar)
4. **`drill_paying`** owner_type_filter parametresi (all/institution/user) +
   `_row_user(coach)` helper
5. **`drill_free`** owner_type_filter aynı şekilde
6. **`drill_trial_expired_unconverted`** owner_type_filter + 2 ayrı upgraded_set
   (institution + user)
7. **`drill_plan_members`** owner_type_filter — solo planlardaki koçlar görünür
8. **`health:*` drill** kurum-only KALIR (tenant_health sadece kurum metriği) +
   UI'da segment≠all iken "Terk Riski yalnız kurumlar — koç için Aksiyon Merkezi"
   açıklama notu
9. **`plan_change_summary` + `daily_plan_changes` + `trial_expired_unconverted`**
   sayım fonksiyonlarına owner_type_filter (önceden sayım segment-bağımsızdı;
   bu yüzden "sayım var drill 0" bug'ı çıkıyordu)

**Backend (`revenue_panel.py`):**
- `_row_user(coach, ...)` helper — bağımsız koç row üreticisi (owner_type='user',
  display_name, user_id/name/email)
- `_row` (kurum) + `_row_user` (koç) ikisi de **owner-pattern alanları**
  (`owner_type` / `owner_id` / `display_name`) doldurur (geri uyumluluk için
  `institution_id`/`name` korunur kurumda; koç row'unda 0/display)
- `DRILL_REGISTRY` tüm handler lambda imzaları `(db, segment="all")` →
  segment'i drill fonksiyonuna `owner_type_filter` olarak geçirir
- `drill_for_key` `segment="all"` parametresi
- `get_revenue_panel_data` segment-aware (sayım fonksiyonlarına geçirir)

**Şema (`schemas/admin.py`):**
- `RevenueDrillRow` polymorphic: `owner_type` + `owner_id` + `display_name` +
  opsiyonel `user_id/user_name/user_email` + plan değişimi alanları
  (`from_plan_label`/`to_plan_label`/`event_at`/`event_days_ago`/`event_note`)

**Endpoint (`routes/api_v2/admin.py`):**
- `/security-monitor/revenue/drill` `segment` query parametresi
  (pattern: `all|institution|user`)
- Owner-aware row mapping (institution_id/name → 0/"—" koç row'unda)
- `/security-monitor/revenue` dashboard endpoint'i `data = get_revenue_panel_data(
  db, segment=segment)` ile sayımları da segment-aware doldurur (önceki bug)

**Frontend (`admin-revenue-dashboard-client.tsx`):**
- `openDrill` her drill için seçili segment'i geçirir (eski "yalnız plan_change:*"
  yerine genel)
- Alt 4 KPI segment-aware başlık + alt etiket + sayım (mrr_combined kullanır)
- Plan Dağılımı tablosu segment-aware (Hepsi → 3 sütun; tek segment → 1 sütun)
- Üstte segment etiketi "Yalnız kurumlar / Yalnız bağımsız koçlar"
- **Mini sözlük** kutusu (Yeni kayıt/Yükselen/Düşüren/Net Büyüme/Duraklatma
  açıklamaları — CLAUDE.md jargon yasağı kuralı)
- `ChangeKpi` +`tooltip` prop (her KPI'da ⓘ hover açıklaması)
- Drill tablosu yeniden tasarlandı:
  - **Kim** sütunu: "Kurum" / "Koç" rozeti (mavi/violet) + isim + ID/email
  - **Plan Hareketi**: `from_plan_label → to_plan_label` (örn. "Solo Ücretsiz → Solo Başlangıç")
  - **Aylık** + **Ne zaman** (tarih + "N gün önce")
  - **360** linki owner-aware (`/admin/revenue/users/{id}` veya `/admin/revenue/institutions/{id}`)
- "{count} kurum" → "{count} kayıt" (kurum+koç karışık)

**Smoke (`test_api_v2_admin_revenue_dashboard.py`): 16 → 32 senaryo:**
- Tutarlılık testleri kritik: **26: `change_summary.upgrades == drill.count`
  her segment için** (kullanıcının yaşadığı bug'ın regresyon koruması)
- **27: `trial_expired_30d` sayım ≥ drill row sayısı** (drill upgrade etmiş
  olanları çıkarır)
- **28: tüm drill rows'ta owner-pattern alanları dolu** (frontend güvenli render)
- 17-25: kapsamlı drill × segment matrisi (paying/free/trial:expired/plan:solo_pro/
  etut_standart × all/institution/user)

**KURAL (kullanıcının vurgusu):** "Bu sayfanın üstünden kaç defa geçtik. Lütfen
bu sayfayı **hangi kod varsa testini yaparak** doğrulamanı istiyorum." → bundan
sonra büyük sayfa refactor'larında sayım↔drill tutarlılık testleri **zorunlu**.

## Signup intended_plan → post_trial_plan (2026-05-29)

**Bağlam (kullanıcı bildirdi):** `/pricing` "Solo Başlangıç 14 gün ücretsiz dene"
butonuna basıp `/signup/teacher?plan=solo_pro`'ya gidip kayıt olunca `/teacher/plan`
"MEVCUT PAKET: **14 Günlük Pro Deneme**" diyordu — kullanıcının seçtiği paket
DB'ye HİÇ yazılmıyordu, deneme bitince herkes solo_free'ye düşüyordu.

**Bug (3 katman):**
1. Backend `SignupTeacherIn` Pydantic modelinde `plan` alanı YOK → URL parametresi
   tamamen yutuluyor
2. `start_solo_trial` sabit `post_trial_plan = SOLO_FREE` (sabit kodlu)
3. Frontend signup formu body'ye `plan` parametresini eklemiyor

**Düzeltme (5 katman):**
1. `SignupTeacherIn` +`intended_plan: str | None` opsiyonel alanı
2. `plans.start_solo_trial` +`intended_plan` parametresi → geçerli `_VALID_SOLO_PAID_
   TIERS` ({solo_pro/elite/unlimited}) içinde ise `post_trial_plan = intended_plan`,
   değilse `solo_free`. PlanChangeHistory note'a "+ sonra: solo_pro" eklenir
3. Signup endpoint `start_solo_trial(intended_plan=payload.intended_plan)`
4. Frontend `signup-teacher-form` `intendedPlan` prop alır + body'ye
   `intended_plan: intendedPlan || undefined` ekler; `page.tsx`'te
   `<SignupTeacherForm intendedPlan={planParam} />`
5. `TeacherPlanResponse` +`post_trial_plan` +`post_trial_plan_label` (PLAN_CATALOG'dan
   etiket) +`post_trial_plan_credits` (PLAN_ALLOCATIONS'tan kredi)

**Frontend `/teacher/plan` ek iyileştirmeler:**
- Üst kart başlığı: `data.trial_active && data.post_trial_plan_label` ise
  "Solo Başlangıç — 14 gün ücretsiz deneme" (önceden "14 Günlük Pro Deneme")
- **Cyan bilgi notu** "Deneme bittiğinde Solo Başlangıç paketine geçmek için
  ödeme talep edilir. **Yapay zekâ kredin 1.500 / ay** olur" (post_trial_plan_credits
  ile vurgulu)
- "Paketini seç" kartı (SoloUpgradeCard) **post_trial_plan'i öncelikli seçer**
  (`intendedFromSignup || recommended_plan || ...`) — kullanıcının kasıtlı seçimi
  öne çıkar (öğrenci sayısı bazlı recommended yerine)

**Smoke (`test_api_v2_auth_p3.py`):** "signup happy" senaryosu zenginleştirildi —
`intended_plan='solo_pro'` body alanı + DB'de `u.post_trial_plan == 'solo_pro'`
doğrulaması (geçersiz tier → solo_free fallback; intended_plan boş → solo_free).

## Trial kredi tükenince ödemeye yönlendirme — Paket A (2026-05-29)

**Bağlam:** Trial koç AI özelliği çağırınca 50 kredi tüketince mesaj "5 saat sonra
tekrar deneyin" diyordu — yanıltıcı (krediler aylık yenilenir, çözüm ödeme).
Ayrıca frontend toast'ında "/teacher/plan'a git" yönlendirmesi yok, kredi göstergesi
yoktu.

**Backend (`credits.py`):**
- `check_credit_available` bağımsız koç için **'exhausted'** reason (eski
  'cooldown' yerine; bağımsız koç için "X saat sonra tekrar" anlamsız)
- `record_usage` balance=0 olduğunda `blocked_until` SET ETMEZ (eski kalıp
  yanlış mesaj kaynağıydı)
- `consume_credits` CreditBlocked mesajı `reason_messages` dict:
  - `exhausted`: "Bu ay için yapay zekâ kredin bitti. Paketini yükselterek
    kesintisiz devam edebilirsin."
- `PLAN_ALLOCATIONS` legacy `starter`/`professional` kaldırıldı (PLAN_CATALOG'da
  YOK, hiç kullanılmıyor). `free` defensive fallback olarak KALDI (DB'de 140
  non-teacher User satırı var)

**Backend (`teacher.py`):**
- `_ai_credit_exhausted_error(user, message)` modül-seviyesi helper — 402 detail'a
  `details.upgrade_url` + `upgrade_to_plan` + `upgrade_to_plan_label`
  (`PLAN_CATALOG[post_trial_plan].label`) ekler
- 3 AI endpoint (parse-photo / parse-voice / coaching-insight) `except CreditBlocked`
  helper'a yönlendir

**Frontend:**
- `use-teacher-mutations.ts` `showCreditExhaustedToast(err)` — backend'in
  `details.upgrade_to_plan_label` + `upgrade_url`'i okur, Sonner `action` API'siyle
  "**Paketi al**" butonu (tıklayınca `window.location.href = upgradeUrl`).
  3 yerde basic toast'tan helper'a çevrildi.
- `TeacherPlanResponse` +`ai_credits_used` +`ai_credits_allocated`
- `/teacher/plan` `AiCreditMeter` componenti: emerald/amber/rose 3 renk ilerleme
  çubuğu + "**N kredi yalnız deneme süresine özeldir. Solo Başlangıç paketine
  geçtiğinde aylık 1.500 kredi (~30× daha fazla) tanımlanır**" karşılaştırma
  bilgisi (post_trial_plan_credits bazlı multiplier)

## Paket B — /teacher/plan Google Workspace tarzı detaylı kartlar (2026-05-29)

**Bağlam (kullanıcı, Google Workspace ekran görüntüsü paylaştı):** 3 paket
küçük tıklanabilir kutu yerine **büyük kartlar yan yana** + her kartta tier'a
özel özellik listesi + AI kredi vurgusu + CTA.

**Frontend (`teacher-plan-client.tsx`):**
- `TIER_DETAILS` const — solo_pro / solo_elite / solo_unlimited için 7/6/6 madde
  özellik listesi + aylık AI kredi + badge ("En popüler" → solo_elite)
- `SoloUpgradeCard` 3 büyük kart `lg:grid-cols-3`:
  - Plan adı + öğrenci kapasitesi + büyük fiyat (aylık/yıllık toggle)
  - **Cyan vurgulu** "Aylık yapay zekâ kredisi" kutusu (en görünür alan)
  - Tier-bazlı özellik listesi (alt tier'ın tüm özellikleri + bu tier'a özel)
  - CTA: aktif/seçili **"Bu pakete geç (öde)"** (cyan), diğer **"Bu paketi seç"**
    (beyaz) — buton metni sade (plan adı kart başlığında zaten büyük; "Solo
    Başlangıç paketine geç (öde)" kırpılıyordu, kullanıcı bildirdi)
- Üst rozetler:
  - **"Denemede açık"** (cyan, sağ üst) — kullanıcının post_trial_plan ile eşleşen
  - **"Sana uygun"** (amber, sağ üst) — öğrenci sayısına uygun ama denemeyle aynı değil
  - **"En popüler"** (amber, üst-orta) — solo_elite için kalıcı
- Alt mini-bilgi: seçili paketin kredi maliyet tablosu (sesli dikte 3, foto 5,
  içgörü 6 kredi başına)

**Aynı patern kurum tarafına da uygulandı** (`admin-institution-detail-client.tsx`):
- `INSTITUTION_TIER_DETAILS` const (institution_free / etut_standart / dershane_pro /
  enterprise için kredi + 5-6 özellik)
- PlanCard'ın "seçici" modunda 4 büyük kart `xl:grid-cols-4` (önceden 4 küçük
  kutu) — fiyat + kredi vurgusu + özellik + CTA
- "Aktif paket" (disabled) / "Bu pakete geç" (seçili, cyan) / "Bu paketi seç"

## Talepten Aktivasyona — tek dialog kurum onboarding (2026-05-29)

**Bağlam (kullanıcı):** Kurum bilgilendirme formundan sonra **8 manuel adım**
süper admin için (3 ayrı sayfa). "Bu süreç havada mı yoksa otomatik mi?" Karar:
**tek dialog'da** kurum + yönetici + ödeme linki + e-posta + contact_request close.

- Backend endpoint `POST /admin/contact-requests/{id}/onboard`:
  1. Kurum yarat (slug auto-gen + çakışmada `-N`)
  2. Kurum yöneticisi yarat (`INSTITUTION_ADMIN`, 14 karakter güçlü geçici şifre +
     `must_change=True` + `email_verified_at=now`)
  3. Ödeme linki yarat (`payment_link_service.create_link`, target=institution)
  4. **E-posta gönder** (`institution_onboarding.html`, yöneticiye giriş bilgileri +
     ödeme bağlantısı — opsiyonel `send_email` flag)
  5. ContactRequest `status=closed` + admin_note'a izleme satırı ("Onboarding tamam —
     kurum #N (ad), yönetici #M (email), ödeme linki #K (X ₺)")
  6. Audit: `INSTITUTION_CREATE` + `USER_CREATE` `from_contact_request=N`
- Şema: `OnboardInstitutionBody` (institution_name + slug + plan + admin_full_name +
  admin_email + payment_amount + payment_cycle + payment_description +
  payment_expires_in_days + send_email) → `OnboardInstitutionResult` (geçici şifre +
  link URL + email_sent + message)
- E-posta template `institution_onboarding.html` — hoş geldiniz + cyan "Şimdi Öde —
  3DS" CTA + giriş bilgileri kutusu (geçici şifre amber vurgulu)
- Frontend `OnboardDialog` (admin-contact-requests-client):
  - ContactRow'a 2. buton: "🚀 Kurum Aç + Aktive Et" (yalnız
    `status != closed && !linked_institution_id && !linked_user_id` iken)
  - Dialog 3 bölüm: Kurum (ad + plan) + Yönetici (ad + email) + Ödeme linki
    (tutar + cycle + açıklama + süre) + "Otomatik e-posta gönder" checkbox
  - Form **contact_request'tan ön-doldurulur** (ad/email/kurum adı)
  - **Plan/cycle değişince tutar otomatik güncellenir** (`PLAN_DEFAULT_AMOUNTS`:
    etut_standart 10K / dershane_pro 30K; yıllık = aylık × 10). Süper admin
    yine manuel override yapabilir (özel pazarlık) — kullanıcı bug bildirimi
    sonrası eklendi (önceden dershane_pro seçilse bile etut_standart fiyatı
    kalıyordu)
  - Başarı paneli: geçici şifre + URL **kopyalanabilir** + "E-posta gönderildi"
    (yeşil) veya "Elden ilet" (amber) durumu + "Kurum sayfasına git" CTA
- `useOnboardInstitution` hook (use-admin-mutations'a eklendi)

**KURAL (kullanıcı vurgusu):** Bir alan/durum değişince etkilenen tüm yüzeyler
aynı commit'te güncellenir — bu durumda PaymentLink tablosundaki yanlış tutar
(önceki bug'lı testte 10K kayıt) ürün hatası DEĞİL, akışın yeniden test edilebilir
durumda olduğu için temizleme kullanıcıya bırakıldı.

## Veli paneli + haftalık mail + mobil giriş (2026-05-29)

**Bağlam (kullanıcı 3 iş):**
1. Veli haftalık mail sadece gün + toplam test sayısı gösteriyor → günlük detay +
   son deneme netleri eklenmeli
2. Veli panel ana sayfada deneme bilgisi yok
3. Anasayfa mobil görünümünde "Giriş" butonu görünmüyor

- **Veli paneli son deneme kartı**:
  - Backend `ParentChildSummary` +5 alan (`latest_exam_title`/`date`/`net`/
    `section`/`count`)
  - `/parent/dashboard` endpoint: her çocuk için tek sorguda toplam sayım
    + en son ExamResult (`exam_date desc + created_at desc`)
  - Frontend `parent-dashboard-client` ChildCard'a petrol mavisi tonlu "Son Deneme"
    bölümü: deneme adı + sınav türü rozeti (LGS/TYT/AYT/YDT) + büyük net +
    tarih + sağ üst "toplam N deneme" rozeti; hiç deneme yoksa bölüm görünmez
- **Veli haftalık rapor maili zenginleştirildi**:
  - `notification_producers.py` 2 yeni helper:
    - `_build_daily_breakdown(student_id, week_start, week_end)` — 7 gün için
      her görev: kitap + bölüm + `planned_count/completed_count` + günlük toplam
      (Pzt/Sal/.../Paz; boş günler dahil)
    - `_get_latest_exam(student_id, since_days=7)` — son 7g girilen ExamResult
      (title, date, net, correct/wrong/blank, section)
  - `produce_weekly_report` payload'a `daily_breakdown` + `latest_exam` eklendi
  - Template `parent_weekly_report.html` zenginleştirildi:
    - **"Günlük Program" tablosu** — 7 gün × kitap × bölüm × `15/20 soru`
      (tamamlanan emerald, eksik slate); günlük toplam sağ alt
    - **"Son Deneme" cyan kutu** — başlık + sınav türü + tarih + büyük net +
      doğru/yanlış/boş kırılımı
  - **Bug fix**: Jinja2'de `items` rezerve adı `dict.items()` ile çakışıyordu →
    producer'da `rows` adı kullanıldı (template + helper güncellendi)
- **Mobil ana sayfa "Giriş" butonu** (`landing-client.tsx`):
  - Header: eski `hidden ... sm:inline` class'ı kaldırıldı → mobilde de görünür
    ("Giriş" cyan-border, "Ücretsiz Dene" cyan-dolu yan yana)
  - StickyMobileCta: "Giriş" küçük border buton + "Ücretsiz Dene" ana buton

**KURAL (yeni — Jinja2 template adlandırma):** Jinja2'de `dict.items()` /
`dict.keys()` / `dict.values()` built-in metotları **iterate edilemez** — yani
template'de `{% for x in obj.items %}` ile çakışırsa "object is not iterable"
hatası verir. Producer/ctx'lerde rezerve dict-metodlarıyla aynı isim
kullanılmamalı (örn. `items` yerine `rows` veya `entries`).

## "Diğer"/etkinlik görevleri tamamlamaya sayılır + Veliye-duyur önizleme (2026-06-01)

**Bağlam (kullanıcı, student 12 Pazar):** 7 görev (3 TEST=8 soru + 4 OTHER), 2 OTHER
"tamam" ama manşet **%0**. Kök neden: gün/hafta `pct` **tamamen soru-bazlıydı**
(`completed_count/planned_count`); kalemsiz "Diğer" görevler `planned=0` → %'ye hiç
girmiyordu (2026-05-24 "etkinlik soru %'sine girmez" kararının revizyonu).
- **Karar (kullanıcı onayı): iki ayrı metrik.** (1) **Soru hacmi** ("8 test") yalnız
  sayısal görevlerden — analitik/risk/veli soru tablosu bunu kullanmaya DEVAM eder
  (Diğer'e sayı uydurma yok). (2) **Görev tamamlama** (manşet %) = her görev 1 birim;
  COMPLETED→1.0, sayısal görev→çözülen/planlanan, kalemsiz etkinlik tamamsa→1 değilse→0.
  Manşet artık "%0" yerine "%29" (2/7) gösterir.
- Backend: `teacher.py` `_task_completion_fraction` + gün/hafta `pct` görev-bazlı
  (planned/completed soru olarak KORUNDU — print özeti + "8 test" değişmez).
- **Print bug:** `program/print` `DayBlock` `t.items.map` ile satır üretiyordu →
  kalemsiz görevlerin items'i boş → **print'te görünmüyordu**. `ActivityTaskRow`
  eklendi (başlık + tip + "yapıldı ✓").
- **Veli içeriği zaten doğru:** `parent_new_program.html` rows boşsa task.title'ı
  render ediyor → Diğer görevler veli mailinde ZATEN var (değişiklik gerekmedi).
- **Veliye-duyur ÖNİZLEME (yeni):** `GET /teacher/students/{id}/program/parent-preview`
  (salt-okuma, bildirim YOK) — veli mailinin `_build_daily_breakdown`'unu + yayınlanmış
  görev sayısı + alıcı veli (24s dedup) döndürür. Frontend `ParentAnnounceDialog`
  ("Veliye duyur" artık `window.confirm` yerine önizleme modalı açar: gün gün program
  [Diğer dahil, is_activity rozetli] + alıcılar + taslak uyarısı → "Velilere gönder").
- Smoke `test_api_v2_teacher_week_activity_pct.py` 2/2 (görev-pct + önizleme). Regresyon:
  weekly_plan 14 + itemless 10 + teacher_read 12. tsc/eslint temiz. **NOT:** smoke'ta
  id-reuse orphan TaskBookItem temizliği gerekti (ürün hatası değil).

## Veli önizleme ders-grubu + "test" birimi + deneme düzenleme + net grafiği tür-ayrımı (2026-06-01)

Kullanıcı önizlemeyi inceledi, 4 düzeltme + 1 ek özellik:
- **Birim "soru" → "test"**: `_build_daily_breakdown` + `parent_new_program.html` +
  önizleme modalı artık "test" der (sistemin birimi = atanan test sayısı; hafta
  görünümü zaten "test" diyordu).
- **Ders bazlı gruplama**: `_build_daily_breakdown` her güne `subject_groups`
  (Subject.order'lı: ders başlığı → konu/bölüm + test) + `activities` (kalemsiz
  Diğer/Video/Özet/Tekrar) ekler (`tasks` düz yapı weekly_report için korundu).
  Mail + önizleme bunu render eder.
- **Veliye-duyur önizlemesine denemeler eklendi** (`recent_exams`, son 90g).
  **Deneme paylaşım kararı (kullanıcı 2026-06-01):** denemeler veliyle paylaşılır,
  **varsayılan AÇIK** (veli paneli + veli mailleri + önizleme); öğrenci isterse
  kapatabilmeli (opt-out toggle) — **bu toggle migration'lı AYRI iş, henüz YOK**
  ([[feedback-holistic-change-propagation]] · `student-exams-panel` notu hâlâ
  "veliyle paylaşılmaz" diyor → toggle yapılınca düzeltilecek; şu an çelişkili).
- **Deneme DÜZENLEME** (yeni — kullanıcı "hatalı girişlerde düzenle olmalı"):
  `_validate_and_compute_exam` helper'ı create+update ortak; yeni `POST
  /api/v2/teacher/exams/{id}` (sahiplik 404, created_by_id değişmez, net yeniden
  hesap). Frontend `student-exams-panel` her deneme kartına Pencil "Düzenle" +
  `ExamForm editRow` (prefill) + `useUpdateExam`. Smoke exams 18/18 (8b/8c update).
- **Net Gelişimi grafiği tür-ayrımı** (kullanıcı: TYT+AYT aynı grafikte yanlış):
  farklı sınav türleri farklı ölçek (TYT/120·AYT/80·LGS) → tek çizgide karıştırma
  YOK. `NetTrendChart` türe göre filtreler + tür seçici (native select, en çok
  denemesi olan tür varsayılan); hiçbir türde ≥2 deneme yoksa grafik gizli.
- Smoke: exams 18/18 + week_activity_pct 2/2 (önizleme grouped yapıya güncellendi) +
  weekly_plan 14 + itemless 10. tsc/eslint temiz.

## Mail worker-rebuild dersi + e-posta logosu PNG + buton hover + deneme özet/grafik per-tür (2026-06-01)

Kullanıcı gönderilen maili inceledi, 4 sorun:
- **KRİTİK deploy dersi:** Gönderilen mail eski "soru"/grupsuz formattaydı çünkü
  e-postaları render eden **worker container'ı yeniden oluşturulmamıştı** —
  `docker compose up -d --build web next` yapmıştım ama **worker** (dispatcher,
  e-posta/cron render eder) eski image'ı çalıştırıyordu. **KURAL: backend kodu/
  şablon/cron/producer değişince deploy'a `worker` DAHİL** (`up -d --build web
  worker next`). redeploy.sh (argümansız `up -d --build`) zaten hepsini kapsar;
  hedefli deploy'da worker'ı atlamak yasak. Worker recreate → mail ders-gruplu + "test".
- **E-posta logosu PNG (SVG değil):** Mailde logo kırık görünüyordu — `etutkoc-mark.svg`
  SVG; **e-posta istemcileri (Gmail/Outlook) SVG'yi engeller**. Çözüm: `apple-touch-icon.png`
  (şeffaf amblem) → `web/public/etutkoc-mark.png` kopyalandı; 12 e-posta şablonunda
  SVG img → PNG img; Caddy `/etutkoc-mark.png` rotası. **KURAL: e-posta logosu daima
  PNG (SVG e-postada görünmez).**
- **"Veliye duyur" buton hover kontrastı:** `variant="outline"` + `bg-emerald-50` →
  outline'ın `hover:text-accent-foreground`'u koyu temada metni açık renge çevirip
  açık-yeşil zeminde okunmaz yapıyordu. Solid `bg-emerald-600 text-white
  hover:bg-emerald-700 hover:text-white` (variant kaldırıldı).
- **Deneme özet şeridi + grafik per-tür:** Özet (Ortalama/En İyi/Son Net) + grafik
  farklı sınav türlerini (TYT net/120 · AYT net/80) **birleştiriyordu** — kıyaslanamaz.
  Tür seçimi `StudentExamsPanel` seviyesine taşındı (native select, en çok denemesi
  olan tür varsayılan); SummaryStrip + NetTrendChart artık seçili **tek türe** göre
  hesaplar. Deneme listesi (her satır kendi tür rozetiyle) tüm türleri gösterir.
- tsc/eslint temiz. Deploy: web + worker + next rebuild + Caddy `restart proxy`.

## Risk göstergesi onboarding-grace (low_completion + consecutive_empty) + WhatsApp seed prod boşluğu (2026-06-01)

- **Risk yanlış-pozitif (kullanıcı: /institution/at-risk):** Dün eklenen öğrenci
  "14 gün üst üste boş" + "düşük haftalık tamamlama" alıyordu. `risk_analysis`'te
  bu iki gösterge onboarding-grace'siz: `low_completion` yalnız `planned>0 & rate<40`
  bakıyordu; `consecutive_empty` bugünden 14 gün geriye sayıp hesap-öncesi günleri
  de "boş" sayıyordu. Düzeltme (`ONBOARDING_GRACE_DAYS=3`): low_completion'a hesap
  yaşı gate; consecutive_empty `empty_days = min(empty, account_age)` (1 günlük hesap
  "14 boş" olamaz; ≥3 eşiğiyle yeni öğrenci otomatik korunur). no_program zaten
  3-gün grace'liydi → sabite bağlandı. (2026-05-23 no_login/no_program grace'inin
  performans göstergelerine genişletilmesi.) Smoke `test_risk_onboarding_grace.py`
  6/6 (yeni→sessiz, 6g→sinyal var + boş gün hesap yaşıyla sınırlı). Regresyon:
  institution_p2 19 + action_center 8 + alert_correctness 9/9 (ilk koşu 7/9 idi =
  id-reuse kontaminasyonu, tekrar koşunca 9/9 — fix age≥3'te no-op).
- **WhatsApp şablonları prod'da boştu (kullanıcı sordu):** localde 35 şablon var,
  canlıda `/admin/whatsapp-templates` boş. Sebep: `seed_whatsapp_templates.py`
  (35 idempotent şablon) **prod'da hiç çalışmamış** — `start.sh` yalnız
  init_db + seed + seed_landing_cards çalıştırıyordu; whatsapp seed YOKtu. Migration
  tabloyu kurmuş ama doldurmamış (count=0). Düzeltme: `start.sh`'e
  `python -m scripts.seed_whatsapp_templates || true` eklendi (web start'ında seed) +
  prod'da elle çalıştırıldı. **KURAL: seed'le dolan her tablo start.sh'te olmalı
  (yoksa prod'da boş kalır).**

## Bireysel (tekli) WhatsApp gönderimi — kurum yöneticisi + süper admin (2026-06-01)

**Bağlam (kullanıcı):** `/teacher/bulk-wa`'da sidebar'da yalnız "Toplu WhatsApp"
görünüyor, bireysel mesaj linki yok sandı. **Denetim:** WhatsApp mesajlaşma
erişimi — Öğretmen: toplu (sidebar) + bireysel (BAĞLAM-içi: öğrenci detayı
"WA Gönder" + Veliler sekmesi WhatsApp ikonu, `WaSendDialog`). Kurum yöneticisi:
toplu var, bireysel YOK. Süper admin: yalnız Şablonlar + Audit. Veli/Öğrenci:
yok (alıcı, backend 403 — doğru). Tasarım: toplu = sidebar (hedefsiz sihirbaz);
bireysel = kişinin kendi sayfasından (hedef gerekir) — öğretmende eksik değil.
- **Kullanıcı kararı: kurum yöneticisi + süper admin'e bireysel ekle.** Backend
  zaten izinli (`/messaging/wa-link` + templates + target; P4 K4/K5 testleri).
  Frontend-only: `teacher-card-client` (kurum öğretmen detayı → "WA Gönder",
  hedef=öğretmen, kategori=kurum_ogretmen) + `admin-user-detail-client` (kullanıcı
  detayı → "WA Gönder", `!is_self`, kategori=admin_yonetici). Paylaşılan
  `WaSendDialog` reuse. tsc/eslint temiz, next rebuild.
- **NOT:** SMS soft-mod'da olduğu için (telefon doğrulama kapalı) gerçek gönderim
  hedefin doğrulanmış telefonu olunca çalışır; UI hazır, davranış tutarlı (toplu
  ve öğretmen bireyseli de aynı kısıta tabi).

## BFF-JWT impersonation (sahte oturum) — Next.js panellerinde çalışır hale getirildi (2026-06-01)

**Bağlam (kullanıcı):** `/admin/users/{id}` "Sahte Oturum" çalışmıyordu — gerekçe
textarea'sı beyaz-üstüne-beyaz + "başlat"a basınca /admin'de kalıyordu. Kök neden:
impersonation ucu yalnız **Jinja `request.session`'a** yazıyordu; paneller artık
Next.js + **BFF JWT cookie** ile auth → Jinja session ölü, cookie hâlâ süper admin
→ hedef panele gidince rol-koruması /admin'e geri atıyordu.
- **Textarea kontrastı:** `text-slate-900 placeholder:text-slate-400` (commit `8fca02e`, deploy).
- **BFF-JWT impersonation (onaylı):** JWT'ye opsiyonel **`imp_by`** claim'i
  (`jwt_auth`: `_make_token`/issue_*/`issue_token_pair` + `TokenPayload.impersonator_id`
  + decode; imp_by None iken token birebir aynı → api_v1 47/47 korundu).
  - `POST /users/{id}/impersonate`: Jinja session'a EK olarak **hedef için
    access+refresh cookie** basar (`imp_by=admin.id`, yeni ActiveSession sid) →
    Next.js paneli hedefi görür. redirect = hedef roleHome.
  - `POST /impersonate/end` (auth dep YOK): aktif access cookie'sinin `imp_by`'ından
    admin'i çözer → Impersonation kaydını kapat + imp ActiveSession terminate +
    **admin'in normal cookie'sini** geri bas (imp_by YOK) → /admin.
  - `POST /auth/refresh`: imp_by'ı taşır (impersonation refresh'te kopmaz).
  - `GET /auth/impersonation-status` (auth dep YOK): access cookie imp_by'ından
    {active, impersonator_name, target_name} → banner besler.
  - Frontend: `components/impersonation-banner.tsx` (mor üst bant + "Admin'e dön" →
    end → redirect) — teacher/institution/parent/student shell'lerine eklendi
    (admin'e impersonate edilemez). admin-user-detail ImpersonateCard zaten redirect
    yapıyordu (artık cookie hedefe geçtiği için panel hedefi gösterir).
  - **Güvenlik:** kendini/diğer süper admini/pasifi impersonate yasağı korunur;
    audit (IMPERSONATE_START/END) korunur; admin'in tarayıcısına hedef JWT'si
    basılır (impersonation'ın doğası) — imp_by + audit ile izlenir, "Admin'e dön"le
    geri alınır.
  - Smoke `test_api_v2_impersonation_bff.py` **8/8** (impersonate→cookie swap→
    /auth/me hedef→status active→refresh korur→end→admin restore→status pasif) +
    admin_users **26/26** (18b end-restore eklendi — cookie-swap yeni davranışı) +
    api_v1 47 + auth 14 + auth_p1 10 + me 13. Migration YOK. Deploy: web+worker+next.

## GÖREV / TEST / DENEME standardizasyonu — sistem geneli (2026-06-02)

**Bağlam (kullanıcı, Image 31):** Hafta görünümü "3 görev · 122 test" diyordu =
2 integral test + **120 (TYT Genel Deneme'nin 120 sorusu test sayılmış)**.
"deneme ayrı test ayrı diğer ayrı görev ayrı olmalı, her yerde eksik olmasın."

**Standart (kullanıcı, kilitli):** GÖREV = Task; programa eklenen her madde 1
görev (bir görevde çok kalem OLMAZ). TEST = görev içi soru hacmi (ikincil).
DENEME ≠ TEST. 4 kategori: test (soru bankası) · deneme (branş/genel deneme
kitabı) · tam_deneme (kitapsız "Deneme") · etkinlik (video/özet/tekrar/diğer).

- **Çekirdek:** `app/services/gorev_stats.py` — `classify_gorev`/`gorev_done`/
  `summarize` (görev/test/deneme/etkinlik AYRI) + public `is_test_book`/
  `item_is_test`. `scripts/test_gorev_stats.py` 27/27. TEK MERKEZ — tüm panel/
  mail/yazdırma buradan beslenir.
- **Panel yüzeyleri (program-bazlı, hepsi görev manşet + test/deneme ayrı):**
  Koç 360/gün/hafta/liste/pano · Öğrenci gün/hafta · Veli pano/detay/hafta.
  Manşet = "X/Y görev (%Z)"; test = yalnız soru bankası; deneme + etkinlik ayrı.
- **Mail (Faz B):** `_build_daily_breakdown` görev-bazlı (test ders-grupları +
  **Denemeler AYRI başlık** + Etkinlikler ayrı). `parent_weekly_report` +
  `parent_new_program` şablonları görev manşet. "Veliye duyur" önizlemesi mail
  ile birebir. **Jinja FIX:** grup dict anahtarı `items`→`rows` (`.items()`
  metoduna çözülüp "object is not iterable" veriyordu — CLAUDE.md kuralı).
- **Faz C:** Veli **günlük özet maili KALDIRILDI** (haftalık rapor yeter).
  Boş-gün uyarısı GÖREV-bazlı (`_is_empty_day`: hiç görev bitmemiş + hiç
  test/deneme ilerlemesi yok → kısmi çalışan AKTİF) + eşik **3 üst üste** +
  3g cooldown. `test_daily_empty_threshold.py` 6/6.
- **Yüzey 9 — envanter/projeksiyon/DNA/Hız test-only:** `analytics`
  `inventory_totals`/`daily_completed_series`/`daily_planned_series`/`recent_rate`
  +`tests_only` param (varsayılan False → engagement/consistency/UYARILAR
  DEĞİŞMEZ). **`compute_projection` İZOLE** — envanter+seri+rate hepsi
  tests_only=True → projeksiyon yalnız TEST envanteri (deneme girmez).
  `student_snapshot.rate_7d/30d` ("test/gün hız") + DNA "Tamamlama" (study_dna
  additive `display_*`, total_*/burnout'a DOKUNMADAN) + Kaynak Durumu grand-total
  + öğretmen Analitik 30g trend + veli 30g trend + seans prefill hızı → test-only.
  **`test_projection_tests_only.py` 10/10** (soru bankası 100 + genel deneme 40 →
  projeksiyon total=100/completed=30/kalan=70, rate deneme'siz).
- **Regresyon (hepsi GREEN):** gorev_stats 27 · projection_iso 10 · daily_empty 6 ·
  student_read 11 · student_mut 12 · teacher_read 12 · teacher_students 14 ·
  alert_correctness 9 · risk_grace 6 · compliance 10 · parent 20 · tenant 29 +
  şablon render doğrulaması. tsc/eslint temiz. 8 deploy (web/worker/next), canlı.
- **Test-data fix:** `simulate_alert_correctness.py` `Book type="test"` (geçersiz
  enum string) → `BookType.SORU_BANKASI`; `joinedload(book)` artık enum
  deserialize ettiğinden patlıyordu (production değil test bug'ı).
- **KALAN (opsiyonel, düşük öncelik):** `subject_breakdown` (ders dağılımı) **görüntüleme**
  yüzeylerinde hâlâ deneme kitaplarını derse katar (kurulu davranış; kullanıcı
  flag'lemedi). UYARI yolu artık test-only (aşağıda 2026-06-06 fix). Program
  **print** gün/toplam "Planlanan X" soru-bazlı (görev satırları doğru listelenir).
  İstenirse ders-dağılımı görüntülemesi de ayrı pakette test-only yapılır.
- **KURAL:** Yeni bir "test" sayımı/gösterimi eklenince `gorev_stats` (görev/test
  ayrımı) veya `analytics tests_only=True` kullanılır — deneme sorularını "test"
  saymak YASAK. Engagement/consistency/uyarı metrikleri tests_only=False kalır
  (deneme aktivitesi engagement'a sayılır).

### "Bu hafta" → "Son 7 gün" + KONTROL MEKANİZMASI (2026-06-02)

- **Bug (kullanıcı Image 32):** Yeni başlayan haftada (Pzt/Sal) veli kartı "BU
  HAFTA %89" gösteriyordu. Kök neden: **özet kartlar** (`week_stats_for` +
  360/pano görev_week) **rolling son-7-gün** penceresi kullanıyor → geçen
  haftanın bitmiş günleri sızıyor. Etiket yanıltıcıydı.
- **Düzeltme (frontend-only):** ÖZET KARTLARDA "Bu hafta" → **"Son 7 gün"** (veli
  pano + koç pano + veli detay + koç 360 StatusSummary/GorevBreakdownCard). Veli
  pano "Son 7 Gün Oran" → "Tutturma". **HAFTA SAYFALARI (`/week`) DOKUNULMADI** —
  onlar `get_active_program` haftasını kullanıyor ("bu hafta" orada doğru).
- **KONTROL MEKANİZMASI** (kullanıcı: "yok mu bir kontrol mekanizması"):
  `scripts/test_card_consistency.py` (23) — golden senaryo, 5 yüzey AYNI+DOĞRU
  sayı + deneme≠test invariant + projeksiyon izolasyon. `scripts/run_gorev_checks.py`
  — **tek komut** 5 kontrol (68/68). **KURAL: görev/test/deneme veya kart-sayısı
  mantığı değişince `python scripts/run_gorev_checks.py` koş — kırmızıysa kartlar
  bozulmuştur.**

## Hızlı düzeltmeler + 2 yeni özellik (2026-06-03)

- **KRİTİK — öğrenci ilk girişte şifre yenileme PAS GEÇİYORDU:** `teacher_create_
  student_v2` `must_change_password=True` set ETMİYORDU (admin + kurum-öğretmeni
  set ediyordu — yalnız öğrenci eksikti) → login yanıtı must_change=False → /password/
  change'e yönlenmiyordu. Düzeltildi + etkilenen (hiç giriş yapmamış) öğrenciler
  backfill ile must_change=True yapıldı. Diğer roller temizdi.
- **"Bugün hiç tik yapmadı" uyarısı görev-bazlı oldu:** eskiden test hacmine
  (`today_stats.planned>0`) bağlıydı → etkinlik-only gün (soru=0) yeşil kalıyordu.
  Artık `gorev_total>0 & gorev_done==0` (etkinlik dahil, draft hariç). Test
  `test_today_no_tick_gorev.py` 4/4.
- **"Plan"→"Haftalık Program"** etiketi (hedef /day korundu).
- **Atanmamış kitap uyarısı:** book detail'da öğrenci atanmamışsa amber banner +
  "Öğrenci ata" (tüm sekmelerde) + Öğrenciler sekmesinde kaydedilmemiş seçim
  uyarısı. ("AI bölüm sonrası tik kalkıyor" → REPRO: server atamayı KORUYOR;
  sorun kaydetmeden sekme değiştirme.)
- **Bölüm "öğrenci zaten çözmüştü" (geçmiş yıl ayıklama):** öğrenci kitap panelinde
  her bölüme inline "çözülmüş test" girişi → completed_count set, kalan düşer,
  programda atanmaz. POST `/students/{id}/books/{sb_id}/sections/{sec_id}/completed`.
  `test_section_completed_baseline.py` 7/7.
- **Tüm panellerde "Hesabım & Şifre" linki** (→ /me/account): teacher/institution
  (sidebar+mobil) · parent (nav) · student (header+mobil). /me/account hiçbir
  panelden linklenmemişti → şifre değiştirilemiyordu.
- **YENİ ÖZELLİK 1 — kalemsiz göreve çözülen soru** (migration `y2z5e8f9e33y`:
  `tasks.solved_count`): "olmayan kitaptan test" gibi etkinlik/diğer göreve öğrenci
  çözdüğü soruyu girer → **test hacmine** sayılır (kategori etkinlik KALIR, manşet
  görev %'sini etkilemez). complete_task_v2 solved_count; gorev_stats etkinlik
  solved→test_completed. Öğrenci task-card inline "+ Çözdüğüm soru", koç day-board
  "öğrenci N soru çözdü". `test_itemless_solved_count.py` 10/10.
- **YENİ ÖZELLİK 2 — günlük düşünce notu** (migration `z3a6f9g0f44z`:
  `student_day_notes`, student_id+date unique): /student/day'de buton-suz, 700ms
  debounce autosave textarea ("Günün notu"); tekrar açınca devam; koç day-board'da
  cyan salt-okuma kartında görür. PUT `/student/day-note`. `test_day_note.py` 7/7.
- **Migration head = `z3a6f9g0f44z`.** Tümü additive + downgrade'li; prod'da
  start.sh `upgrade head` ile uygulanır.

## Haftalık plan editörü — Katman 1/2/3 (2026-06-03, CANLI)

**Bağlam (kullanıcı, Image 36/37):** program oluştururken 3 acı: (1) birbirine
bağlı testleri (mat öğretmeni 10 test / özel ders sistem-dışı sorular) günlere
yayarken "kaç verdim, kaç kaldı" elle sayılıyor; (2) tek-açık akordeon → bir günü
planlarken diğer günleri görememe; (3) gün içi görevler ders bazlı gruplanmıyor
(araya başka ders giriyor). Kullanıcı önce ciddi analiz istedi → onayladı:
**Katman 1+2 önce**, blok takibi için **hafif "serbest blok"** (Katman 3).

- **Katman 1 — gün içi ders gruplama** (`week-day-card`): `TaskList` görevleri
  ders grubuna göre sıralar (`subjectGroupedOrder`) + renkli `SubjectGroupHeader`;
  aynı dersin görevleri yan yana, araya ders girmez. Sürükle-bırak korunur
  (orderedIds yalnız görev seti değişince ders-gruplu yeniden kurulur). Render
  index-bazlı saf karşılaştırma (eslint immutability).
- **Katman 2 — Hafta Izgarası** (`week-grid.tsx`): 7 günü yan yana, hep görünür
  tek bakış (akordeonun üstünde). Ders gruplu + durum (✓/◐/☐) + sayı/birim;
  güne tıkla → o günün düzenleyicisi açılır + kaydırılır (`#day-{date}` +
  scroll-mt). `grid-cols-2 sm:4 lg:7`, katlanabilir.
- **Katman 3 — serbest iş bloğu** (**migration `a4b7g0h1g55a`**, additive):
  `coach_work_blocks` (coach/student/title/subject/total/unit/note/status) +
  `tasks.work_block_id` (nullable FK SET NULL). Backend `CoachWorkBlock` modeli +
  5 endpoint (list/create/update/archive/delete · owner-pattern 404) + görev
  oluşturmada opsiyonel `work_block_id` + serializer'a work_block_id/title/unit +
  dağıtılan/kalan agregasyonu (`_work_block_aggregates`). **Rezerv YOK** — sayaç.
  Smoke `test_api_v2_teacher_work_blocks.py` **19/19**.
  - Frontend: `WorkBlockPanel` (Kaynak Durumu üstünde — ilerleme + oluştur/
    düzenle/arşivle/sil) + add-task-form **"Blok" tipi** (blok seç/oluştur + bu
    güne kaç → bağlı görev) + week-day-card/week-grid blok görevini ders grubuna
    sokar (başlık `{Ders}·{etiket}` parse) + **violet "Blok" rozeti** + blok
    birimi (deneme'den ayrı).
- **Migration head = `a4b7g0h1g55a`.** Doğrulandı (prod: kolon+tablo var,
  endpoint 401, site 200). Commit `5f73dbf`, web/worker/next rebuild + DB yedek.
- **Blok = ETKİNLİK kararı** (kullanıcı 2026-06-03, commit `bae9360`): blok görevi
  istatistiklerde etkinlik sayılır — görev birimi (manşet % + "X/Y görev") ama
  TEST/DENEME hacmine GİRMEZ (blok kendi dağıtılan/kalan sayacıyla izlenir).
  `gorev_stats.classify_gorev`: `work_block_id` set → "etkinlik" (kitapsız kalem
  taşısa da tam_deneme SAYILMAZ); kitapsız gerçek deneme (work_block YOK) →
  tam_deneme korunur → panel/mail "Etkinlikler"e gider, "Denemeler"e karışmaz.
  `/day` + yazdırma: blok + kalemsiz etkinlik görevleri başlık parse ile DERSİNE
  gruplanır (editör/ızgara ile tutarlı) + birim work_block_unit. Tüm yüzeyler
  tutarlı. [[feedback-holistic-change-propagation]]

- **Periyot bölümleri + görev-adından ders eşleştirme** (2026-06-04, commit
  `9dfc091`, frontend-only):
  - **(A) Sabah/Öğle/Akşam:** günü periyotlu öğrencilerde (en az 1 görevde
    `period` dolu) editör (week-day-card) + Hafta Izgarası (week-grid) +
    yazdırma (print) periyot başlıkları gösterir; her periyot içinde dersler
    kendi arasında gruplanır. Görev eklenirken `PeriodChips` seçimi → anında o
    bölüme + ders grubuna. Periyotsuz günde yalnız ders gruplaması. Editörde
    `dayTaskOrder(tasks, subjects, usePeriods)` (periyot rank → ders ilk-görülme)
    + PeriodHeader/SubjectGroupHeader; drag grup-içi korunur (set/mod değişince
    yeniden kurulur).
  - **(B) Görev adından ders:** branş/genel deneme kitapsız → "Diğer"e düşüyordu;
    artık görev ADI taranır (`findSubjectInTitle`), bilinen ders adı geçiyorsa o
    derse girer (örn. "AYT Matematik Branş Denemesi" → Matematik, test görevleriyle
    AYNI `s{id}` grubunda BİRLEŞİR). " · " önekli (video/özet/tekrar/diğer/blok)
    görevler de tam-ad eşleşmesiyle (`findSubjectByExactName`) bilinen derse
    çözülür. week-board `getStudentAllSubjects`'i editör+ızgaraya geçirir; print
    server'da fetch eder. (Sınırlı: tam-ad substring eşleşmesi; "Türk Dili ve
    Edebiyatı" gibi uzun adlar branş başlığında geçmezse "Diğer" kalır.)

## WhatsApp Üyelik Teklifi (sigortam.net tarzı) — Paket 1 (2026-06-04, CANLI)

**Bağlam (kullanıcı):** sigortam.net'in WhatsApp'tan gönderdiği markalı teklif +
link → web akışı → satın alma deneyimini istedi. Görseller analiz edildi: akış =
WhatsApp İşletme mesajı (görsel+metin+buton) → **uygulama-içi tarayıcıda web
sayfası** → satın alma (saf sohbet-içi DEĞİL). **A/B çatalı** sunuldu:
- **A (şimdi, Meta onayı YOK):** Click-to-WhatsApp ile markalı link → web akışı.
- **B (sonra):** WhatsApp Cloud API + Meta Business doğrulama (mavi-tik gönderen).
**Kullanıcı kararı:** A'yı yap, sonra B. **Meta doğrulama + Iyzico canlı kart DA
kayıtlı işletme ister** (salt TC yetmez); kullanıcının işletmesi yok → A'da
tamamlama = **"talep → manuel aktive" + havale/EFT (kişisel IBAN, manuel onay)**.
WhatsApp Pay Türkiye'de YOK.

**Paket 1 — markalı sayfa + backend link üretimi** (**migration `b5c8f1g2f99w`**,
additive; head = `b5c8f1g2f99w`):
- `membership_offers` tablosu + `MembershipOffer` modeli (token, hedef koç,
  offer_type new|renewal, plan_code, cycle, amount[özel fiyat|null], title,
  message, status, completion[requested|havale_claimed], viewed/accepted/expires).
- `membership_offer_service`: create_offer (token) · public_view · record_request
  (ContactRequest source="membership_offer" + koç_id/hedef_kod → admin İletişim
  Talepleri'nde görüp activate-plan) · record_havale_claim · havale bilgisi
  (app_settings `membership_havale`).
- Public router `/membership/{token}` (login'siz): GET + /request + /havale-claim.
  Admin router `/admin/membership-offers` (_require_super_admin): create + havale
  GET/POST. `app/routes/api_v2/admin_membership.py` (admin'den `_require_super_admin`
  import eder). Smoke `test_api_v2_membership_offer.py` **15/15**.
- Frontend: `/membership/[token]` mobil-öncelikli markalı sayfa (force-light,
  ETÜTKOÇ logo, **OG meta** → WhatsApp link önizlemesinde logo) + plan/fiyat/
  özellik kartı + client actions (talep + havale IBAN/kopyala/ödedim). proxy
  public allowlist + Caddy `/membership/*` → next (restart proxy).
**Paket 2 — süper admin oluşturucu UI + havale ayarı** ✅ (2026-06-04, migration YOK):
- Backend: `/admin/membership-offers` GET list (son 100 + durum/completion +
  public_url) + plan-options (PLAN_CATALOG satılabilir planlar). create + havale
  P1'den.
- Frontend `/admin/membership-offers` (admin-shell "Ticari Pano → Üyelik Teklifleri
  (WhatsApp)"): havale/EFT ayar kartı + teklif oluşturucu (hedef koç ara/seç veya
  genel + yeni/yenileme + plan + döngü + özel fiyat + başlık/mesaj + süre → link
  kartı: kopyala + **WhatsApp'ta Aç** [wa.me mesaj+link hazır] + önizle) + son
  teklifler listesi (koç telefonu varsa doğrudan WhatsApp). Uçtan uca kullanılır:
  admin link üretir → WhatsApp'tan gönderir → koç markalı sayfada talep/havale →
  İletişim Talepleri → aktive. tsc/eslint temiz, canlı.
**Paket 3 — toplu / gruplu gönderim** ✅ (2026-06-04, migration YOK):
- Backend: `/admin/membership-offers` GET `/audience` (bağımsız koç hedef grupları:
  ücretsiz / denemede / ücretli-yenileme + üye listeleri) + POST `/bulk` (seçili
  koçların her birine kişisel token+link; ≤200, tekilleştirir, atlar). Smoke 19/19.
- Frontend: membership client "Tekli / Toplu" mod + BulkComposer (grup chip +
  üye checklist + teklif parametreleri) + BulkResults (her koç link kopyala +
  WhatsApp [telefon varsa doğrudan] + "Tüm linkleri kopyala" broadcast).
- **KALAN:** Iyzico kart (işletme gelince) + B (Cloud API mavi-tik).

## Vitrin + akıllı paket içeriği (2026-06-04, A1+A2 CANLI · B sırada)

**Teşhis (canlı veri):** keşif ÇALIŞIYOR — 109 aday (`kesif-mig-*`) migration'lardan
bulunmuş AMA hepsi DRAFT'ta sıkışmış (mockup/benefit/rol yok + teknik başlık →
yayınlanamıyor); landing yalnız 11 elle-seed (`kesfet-*`) kart gösteriyor. Paket
bullet'ları `plans.py` `features_included`'da sabit/generic, feature_catalog'dan
kopuk. **Onaylı yön (kullanıcı):** A→B sırası · Gemini · generic mockup · tek-kaynak;
**+ benzer alandaki özellikleri tek temalı kartta birleştir** (109 → ~10 tema).

- **A1 ✅ generic mockup:** `mockup_registry`'ye `"generic"` (bespoke görsel
  gerektirmez) + Next.js `GenericShowcase` (`mockups.tsx` MAP) + Jinja parite.
  mockup zorunluluğu artık yayın darboğazı değil.
- **A2 ✅ AI temalı gruplama:** `feature_clustering.cluster_and_draft` — Gemini
  (ücretsiz key, personal_data=False) keşif adaylarını PAZARLAMA temasına gruplar
  (WhatsApp/AI/veli/akademik…), her temaya çarpıcı kart (başlık+tagline+birleşik
  benefit+ticari ağırlık→strategic_priority+rol) + generic mockup ile DRAFT üretir;
  kaynak adayları `manual_hide=True` ile kuyruktan gizler. Endpoint
  `POST /admin/feature-catalog/discovery-queue/ai-cluster` (AI hata→502/422).
  Admin keşif-kuyruğu sayfasında "AI ile grupla & temalı kart üret" butonu.
  Smoke `test_api_v2_feature_clustering.py` **5/5** (Gemini monkeypatch).
  **Kullanım:** admin "AI ile grupla" → ~10 temalı DRAFT → Vitrin Kartları'nda
  gözden geçir → yayınla → anasayfa.
  **FIX (2026-06-04, kullanıcı prod hatası "JSON nesnesi değil"):** 109 aday →
  büyük yanıt + 2.5 düşünme tokenı maxOutputTokens=8192'i aşıp JSON'u kesiyordu.
  `gemini.generate`'e `max_output_tokens` + `prefer_paid` eklendi; clustering
  **ücretli pro model + 24576 token + 90s timeout + tek çağrıda ≤70 aday** (kalan
  varsa "tekrar çalıştır"). Kullanıcı kararı: bu önemli iş ücretli key'den.
- **B ✅ akıllı paket içeriği TEK KAYNAK:** paket bullet'ları 4 ayrı yerdeydi
  (`pricing.py _marketing_cards` GÜÇLÜ · `plans.py features_included` bland ·
  `teacher-plan TIER_DETAILS` frontend-hardcoded [görseldeki bland kart] ·
  admin `INSTITUTION_TIER_DETAILS` hardcoded) → tek `pricing.features_for_plan(
  plan_code)` (pazarlama-odaklı: yapay zekâ hazırlığı, kopan öğrenci erken uyarı,
  veli bildirim…). `_marketing_cards` bunu kullanır (DRY); catalog'a `plan_features
  {kod: bullet'lar}` eklendi. **Fiyat/limit iskeleti BOZULMADI** — yalnız sunum.
  Yüzeyler: /pricing+anasayfa (zaten) · membership üyelik sayfası (features_for_plan) ·
  /teacher/plan + admin kurum (API plan_features[code], yerel fallback). plans.py
  features_included artık yalnız dead Jinja. Smoke pricing 8 + membership 19. CANLI.
- **Vitrin + akıllı paket içeriği (A1+A2+B) TAMAMLANDI.** Kalan opsiyonel: AI
  prompt ton ayarı (kullanıcı A2 çıktısını görünce) + commercial_weight'i landing
  skoruna besleme. [[project-revenue-panel-v2-roadmap]]

## Mobil App — Koç + Kurum ekranları + Push bildirimi (2026-06-05)

**Bağlam (kullanıcı, otomatik plan direktifi):** "koç ekranı ve ona bağlı bütün
işlemleri sormadan tamamla → kurum yöneticisi ekranlarına geç → web vs app
özelliklerini karşılaştır → e-posta gönderimlerinin uygulamada **bildirim** olması
konusunu (push) en son çöz. Kararları benim için al." Mobil = Expo SDK 54
(öğrenci/veli zaten vardı). Mobil-only değişiklik deploy gerektirmez (endpoint'ler
canlı); backend ekleri web+worker rebuild ile deploy.

- **Koç app** (commit `5567a06`/`de0902f`/`a59e127`): öğrenci listesi (uyarı renkli)
  + **öğrenci detayı sekmeli** (Genel durum / **Denemeler** gör+sonuç gir+sil net
  canlı hesap / **Seanslar** gör+kaydet durum/kanal/gündem/ruh hali) + **Tahsilat**
  (aylık pano, ücret belirle + ödeme gir, ay seçici) + **Destek** (talep/yanıt
  thread + Gelen Talepler) + Profil. Program editörü/kütüphane/AI/abonelik/WhatsApp
  **web'de** (Profil→Web paneli linki). Paylaşılan `FormSheet` (klavyeden kaçınan
  alttan modal) + `components/support/*` (kurum+veli reuse).
- **Kurum Yöneticisi app** (commit `dd070d6`): rol yönlendirme institution_admin
  → /institution/dashboard. **Panel** (kurum KPI + riskli/pasif + koç performans
  satırları orana göre renk ≥70 yeşil/≥40 amber/<40 rose) + **Müdahale Merkezi**
  (severity kartları + öneri) + **Talepler** (gelen+kendi) + Profil. Analiz
  derinliği/CRUD/abonelik **web'de**.
- **Push bildirim** (commit `c1bfb62`, **migration `c6d9g2h3g00x` — device_push_tokens,
  additive; CANLI deploy edildi, head=c6d9g2h3g00x**): `DevicePushToken` +
  `push_notifications` servisi (Expo Push API, best-effort: hata fırlatmaz,
  `DeviceNotRegistered`→token siler). `POST/DELETE /api/v2/me/push-token` (upsert/sil).
  **notification_dispatcher EMAIL kanalında veliye push** (kind→başlık: Haftalık
  rapor/Yeni program/Dikkat/Koç notu/Boş gün); **support reply** ilgili taraflara
  push. Mobil: `expo-notifications` + app.json plugin + `lib/push` (izin+token+kayıt,
  web/simülatör/projectId yoksa **sessiz no-op**); auth authed→kayıt, çıkış→sil.
  `test_api_v2_push_notifications.py` **9/9**; regresyon auth_mobile 9 + me 13 +
  support 54 + api_v1 47 GREEN. **Tam çalışması için EAS projectId + EAS build**
  gerek (Expo Go'da projectId yoksa kayıt no-op; özellik bozulmaz).
- **Web↔app parite tablosu**: `mobile/PARITY.md` (rol bazlı özellik karşılaştırması
  + bildirim push kapsamı + sıradaki opsiyonel adımlar).

## Mobil App — rol derinleştirme + veli deep-link (2026-06-05, EAS build öncesi)

**Bağlam (kullanıcı, EAS build'den önce eklemeler — onaysız ilerle):** 3 alan.
Hepsi mobil-only (endpoint'ler zaten canlı → deploy YOK). 82 rota temiz derlenir.

- **Veli (öncelik — "projenin en güçlü yönü") — bildirim deep-link + rapor** (commit `faeaeaf`):
  - `NotificationObserver` (root `_layout`): push'a tıkla → doğru ekran (soğuk
    açılış pending→authed'de yönlendir; sıcak tık anında). Eşleme: weekly_report→
    **Haftalık rapor** (geçen hafta performansı), new_program→Haftalık program,
    teacher_note/drop_alert/exam_approaching/empty_day→Çocuk detayı, support→thread.
  - Yeni **Haftalık rapor** ekranı (`parent-child-report`): performans halkası
    (%tamamlama ton renkli) + görev/test toplamı + gün gün barlar (geçen
    tamamlanmış hafta, `getParentChildWeek(lastMonday)`). Çocuk detayına "Haftalık
    rapor" + "Haftalık program" butonları.
- **Öğrenci — günün notu + Gelişim + Kitaplar** (commit `bf7ecfd`):
  - Bugün ekranına **günün notu** kartı (`DayNoteCard`, 700ms debounce autosave,
    web ile aynı; koç web day-board'da görür).
  - Yeni **"Gelişim" sekmesi**: Çalışma DNA (kronotip + dönem barları + zirve) +
    Hedefler (özet + aktif ilerleme) + Odak (seri/dk/puan) + Tekrar (aralıklı —
    due + breakdown). **Kitaplarım** ekranı (ders bazlı açılır + kitap progress).
  - lib/student: saveDayNote + booksProgress/dna/focus/review/goals fetcher'ları.
- **Koç — Program + davet + paket** (commit `cf4ed1f`):
  - Öğrenci detayına **"Program" sekmesi**: haftalık görünüm (gün kartları + görev
    durumu + %) + her güne **"Görev ekle"** (`AddTaskSheet`: Test kitap→bölüm→soru
    [atanmış kitaplardan, kalan göster] veya Etkinlik video/özet/tekrar/diğer) →
    POST /students/{id}/tasks; görev sil (basılı tut).
  - **Öğrenci davet**: listede "Davet" → ad/email/sınıf → oluştur → geçici şifre
    kartı + kopyala (expo-clipboard).
  - **Paket** (bağımsız koç, Profil→"Paketim"): durum + AI kredisi (kullanım barı)
    + tier seçenekleri (sana-uygun rozeti) + yükselt (onaylı, /plan/upgrade).
  - lib/teacher: week/task-create/student-books/create-student/plan fetcher'ları.
  - **Web'de kalan koç işleri** (PARITY.md): gelişmiş program editörü (sürükle-
    bırak/rezerv/blok/periyot), kütüphane/kitap CRUD, AI foto/ses, kaynak kullanım
    oranları, akademik yıl, sınıf yükseltme, odak/tekrar/hedef düzenleme.
- **Sıradaki:** EAS build + projectId (push uçtan uca test + store derlemesi) ·
  native AI yakalama · Faz 7 `app/preview/*` temizliği.

## Mobil App — Odak/Tekrar/DNA/Hedef YÖNETİLEBİLİR (koçluğun sırrı) (2026-06-05)

**Bağlam (kullanıcı, kritik):** "Koçluğun sırrı burada — basit program takibinden
farkı bu. Odak/Tekrar/DNA/Hedef hem koç hem öğrenci için mobilde **yönetilebilir**
olmalı. Öğrencilerin çoğunda bilgisayar yok → telefonda yoksa kullanılmaz." Salt-
okuma reddedildi. Mobil-only (uçlar canlı). 95 rota temiz.

- **Öğrenci — etkileşimli** (commit `feb9b69`): Gelişim hub salt-okumadan aksiyona:
  - **Odak**: canlı Pomodoro (`/student-focus`) — süre seç → geri sayım ring →
    Bitir/Vazgeç (`/focus/start|stop|cancel`).
  - **Tekrar**: aralıklı tekrar oturumu (`/student-review`) — due kartlar tek tek,
    Hatırlamadım/Zor/İyi/Kolay (FSRS rating 1-4, `/review/{id}/rate`).
  - **Hedefler**: oluştur + ilerleme gir + Başardım (`/student-goals`,
    `/goals` + `/progress` + `/toggle`).
  - Gelişim kartlarına aksiyon butonları (Odağa başla / Tekrara başla(N) / yönet).
- **Koç — izle + yönet** (commit `46c0590`): öğrenci detayı "Genel" → **"Gelişim
  izleme"** (`/teacher-student-dev`) alt-sekmeli (DNA/Odak/Tekrar/Hedef):
  - DNA (kronotip + dönem + ders kırılımı + trend) · Odak (seri/puan + son
    oturumlar) · Tekrar (**zorlandığı konular** + kaç kez unuttu = koçluk
    içgörüsü; ders seed) · Hedef (**hedef ağacı** nested + öğrenciye hedef ekle).
  - lib/teacher: dna/focus/review/goals fetcher + createTeacherGoal + seedTeacherReview.
- Backend teacher uçları (`/students/{id}/dna|focus|review|goals` + goal create +
  review/seed) ZATEN vardı — mobil bağlandı. PARITY.md güncel.

## Veli Haftalık Rapor — doyurucu analiz (web + mobil) (2026-06-05, migration YOK)

**Bağlam (kullanıcı, Image #56):** Veli haftalık rapor ekranı "kemik" idi —
sadece bir tamamlama halkası + gün gün `138/138 · 151/151` (etiketsiz görev/test
sayıları, anlamsız). Kullanıcı: "bir veli olsan çocuğunun en çok merak ettiğin
bilgi ne olurdu?" → bu hafta düzeldi mi (geçen haftaya kıyas) · netler yükseliş
mi düşüş mü · en çok hangi dersi çözüyor / aksatıyor · gün gün ne yaptı. Hem web
veli hem mobil.
- **Kritik bulgu (KURAL 1):** `schemas/parent.py`'de zaten zengin bir
  **`WeeklyReportResponse`** şeması vardı (öksüz — endpoint/servis/frontend hiç
  bağlanmamış; geçmiş oturumda tanımlanıp yarım bırakılmış). Tam istenen alanlar:
  daily + subjects (most_completed/most_neglected) + comparison (delta/direction)
  + exams + exam_trend + teacher_notes + verdict. Bu şemayı tamamladım.
- **Tek kaynak backend:** `app/services/parent_weekly_report.py` →
  `build_weekly_report(db, parent, student_id, week_start)`. `gorev_stats.summarize`
  (görev/test/deneme ayrımı) reuse: bu hafta + geçen hafta özeti + per-gün +
  per-ders (TEST kategorisi) agregasyonu; en çok çözülen = max test_completed,
  en çok aksatılan = planlanan>0 & en düşük %; net trendi = son denemenin
  türünde önceki denemeyle delta (son 60g, ≤8 deneme); koç notu son 14g; verdict
  level(≥70 good/≥40 warn/<40 bad) × direction → sade-dil tek cümle.
  - **Varsayılan hafta = son TAMAMLANMIŞ hafta** (geçen Pzt; kıyas dürüst:
    tam↔tam). `week_start` daima Pazartesi'ye snap. prev/next ile gezilir.
  - **KVKK:** `assert_parent_can_view` (bağ yoksa 404). **Deneme netleri veliye
    PAYLAŞILIR** (2026-06-01 kararı, dashboard zaten gösteriyordu); web dashboard
    "net paylaşılmaz" bayat gizlilik notu gerçeğe uyduruldu (konu bazında
    doğru/yanlış + öğrenci-koç notları paylaşılmaz).
- Endpoint `GET /api/v2/parent/students/{id}/weekly-report?week_start=YYYY-MM-DD`.
  `scripts/test_api_v2_parent_weekly_report.py` — **14/14**.
- **Web:** `lib/types/parent.ts` + `lib/api/parent.ts` (weeklyReport key + fetcher)
  · yeni `/parent/students/[id]/report` route + `parent-weekly-report-client.tsx`
  (hafta gezgini + verdict bandı + **geçen haftaya kıyas manşeti** [Tamamlama%/
  çözülen test/çalışılan gün ↑↓ delta] + ders kırılımı [en çok çözülen/aksatılan
  chip + barlar] + deneme performansı [büyük net + trend + son denemeler] + gün
  gün net-etiketli + koç notları). Öğrenci detayına **"Haftalık Rapor"** birincil
  butonu. Kontrast-güvenli (tonal zeminlerde explicit koyu renk).
- **Mobil:** `lib/parent.ts` (WeeklyReport tipleri + `getParentWeeklyReport`) ·
  `parent-child-report.tsx` route hafta gezginli (varsayılan backend = son
  tamamlanmış hafta) · `child-report-view.tsx` web ile birebir bölümlere
  yeniden yazıldı (Ionicons) · preview mock güncellendi.
- **Doğrulama:** weekly-report 14/14 · parent 20/20 · gorev_stats 27/27 ·
  card_consistency 23/23 · **run_gorev_checks 82/82** · web tsc+eslint temiz ·
  mobil tsc temiz. Migration YOK (mevcut tablolardan agregasyon).
- **NOT (deploy):** backend (parent_weekly_report + endpoint) hem web hem mobil
  tarafından tüketilir → canlıda görmek için **web+worker+next rebuild** gerekir
  (mobil app kodu ayrıca EAS build ister). [[feedback-card-numbers-need-units]]
  [[feedback-holistic-change-propagation]] — commit `e54ee8c` (web+backend, deploy
  edildi) + `27a1e1e` (mobil gün-gün bar fix).

## Mobil — koç/öğrenci eksikleri paketi (2026-06-05, mobil-only, migration YOK)

**Bağlam (kullanıcı):** 7 maddelik istek; kullanıcı "önce mobil koç/öğrenci
eksikleri" dedi. Hepsi MEVCUT backend uçlarını kullanır (yeni endpoint/migration
YOK) — yalnız mobil UI parite. Web'de hepsi zaten vardı; mobilde eksikti.
- **M-1 — Koç öğrenciyi pasife alma/aktif etme**: `student-detail-view` "Hızlı
  işlemler"e Pasife al/Aktif et butonu (Alert onay) → `/teacher/students/{id}/
  deactivate|reactivate`. `teacher-student.tsx` mutation + invalidate.
- **M-5 — Mobilden WhatsApp gönderme** (kullanıcının sorusu = EVET): yeni
  `lib/messaging.ts` (web `/messaging/*` aynen) + paylaşılan
  `components/messaging/wa-send-dialog.tsx` (Modal: şablon seç + değişken doldur +
  önizleme → `buildWaLink` → **`Linking.openURL(wa.me)`** → WhatsApp metin hazır
  açılır). Öğrenci detayına "WhatsApp gönder" butonu (defaultCategory="ogrenci").
  Backend yetki matrisi (koç→kendi öğrencisi+velisi) hazırdı; telefon doğrulanmamış
  hedefte 400 → Alert. (Kurum yöneticisi/veli hedefleri sonra eklenebilir.)
- **M-4 — Koç abonelik/yenileme talebi**: `plan-view`'e "Öde ve devam et / yenile"
  kartı (aylık/akademik-yıl döngü seçici) → `/teacher/subscription-request`
  {plan, cycle} → contact_request (manuel aktivasyon). Mevcut direkt "Bu pakete
  geç" (upgrade) korundu; bu AYRI ödeme/yenileme akışı.
- **M-2 — Koç öğrenci taleplerini (TaskRequest) yönetme**: yeni `teacher/requests.tsx`
  **5. tab "Talepler"** (bekleyen sayı rozetli) + `teacher-requests-view` (kart liste:
  Onayla/Reddet/Yanıtla). `/teacher/requests` + approve/reject({reason})/respond
  ({response}). Red/yanıt için alttan metin modalı. **Destek (SupportRequest)
  tab'ından AYRI** — bu program talepleri.
- **M-3 — Öğrenci talepleri ayrı sekme**: `student/requests.tsx` **6. tab
  "Talepler"** (eski profil-içi link + standalone `(app)/requests.tsx` kaldırıldı;
  `RequestsView` reuse). Öğrenci "Koça ilet" ile oluşturduğu istekleri burada
  görüp geri çeker.
- **Doğrulama**: mobil `tsc --noEmit` temiz + `expo lint` ile feature dosyaları
  temiz (kalan 2 hata parent/dashboard + preview, ÖNCEDEN vardı — benim değil).
  `expo lint`'in kurduğu eslint config + package.json/lock değişikliği geri alındı
  (istenmedi). **Mobil-only → sunucu deploy GEREKMEZ** (uçlar canlı); Expo reload
  ile görünür. EAS build sırada.

## KRİTİK güvenlik fix — logout Jinja session cookie'sini temizlemiyordu (2026-06-05, deploy edildi)

**Bağlam (kullanıcı):** Admin çıkış yapınca `/admin`'e dönüyor ve panel çıkış
yapmamış gibi çalışmaya devam ediyordu.
- **Kök neden:** BFF dependency (`dependencies._resolve_user_v2`) 3 kanallı:
  cookie → bearer → **Jinja `session` cookie fallback** (`session.get("user_id")`,
  geçiş dönemi). `/admin/impersonate/end` (admin.py:2479) impersonation bitince
  admin'in `user_id`'sini `request.session`'a yazıyor. `v2_logout` yalnız BFF
  cookie'lerini siliyordu → kalan `session` cookie ile dependency LOGOUT SONRASI
  hâlâ authenticate ediyordu → `/admin` açık kalıyor, `/login` de oturum görüp
  roleHome'a (admin) sıçratıyordu.
- **Fix (`auth.py` v2_logout):** `request.session.clear()` eklendi → SessionMiddleware
  `session` cookie'sini Max-Age=0 ile siler. Çıkış sonrası HİÇBİR kanaldan auth yok.
- **Kapsam:** yalnız **impersonation kullanan süper adminleri** etkiliyordu
  (`session["user_id"]`'yi YALNIZ impersonation endpoint'leri yazıyor — admin.py
  2327/2480). **Mobil ETKİLENMEZ** (Bearer token secure-store'da; cookie/session
  yok; `signOut` → `clearTokens()` yerel temizler). Normal web kullanıcıları
  (öğretmen/öğrenci/veli/kurum) BFF cookie-only → session cookie almıyorlar →
  zaten etkilenmiyorlardı. Fix yine de TÜM kullanıcıları korur (logout artık tüm
  auth durumunu temizler).
- **Reprodüksiyon + test:** `test_api_v2_logout_session.py` (impersonate→end→logout→
  /me MUST 401). Fix'siz **kırmızı** (logout sonrası /me=200 admin + /admin/dashboard
  =200 — kullanıcının raporu birebir); fix'le **12/12 yeşil**. Regresyon:
  impersonation_bff 8/8 · auth_p1 10/10 · me 13/13. Commit `b09f3a6`, web+worker
  rebuild, canlıda `request.session.clear()` doğrulandı.
- **AÇIK HARDENING (opsiyonel, kullanıcı kararı):** migration tamamlandığı için
  BFF dependency'sindeki `_resolve_from_session` fallback'i artık geçiş-dönemi
  liability'si — yalnız impersonation session yazıyor. İstenirse (a) impersonation
  start/end'in `session` yazımları kaldırılır (kaynağı kurutur) veya (b) fallback
  dependency'den çıkarılır (BFF tamamen cookie/bearer olur). Bu fix tek başına
  raporlanan açığı kapatır; hardening belt-and-suspenders.

## Demo silme — transitif kapanış (demo kullanıcılar + ÜRETTİKLERİ) (2026-06-06, deploy edildi)

**Bağlam (kullanıcı):** Demo koç/kurum açıp test ederken **gerçek (demo-işaretsiz)**
kayıtlar üretiliyor (demo koçun manuel oluşturduğu öğrenci, kurum yöneticisinin
davet ettiği öğretmen+öğrenci, kitap, görev, deneme). Eski `delete_demo_session`
yalnız `is_demo=True` seed kayıtlarını siliyordu → bu üretilenler **yetim kalıyordu**
(`User.teacher_id` SET NULL → koçsuz öğrenci; davet edilen öğretmen+öğrencisi
sistemde kalıyor). Kullanıcı: "demo kullanıcılarını ve bu kullanıcıların
ürettiklerini sistemden temizleyebilmeliyiz."
- **FK denetimi:** users.id'ye giden 117 FK'nin TAMAMI explicit ondelete (59
  CASCADE + 58 SET NULL) — bloklayıcı yok. **Prod (Postgres):** User satırı
  silmek tüm CASCADE ağacını otomatik temizler, SET NULL'ları null'lar
  (audit/log korunur). **Dev (SQLite):** FK pragma kapalı → explicit silmeler
  gerekli (mevcut fonksiyonun nedeni buydu).
- **Çözüm (`demo_seed._demo_closure`):** transitif kapanış — (1) demo seed
  kullanıcıları + (2) demo kurum ÜYELERİ (institution_id; davet edilen öğretmen/
  öğrenci) + (3) koçların öğrencileri (teacher_id, iteratif) + (4) bu öğrencilerin
  velileri (**GÜVENLİK: yalnız tüm çocukları silinecek sette olan veli; başka
  gerçek çocuğu olan veli KORUNUR**). `delete_demo_session` bu genişletilmiş
  user_ids/inst_ids ile mevcut explicit silmeleri çalıştırır + Invitation
  (kurum→öğretmen) + ParentInvitation (koç→veli) eklendi + bulk user/institution
  silme (prod cascade gerisini halleder).
- **Test `test_demo_seed_cleanup.py` 13/13:** (S1) solo demo koç + manuel gerçek
  Zeynep+veli+kitap+görev+deneme → hepsi süpürüldü, yetim yok. (S2) demo kurum +
  davet edilmiş non-demo öğretmen + onun öğrencisi+velisi+davet+kitap+veri →
  hepsi süpürüldü, kuruma/koça bağlı yetim yok. Regresyon: demo_seed 12/12 +
  demo_sessions 12/12 + admin 13/13.
- **NOT:** `User.teacher_id` SET NULL tasarımı GERÇEK kullanım için DOĞRU kalır
  (bir koç hesabı silinince öğrenciler kaybolmasın → bağımsız olurlar). Bu
  değişiklik yalnız DEMO seansı silmede tam-süpürme yapar. "Demo Oturumları"
  (`/admin/demo-sessions`) sayfasındaki Sil bu kapanışı kullanır.

## Web koç analitik sayfası zenginleştirildi — "program süreci" panosu (2026-06-06)

**Bağlam (kullanıcı, orijinal 7 maddeden #5):** `/teacher/students/{id}#analytics`
yalnız 2 grafik (30g trend + ders barı) içeriyordu. "Koç olsan öğrencinin program
süreciyle ilgili neler bilmek isterdin" → DNA/deneme/odak ZATEN ayrı sekmelerde;
analitik sekmesi **program yürütme** panosu yapıldı (mevcut servisleri reuse).
- Backend `GET /teacher/students/{id}/analytics` zenginleştirildi (migration YOK):
  `student_snapshot` + `compute_projection` + `consistency_score` +
  `daily_activity_flag_series` + `daily_completed/planned_series` + ExamResult
  reuse. 7 yeni blok: **summary** (tempo: rate_7d/30d test/gün + istikrar + tutturma
  + aktif gün + en uzun seri) · **weekly_trend** (son ~10 hafta tamamlama %, Pzt
  bucket) · **activity_calendar** (35 gün gün-gün aktif/planlı-tik-yok/plan-yok) ·
  **dow_performance** (Pzt–Paz ortalama çözülen + tutturma — `proj.dow_rates/
  dow_hit_rates`) · **projection** (sınava kalan/erişilebilir/gap/güven/status) ·
  **exam_trend** (son 60g deneme + aynı-tür net delta) · **warnings** (risk
  sinyalleri). `schemas/teacher.py` +8 model.
- Frontend `student-analytics-panel.tsx`: mevcut SVG çizgi + ders barları korundu;
  üstüne SummaryStrip + ProjectionCard + WeeklyTrendCard (div bar) + DowCard +
  ActivityCalendarCard (GitHub-grid) + ExamTrendCard + WarningsCard. Kontrast-
  güvenli (tonal zeminlerde explicit koyu renk). `lib/types/teacher.ts` +8 tip.
- **Test** `test_api_v2_teacher_analytics_rich.py` **10/10** (7 blok + tempo +
  projeksiyon 200 + net trendi +10 + 35-gün takvim + 7-gün dow). Regresyon:
  5d1 10/10 + teacher_read 12/12 + teacher_exams 18/18 · web tsc+eslint temiz.
- **KALAN (orijinal 7'den #6):** öğrenci kendi web analiz sayfası — sıradaki.

## 4 sorun — mobil itemless + abonelik pending + abuse yanlış-pozitif + abuse testi (2026-06-06)

Kullanıcının 5 sorusundan 4'ü bu turda çözüldü (#1 mobil giriş + #5 önlem ayrı
paketlerde — kullanıcı onayı: tanıtım carousel + signup · IP hız kapısı + telefon
doğrulama kapısı).
- **#3 — Mobil itemless/etkinlik görevi "yapılmadı" görünüyordu** (bug): mobil
  `teacher/week-view.tsx` `done = pct >= 1` kullanıyordu; itemless görevde
  (video/deneme/diğer, planned=0) pct=0 → hep yapılmadı. Web `status === "completed"`
  kullanır. Düzeltme: `taskDone(t) = status === "completed" || (planned>0 && pct>=1)`
  (görev satırı + gün başlığı sayımı). tsc temiz.
- **#4 — Abonelik "ödeme talebi" butonu her açılışta aktif** (bug): `GET /teacher/plan`
  yanıtında bekleyen-talep bayrağı yoktu (POST idempotent ama GET bilmiyordu).
  `TeacherPlanResponse.has_pending_subscription_request` eklendi (subscription-request
  ile aynı ContactRequest sorgusu). Mobil plan-view + web teacher-plan-client bekleyen
  talepte butonu pasifleştirir + "Talebin alındı" gösterir. subscription smoke 11/11.
- **#2 — "Sürekli açık abuse ihlali sinyali"** (yanlış-pozitif): `multi_account_same_device`
  (aynı IP+UA'dan 3+ farklı user/24s) sinyali süper admin'in kendi test davranışından
  tetikleniyordu — impersonation hedef için admin tarayıcısından ActiveSession açar →
  3+ distinct user → eşik(3) anında aşılır, saatlik cron+dedup ile sürekli açık kalır.
  **Fix (migration `d7e0h3i4h11y` — active_sessions.imp_by, additive):** impersonation
  oturumu `imp_by`=admin id ile işaretlenir; dedektör `imp_by IS NULL` + `role !=
  super_admin` ile bunları sayımdan dışlar. **Eşik 3'te bırakıldı** (5 yapmak #5'i
  yakalanamaz yapardı). `record_session_start(imp_by=)` + admin.py impersonate çağrısı
  güncellendi.
- **#5 — Çoklu-hesap çiftliği TEST EDİLDİ** (`test_abuse_multi_account_scenario.py` 4/4):
  bağımsız koç N hesap açıp her birinde 3 öğrenci → solo_free limitini aşar. Kamera:
  (A) aynı cihaz/IP'den 3 hesap → YAKALAR; (B) farklı IP (VPN/4G) → bypass; (C)
  impersonation+süper admin → SAYILMAZ (yanlış-pozitif fix doğrulandı). Yakalama
  advisory (login-anı, engellemez). **Asıl önlem (#5 paketi, sıradaki):** signup-anı
  IP hız kapısı + SMS telefon doğrulama kapısı (bir doğrulanmış telefon = bir trial).
- Regresyon: abuse 21/21 · impersonation_bff 8/8 · admin_users 26/26 · logout 12/12 ·
  subscription 11/11. Migration head = `d7e0h3i4h11y`.

## Mobil #1 native koç signup + #5 signup-anı IP hız kapısı (2026-06-06)

Kullanıcının #1 (mobil tanıtım+signup) ve #5 (çoklu-hesap önlem) seçimleri.
Tanıtım carousel önceki commit (`adcbd48`); bu paket native signup + IP kapısı.
- **#1 backend — mobil koç signup**: signup_teacher Turnstile'ı `not payload.mobile`
  ile atlar (mobilde captcha widget'ı zor); `_establish_bff_session(mobile=True)`
  cookie KURMAZ, token pair döndürür; `SignupTeacherIn.mobile` + `SignupOut`'a
  access/refresh token alanları → mobil Bearer auth. (login deseniyle birebir.)
- **#5 backend — IP hız kapısı + sinyal** (migration YOK, AuditLog reuse):
  `signup_guard.py` — aynı IP'den 24s içinde `SIGNUP_IP_BLOCK_THRESHOLD=3`
  self-signup VARSA yenisi **429 signup_ip_rate_limited** (mass farming hard-block;
  mobilde captcha olmadığı için kritik). `abuse_detection.detect_signup_velocity`
  (yeni kind `signup_velocity`, run_all'a + saatlik cron'a dahil) o IP'leri süper
  admin güvenlik kamerasında **işaretler** (USER_CREATE self_signup audit'leri IP'ye
  göre gruplar). `ABUSE_KIND_LABELS_TR`/`DESCRIPTIONS` güncellendi. Kesin önlem
  (bir telefon = bir hesap) SMS telefon kapısı — SMS canlıya alınınca.
- **#1 mobil — native signup ekranı**: `lib/auth.tsx` +`signUp(input)` (mobil=true →
  token → setTokens → authed); `app/signup.tsx` (ad/email/telefon/şifre×2 + hata
  kodları); welcome "Ücretsiz dene" + login "14 gün ücretsiz dene" artık web yerine
  app-içi `/signup`'a gider.
- **Test** `test_api_v2_signup_mobile_guard.py` **7/7**: mobil signup token body'de +
  /me geçer · 3 signup geçer 4. → 429 · signup_velocity dedektörü IP'yi işaretler.
  Regresyon: auth 14 · auth_p1 10 · auth_p3 13 · me 13 · api_v1 47 · multi_account 4 ·
  abuse 21. Migration YOK. mobil tsc temiz.
- **KALAN (#5)**: SMS telefon doğrulama kapısı (SMS canlıya alınınca devreye girer).

## #5 Signup telefon doğrulama kapısı — DORMANT (2026-06-06, migration `e8f1i4j5i22z`)

Çoklu-hesap çiftliğini kökünden kesmek için signup-anı SMS OTP kapısı. **Yalnız
`is_sms_enabled()` (SMS OTP paketi alınıp `SMS_ENABLED=true`) iken zorunlu**; o ana
kadar `signup_phone_required()`=False → signup eskisi gibi (telefon opsiyonel,
doğrulamasız). Deploy edildi ama SMS açılana dek HİÇBİR kaydı etkilemez.
- **Migration `e8f1i4j5i22z`** (down_revision d7e0h3i4h11y): `signup_phone_verifications`
  (hesap-OLUŞMADAN önce telefon-anahtarlı OTP; mevcut `phone_verifications` user_id'ye
  bağlı). Additive, downgrade'li, uygulandı. **alembic head = e8f1i4j5i22z.**
- `signup_phone_service`: required/start/verify/decode_token/phone_in_use (60s cooldown
  + IP saatlik cap + bir-telefon-bir-hesap tekillik). 3 public endpoint
  `/auth/signup/phone/{required,start,verify}` → imzalı `phone_token` (JWT 20dk).
- `signup_teacher` kapısı: açıkken `phone_token` zorunlu → telefon DOĞRULANMIŞ
  (`phone_verified_at` set) + tekillik 409. Web + mobil signup formuna koşullu OTP
  adımı (bütüncül yayılım — kapı global). `test_api_v2_signup_phone_gate` 12/12
  (dormant #2 dahil). Commit `0e6e2bc`, canlı (`/required`→false doğrulandı).

## Mobil Kurum Yöneticisi paneli — web paritesi (2026-06-06, mobil-only)

Kurum yöneticisi mobil panelini web paritesine taşıdı (tümü CANLI uçlar — yeni
endpoint/migration YOK). Yeni **"Analiz" sekmesi** (hub) tüm ekranları gruplar.
- **Koç detayı**: Panel'de koç satırı → `institution-teacher` (öğrenci listesi +
  son 7g planlanan/çözülen + gizlilik banner).
- **Öğretmen daveti**: `institution-invitations` (oluştur + link kopyala/paylaş + iptal).
- **Analiz** (Analiz hub): Program Uyumu · Akademik Çıktı · Risk Paneli · Kohort ·
  Aktivite Haritası · Tükenmişlik · Öğretmen Karnesi · Hedef Analizi · Haftalık Özet
  (arşiv+detay+şimdi gönder) · Veli Güveni. Risk + Tükenmişlik'te **"Koça ilet"**
  (notify-coach müdahale talebi).
- **Üyelik**: Kredi Kullanımı · Limitler · Hesap Ayarları (plan yükseltme talebi).
- **Aktivite Akışı**: kim katıldı/davet etti/yükseltti (gün + tür filtresi).
- Talepler (öğretmen inbox + süper admin) zaten mevcut support ekranındaydı.
- Paylaşılan primitive'ler `components/institution/ui.tsx` (InstitutionScreen scaffold +
  Kpi/tone/Section/Bar/Badge/Banner/MiniBars). `lib/institution.ts` tüm tip+fetcher+
  davet/notify/upgrade mutation'ları. tsc temiz. **Mobil-only — sunucu deploy gerekmez**
  (EAS build ister). Commit `9ae1ae4`. PARITY.md güncel.

## Push bildirim genişletmesi — tüm rol e-postaları + öğrenci işaretleme→koç (2026-06-06)

**Bağlam (kullanıcı, "son derece titizlikle"):** veli/öğrenci/koç/bağımsız koç/kurum
yöneticisi için üretilen e-postalar (yeni program, haftalık özet vb.) mobil push olarak
da iletilmeli + deep-link; ayrıca öğrenci programda işaretleyince koça **mobil-only**
push (e-posta YOK).
- **Kritik mimari bulgu**: `NotificationLog`/dispatcher **veli-merkezli** (`parent_id`);
  push yalnız veliye gidiyordu. Koç/kurum yöneticisi e-postaları **doğrudan
  `email_service.send_email`** ile gidiyor (push yoktu). İki mekanizma da ele alındı.
- **Foundation** (`push_notifications.py`): `safe_push` (e-postayı push'a yansıtan
  best-effort, asla raise etmez, token/user yoksa no-op) + `notify_coach_student_progress`
  (öğrenci-ilerleme→koç, öğrenci başına **3 saat throttle**, e-posta YOK). Mobil
  `notification-router`: yeni deep-link tipleri **coach / coach_student / institution /
  student** → ilgili ekran.
- **E-posta→push yansıtmaları** (mevcut e-posta korunarak, additive):
  - Koç/bağımsız koç: deneme/yenileme/süresi-doldu (`trial_notifications` ×4), kredi %80
    (`credits`), teklif (`offers`), yeni öğrenci talebi (`request_service._notify_new_safe`)
    → Paket/Talepler.
  - Kurum yöneticisi: haftalık özet (`admin_digest`), kredi uyarısı, teklif → Özet
    detayı/Kredi/Abonelik.
  - Öğrenci: talep yanıtlandı (`_notify_resolved_safe`) → Talepler.
  - Veli: zaten dispatcher EMAIL kanalında push'lanıyordu (değişmedi).
- **Öğrenci işaretleme→koç push**: `complete_task_v2` + `set_item_completed_v2`
  (total_done>0) uçlarında **FastAPI BackgroundTasks** ile (öğrencinin isteğini BLOKLAMAZ
  — Expo 10s timeout riski; taze SessionLocal; throttle'lı). Un-mark'ta push yok.
- **KAPSAM DIŞI**: süper admin/satış (mobil süper admin yok) + pre-login (şifre
  sıfırlama/e-posta doğrulama). `notify_new_signup_admin`/contact requests = config
  e-postası (user_id yok).
- `test_push_notifications_expansion` **9/9**. Regresyon: student mutations 12 + read 11 +
  teacher requests 14 + trial 4 + renewal 12 + usage 21 + parent 20 + push 9 GREEN.
  Migration YOK. Commit `af9511f`, **web+worker rebuild + canlıda push smoke 9/9 doğrulandı.**
  **KURAL**: yeni bir e-posta üretildiğinde (aktif rol) `safe_push` ile mobil push da
  eklenir + mobil router'a deep-link tipi tanımlanır. Push daima best-effort + throttle'lı.
- **Stale test notu**: `test_api_v2_admin_revenue_offers` (Invoice plan `kurumsal_pro`
  artık geçersiz) + `test_stage6_credits` (eski cooldown davranışı, Paket A'da değişti) +
  `test_stage4_admin_digest` (at_risk=0, onboarding-grace) **önceden bozuktu** — push
  değişiklikleriyle ilgisiz (additive).

## "{Ders} henüz başlanmadı" uyarısı — deneme atamasını test sayıyordu (2026-06-06, deploy edildi)

**Bağlam (kullanıcı, Berra/student 11):** Öğrenci detayı "Durum Özeti" kartında
"**Türk Dili ve Edebiyatı henüz başlanmadı · Rezerv açılmış ama hiçbir test
tamamlanmamış**" uyarısı sürekli görünüyordu; kullanıcı doğruluğunu test etmemi
istedi. SALT-OKUMA prod teşhisi (`scripts/diagnose_subject_untouched.py`,
lgs-web'e docker cp) ile kök neden bulundu.
- **Kök neden:** O derse tek atama bir **BRANŞ DENEMESİ** kitabıydı (TYT Türkçe
  Denemeleri, type=`brans_denemesi`); 2026-06-02 yayınlanmış (taslak değil) tek
  görev, yapılmamış (reserved=1, completed=0). `analytics.subject_breakdown`
  deneme kitaplarını derse kattığı için `subject_untouched_*` uyarısı (analytics.py
  #6) yanıyordu → **DENEME≠TEST standardı ihlali** (CLAUDE.md'deki "KALAN" notunun
  uyarı yüzeyindeki tezahürü). NOT: Berra'nınki taslak değildi/baseline değildi —
  saf deneme-test karışımıydı.
- **Düzeltme (`analytics.py`, migration YOK):**
  - `subject_breakdown(db, id, tests_only=False)` geriye-uyumlu param: True →
    deneme kitapları (branş/genel) HARİÇ (StudentBook agregasyonu + last_completed_at
    sorgusu). Tüm mevcut çağıranlar (ders dağılımı görüntüleme, veli, öğrenci)
    DEĞİŞMEDİ.
  - `generate_warnings` #6 bloğu (`subject_stale` + `subject_untouched`) artık
    `tests_only=True` ile beslenir.
  - **Defect A:** `due_subject_ids` sorgusuna `is_draft=False` + deneme HARİÇ
    filtresi (taslak/yayınlanmamış geçmiş görev "vadesi gelmiş" sayılmaz).
  - **Defect B:** `subject_untouched` koşuluna `completed==0` eklendi (baseline
    "öğrenci zaten çözmüş" / sayaç drifti ile `completed_count>0` ama
    `Task.completed_at=None` durumunda yanlış "başlanmadı" damgası önlenir).
- **Doğrulama:** `scripts/test_subject_untouched_deneme.py` **5/5** (Berra repro
  deneme-only → uyarı YOK · gerçek test rezervli → uyarı VAR · taslak → YOK ·
  baseline completed>0 → YOK · tamamlanmış → YOK). **Canlı teyit:** prod'da
  `generate_warnings(student 11)` artık **hiç uyarı üretmiyor** (subject_untouched
  YOK) → kart "Dikkat gerekiyor"dan "Yolunda"ya döner. Regresyon: alert_correctness
  9/9 · card_consistency 23/23 · teacher_read 12 · teacher_students 14 ·
  analytics_rich 10 · risk_onboarding_grace 6 GREEN. Deploy: web+worker rebuild
  (analytics cron/mail'de de kullanılır). Commit `9f57d6a`.
- **NOT (pre-existing):** `run_gorev_checks.py` içindeki `test_itemless_solved_count.py`
  0/0 patlıyor (`complete_task_v2` argüman sırası bozuk, `'Session' has no attribute
  'id'`) — bu düzeltmeyle İLGİSİZ, stash testiyle teyit edildi. Ayrı küçük test-fix
  bekliyor.

## Bildirim/e-posta denetimi + "Kuyrukta uzun süre bekleyen bildirim" yanlış-alarmı (2026-06-07, deploy edildi)

**Bağlam (kullanıcı):** Süper admine her sabah "Kuyrukta uzun süre bekleyen
bildirim · değer 396 · eşik 60 · CRITICAL" + "Açık abuse sinyali" alarm e-postaları
geliyordu; "bazen mailler gitmiyor mu" endişesi. Tüm bildirim mimarisi eksiksiz
okundu + 4 SALT-OKUMA prod teşhisi yazıldı (`diagnose_parent_notifications`,
`diagnose_notification_queue`, `diagnose_new_program_render`, `diagnose_abuse_signals`).
- **Kuyruk alarmı = YANLIŞ ALARM (sessiz saat).** "396" mail sayısı DEĞİL, en eski
  bekleyenin **dakika yaşı**. Gece 23:55 (weekly_backstop) + 21:00 (empty_day) cron'ları
  mail üretir → sessiz saat (22:00-07:00) → `scheduled_at=07:00`'a ertelenir →
  07:00'de gönderilir. `notification_health.oldest_queued_minutes` YALNIZ `queued_at`
  yaşına bakıp `scheduled_at`'i (ve `next_attempt_at` retry-backoff'unu) yok sayıyordu
  → 00:55–07:00 arası `oldest_queued_long` (alarm_engine) CRITICAL. **Kanıt:** 06:31'de
  alarm, 07:00'de kuyruk boşaldı (son SENT tam 07:00), hiçbir mail kaybolmadı.
- **Düzeltme (`notification_health.py`, migration YOK):** `oldest_queued_minutes`
  artık `dispatch_pending` ile BİREBİR hizalı — `scheduled_at<=now` AND
  `next_attempt_at(null|<=now)` filtreli; yalnız **gerçekten gönderilebilir-ama-
  gönderilmemiş** satırların yaşını ölçer. Alarm yalnız GERÇEK dispatcher durmasında
  çalar; panel "oldest queued" göstergesi de doğrulaştı.
  `scripts/test_oldest_queued_due_aware.py` **4/4**. Regresyon: security_overview 14 +
  alarms_abuse 21. Commit `47c992e`, web+worker rebuild.
- **Mail pipeline SAĞLIKLI (canlı kanıt):** EMAIL_ENABLED=true (Zoho 587/TLS,
  rotam@etutkoc.com) · `parent_notifications_email` flag açık · 4 cron zamanlı+çalışıyor
  · dispatcher canlı (60sn, batch 50) · son 7 gün **22 SENT / 1 FAILED** (o 1 = 06-01
  `parent_new_program` render bug'ı, 06-02 `items→rows` ile düzeldi; aynı payload şimdi
  OK) · son 24h 0 FAILED. Efe'nin velisine 06-06 21:00 empty_day GİTTİ; 06-01 weekly
  23:55→07:00 (sessiz saat) teslim — mekanizma canlı kanıt.
- **"Açık abuse sinyali" alarmı = test/dev yanlış-pozitifi.** `abuse_open` eşik=0 →
  tek çözülmemiş sinyal her değerlendirmede çalar. 2 açık sinyal (ikisi de kullanıcının
  IP'si 176.88.39.7, info): `multi_account_same_device` (05-17, mobil app `okhttp` çoklu
  giriş) + `signup_velocity` (06-05, test koç kayıtları). **Çözüldü** (prod'da
  `abuse_detection.resolve_signal`, resolver=Süper Admin id=6) → kalan açık sinyal 0,
  alarm susar. Detektör yeni sinyal üretirse yine yakalar (06-06 imp_by fix yeni
  impersonation kaynaklı multi_account üretmiyor).
- **Veli bildirim tetik matrisi (referans):** weekly_report (döngü-bitti olayı +
  23:55 backstop) · new_program (**publish-week + "Veliye duyur"; publish-day DEĞİL**) ·
  teacher_note (buton) · empty_day (21:00, 3+ üst üste boş) · drop_alert (Pzt 06:00) ·
  exam_approaching (08:15, D-30/7/1, **sınav tarihi şart**) · invitation/OTP (anlık).
- **AÇIK (kullanıcı kararına bağlı):** (a) NEW_PROGRAM boşluğu — koç gün-gün yayınlarsa
  (publish-day) veli "yeni program" maili hiç almıyor (Efe: 49 görev, 0 bildirim);
  publish-day'e dedup'lı bildirim veya koça hatırlatma eklenebilir. (b) Efe (12/YKS)
  sınav tarihi boş → exam_approaching hiç çıkmaz (veri eksiği).

## Hızlı Erişim Kartları (QA) — davranıştan öğrenen panel kısayolları (2026-06-11)

**Bağlam (kullanıcı):** 5 rolün panel ana sayfasına, kullanıcının kendi gezinti
alışkanlığından öğrenen dinamik hızlı erişim kartları ("öğrenen → öneren →
tıklandıkça kalıcılaşan"). Mevcut statik kartlara DOKUNULMADI. Mantıksal çerçeve
+ 4 kullanıcı kararı (sayfa+kişi düzeyi · otomatik 3-tık kalıcılaşma + elle
kontrol · ham olay logu + agregat · 5 rol birden web) onaylandı.

- **Migration `g0h3k6l7k44b`** (down_revision f9g2j5k6j33a, additive, downgrade'li,
  uygulandı — **alembic head = g0h3k6l7k44b**): `panel_visit_events` (ham olay;
  ham URL SAKLANMAZ, normalize route_key+entity_id; 180g saklama) +
  `panel_route_stats` (kullanıcı+rota+entity başına TEK satır: EWMA skor +
  sayaçlar + pinned_at/dismissed_until/card_clicks; entity_id=0 = sayfa-düzeyi,
  UNIQUE için NULL yerine 0) + `panel_events_purge` günlük cron seed (03:30 UTC).
- **Servis `panel_behavior.py`**: ~100 girişlik ROTA KATALOĞU (5 rol; regex
  pattern → route_key; detay sayfaları liste anahtarında birikir [fold]; sihirbaz/
  form/token'lı sayfalar bilinçli dışarıda) · EWMA skor (yarılanma 14g, okuma
  anında da indirgenir — cron'suz sönme) · kişi-düzeyi rota ağırlığı 1.5 ·
  60sn dedup (yalnız ileri yönde; out-of-order batch sayılır, last_visit_at
  geriye taşınmaz) · yaşam döngüsü: skor≥3.0 + ≥3 farklı gün → ÖNERİLEN; karta
  3 tık VEYA elle pin → KALICI; dismiss → 90g bastırma + kalıcılık sıfır ·
  entity etiketi okuma anında çözülür + erişim kontrolü (koç→kendi öğrencisi
  aktif; veli→ParentStudentLink; kurum yön.→kendi kurumunun koçu; süper admin→
  kurum/kullanıcı; kitap→sahibi) — erişim düşen kart otomatik düşer ·
  `purge_old_events` (cron; sabitli/kalıcı satır yaşar). NOT: autoflush kapalı
  olduğundan record_visits her olaydan sonra flush eder (batch-içi UNIQUE koruması).
- **Endpoint'ler** (`api_v2/quick_access.py`, prefix /me, tüm roller):
  POST `/me/panel-visits` (batch ≤50) · GET `/me/quick-cards` (≤12 aday) ·
  POST `/me/quick-cards/click|pin|dismiss` (invalidate `me:quick-cards`).
  Kimse başkasının verisini göremez (tüm sorgular user_id'li).
- **Frontend**: `use-panel-visit-tracker.ts` (5 shell'de: teacher/institution/
  admin/parent shell + site-header; ≥3sn kalış → ziyaret; 30sn batch; sekme
  kapanışında sendBeacon; hata sessiz) · paylaşılan `quick-access-strip.tsx`
  (maks 6 kart; pinned→established→suggested sırası; "önerilen" rozeti + pin/
  kaldır kontrolleri; boş durumda HİÇ render etmez; `excludeHrefs` ile statik
  kart tekilleştirme) · 5 panel ana sayfasına eklendi (teacher dashboard /
  institution dashboard / admin dashboard [statik kısayol href'leri exclude] /
  parent dashboard / student day [kendi sayfası exclude]).
- **Test**: `scripts/test_api_v2_quick_access.py` **15/15** (anonim 401 +
  katalog/rol filtresi + dedup + eşik + öneri + 3-tık kalıcılaşma + pin +
  erişim düşmesi + dismiss + rol izolasyonu + veli + 404 + purge + cron kaydı).
  Regresyon: me 13 + auth 14 + tenant 29 GREEN · tsc ✅ · eslint ✅ (build YOK
  — dev kuralı). **CANLI (2026-06-11):** commit `5861822` + fix `86d4dff` push;
  sunucuda pull + DB yedek + web/worker/next rebuild; migration prod'da uygulandı
  (head=g0h3k6l7k44b, cron seed `t`), site 200 + endpoint 401 doğrulandı.
  **DERS — Postgres cron seed:** `cron_schedules.enabled` BOOLEAN — raw SQL
  seed'de literal `1` Postgres'te DatatypeMismatch verir (SQLite yutar; eski
  seed migration'ları prod'da hiç koşmadığından — init_db create_all+stamp —
  desen canlıda ilk kez patladı). Bundan sonra seed INSERT'lerinde bool kolona
  daima `:e=True` bind param. Tarayıcı testi kullanıcıda.
- **QA-3 (mobil) ✅ + EAS Update (2026-06-11):**
  - **EAS Update (OTA) kuruldu**: `expo-updates ~29.0.18` + app.json
    `updates.url` (projectId e70c9fe3) + `runtimeVersion: appVersion` +
    eas.json kanalları (preview/production). **İlk etkinleşme yeni AAB ister**
    (native modül); sonrasında salt-JS değişiklikler `eas update --channel
    production` ile store'suz gider.
  - **Mobil hızlı erişim**: `lib/quick-access.ts` (ÇİFT YÖNLÜ eşleme — mobil
    ekran→katalog web path [izleme] + route_key→mobil ekran [navigasyon];
    yeni mobil ekran = iki tabloya satır) · `panel-visit-tracker.tsx` (authed
    layout; ≥3sn + 30sn batch + AppState background flush; source="mobile") ·
    `quick-access-strip.tsx` (4 rol ana ekranı: koç Öğrenciler / kurum Panel /
    veli Çocuklarım / öğrenci Bugün; dokun→git, **basılı tut→Sabitle/Kaldır**;
    mobilde karşılığı olmayan kart gizlenir).
  - Backend: `PanelVisitsBody.source` (web|mobile, pattern-validated) —
    smoke **16/16** (5b: source=mobile kaydı + geçersiz source 422).
  - Mobil tsc temiz. **Kullanıcı aksiyonu**: `eas build --platform android
    --profile production` → AAB v5 → Play kapalı test; sonraki JS işleri OTA.

## Sosyal kanıt + Dönüşüm ölçümü + Plausible analitik + Kurum/koç panel fix'leri (2026-06-14, CANLI)

Uzun oturum; hepsi prod'a deploy edildi (commit'ler `972b928`→`086ba64`).

**Sosyal kanıt (testimonials)** (migration `j3k6n9o0n77e`): `testimonials` tablosu
(kind: review/institution_ref/success_story · status: pending/published/hidden ·
source: manual/in_app/import). Servis `testimonial_service.py` (TEK MERKEZ) +
public `GET /api/v2/testimonials` (yayınlanmış + counts) + `POST /testimonials/submit`
(uygulama-içi, authed) + `GET /testimonials/prompt` (rol+hesap≥7gün+gönderim-yok →
"Deneyimini paylaş" kartı uygunluğu) + süper admin `admin_testimonials.py` (CRUD +
moderasyon, audit `TESTIMONIAL_MODERATE`). Frontend: `/admin/testimonials` panel +
anasayfa **slider** (otomatik+ok+nokta, line-clamp; 0 yayında→hiç render etme) +
**`ShareExperiencePrompt`** (öğrenci/veli/koç/kurum ana ekranlarında, lazy-init
localStorage dismiss). Smoke `test_api_v2_testimonials.py` **19/19**. Kullanıcı
etutkoc.com yorumlarını panelden elle yükledi.

**Dönüşüm ölçümü** (migration `k4l7o0p1o88f`): `signup_attributions` (anonim landing
`fc_telemetry_sid` çerezi → üyelik; variant_slug + source landing/direct).
`conversion_service.py`: signup'ta `record_signup_attribution` (best-effort, koç
self-signup'a kanca) + `compute_funnel` (ziyaretçi→gördü→**tıkladı**→üye→ücretli +
A/B varyant dönüşümü, doğrudan event verisinden). Süper admin `/admin/conversion`
(huni barları + varyant tablosu + jargonsuz mini sözlük). Smoke
`test_api_v2_conversion.py` **10/10** (baseline+delta + varyant izolasyonu).
**Landing kartları artık TIKLANABİLİR** → `cta_click` + `/signup/teacher`; koç/AI
kartlarına **demo butonları** bağlandı (`bind_landing_demos.py` anahtar-kelime
tabanlı, start.sh'te). `clicked` metriği = cta_click+demo_click.
**ÖNEMLİ bulgu:** dönüşüm hunisindeki "kart etkileşimi" eskiden yalnız scroll
(IntersectionObserver view) ölçüyordu; demo butonu/tıklama YOKtu → ölçülemiyordu.
Şimdi gerçek tıklama (cta_click) + demo (demo_click) var.

**Plausible (self-host) site analitiği — CANLI** (`analytics.etutkoc.com`):
`plausible` + ClickHouse + Postgres (docker-compose). **First-party tracking**:
Caddy ana alan adından `/js/*` + `/api/event` → plausible (reklam-engelleyici
dirençli, KVKK, veri kendi sunucumuzda). Kök layout env-driven script
(`PLAUSIBLE_DOMAIN`). Süper admin `/admin/analytics` gömülü pano (iframe,
`PLAUSIBLE_SHARED_URL`). Kurulum `deploy/PLAUSIBLE_SETUP.md`. Doğrulandı:
analytics 200 + tracking 202 + first-party script 200.
- **DERS — ClickHouse 24.12 auth:** default user'ı ağ üzerinden şifresiz bağlanmaya
  KAPATIYOR → Plausible auth-fail crash-loop. `deploy/clickhouse/user-logging.xml`'e
  `<users><default><password></password><networks><ip>::/0</ip></networks>` ekle
  (servis yalnız iç ağda).
- **DERS — Caddy çoklu site bloğu:** ana blok `route{}` içerdiğinden 2 kapanış `}`
  var; yeni site bloğu (`analytics.etutkoc.com {}`) ana bloğun DIŞINA konmalı,
  içine konursa "unrecognized directive" → TÜM proxy düşer (ana site dahil).
- **DERS — VPS OOM (3.7GB):** Plausible+ClickHouse (~675MB) eklenince Next.js build
  OOM-kill oldu. Çözüm: **2GB swap kalıcı eklendi** (`/swapfile` + fstab) +
  build sırasında Plausible geçici `stop` (gerçek RAM boşalt) → build → geri `up`.
- **Secret sızıntısı:** kurulumda `grep PLAUSIBLE` çıktısı SECRET_KEY_BASE/DB
  parolasını sohbete bastı → secret'lar **döndürüldü** (ALTER USER + yeni .env).

**Kurum/koç paneli fix'leri** (kullanıcı bildirdi, migration YOK):
- **"Filo durumu" → "Öğrencilerin durumu"** (koç panosu; filo metaforu yanlıştı).
- **"Kritik 1 ama tıklayınca liste boş" BUG:** kart sayısı `worst_warning_level`
  (analytics uyarı rengi) ama drilldown `?risk=critical` `risk_analysis` skoru →
  iki sistem uyuşmuyordu. Kart artık `risk_analysis`'ten türetiliyor (Kritik=critical
  · Uyarı=medium+high · Yolunda=ok; `?risk=medium` high'ı kapsar) → kart=drilldown=
  /institution/at-risk tutarlı. (`teacher.py` dashboard fleet + filtre.)
- **Kurum "planlanan test" deneme'yle şişiyordu** (1180, gerçekte 63 test + 1117
  deneme): `week_stats_for(tests_only=True)` + `week_test_deneme_for` (görev-merkezli
  `gorev_stats.classify_gorev`, **`item_is_test` + completed_count** — `summarize.
  test_completed` solved_count ekleyip oranı %100 üstüne çıkarıyordu, KAÇINILDI).
  Kurum dashboard + öğretmen detay + compliance SQL (Book inner-join) test-only.
- **test + deneme YAN YANA:** dashboard KPI "Planlanan test" + "Planlanan deneme"
  ayrı + öğretmen tablosunda "Deneme (çöz/plan)" sütunu (`TeacherSummary`/aggregate
  +deneme alanları). Kurum hem soru-bankası hem deneme çözümünü görür.
- **Efe "programsız" işareti DOĞRU** (grace yalnız <3 gün yeni öğrenciyi korur;
  eski+programsız öğrenci doğru işaretlenir — dokunulmadı).
- Smoke: testimonials 19 · conversion 10 · institution 18 · compliance 10 ·
  teacher_read 12 · gorev kart-tutarlılık 23/23.

**Migration head: `k4l7o0p1o88f`** (signup_attributions). Plausible env'leri
`deploy/.env` (PLAUSIBLE_*). [[feedback-holistic-change-propagation]]
[[feedback-card-numbers-need-units]]

## Notlar

- "feedback_lgs_workflow_decisions" + "feedback_lgs_ux_preferences" memory'lerini
  oku — UI tercihleri orada
- "project_jinja_features_to_preserve" memory'sinde Jinja'da olup taşınması
  gereken kritik özelliklerin envanteri var
- Önceki sohbetlerde alınan kararlar bu dosyaya not edilir; her paketin sonunda
  güncellenir.
