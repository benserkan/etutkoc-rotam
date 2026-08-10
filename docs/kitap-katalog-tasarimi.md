# Kitap Kataloğu + Fotoğraftan Okuma — Tasarım Belgesi (2026-08-10)

## 1. Amaç ve ilke

**Sorun:** Kitap tanımlarken müfredattan ekleme sabit test sayısı basıyor
(`book-wizard-client.tsx:269` → `avg_questions_per_test ?? 10`); koçlar her
üniteyi tek tek düzeltiyor. Mevcut AI önerisi (`ai_book_template.py`) kitabı
GÖRMEDEN ad/yayınevinden tahmin ediyor → birebir tutmuyor. Sistemin görev/rezerv
omurgası test sayısı olduğu için birebir doğruluk kritik.

**Çözüm — iki parçalı, tek paket:**
1. **Okuma motoru:** İçindekiler fotoğrafı/örnek PDF'inden Gemini vision ile
   ünite + birebir test sayısı çıkarma (çift okuma + düzeltilebilir önizleme).
2. **Ortak Kitap Kataloğu:** Bir kitap Türkiye'de BİR KEZ tanımlanır
   (süper admin seed'i veya ilk koçun katkısı), sonraki her koç tek tıkla alır.
   Kapak fotoğrafının rolü içerik üretmek DEĞİL, kitabı tanıyıp katalog
   kaydına eşlemek.

**İlkeler:**
- **3 tık:** koç için en uzun yol 3 tık (aşağıda tık sayımları).
- **Körü körüne kayıt yok:** AI okuması daima düzeltilebilir önizlemeden geçer;
  çelişen satır şüpheli işaretlenir; okunamayan test sayısı UYDURULMAZ, boş
  bırakılır.
- **Katalog kirlenmez:** koç katkısı daima `pending`; yalnız süper admin
  `verified` yapar; koçlar yalnız verified kayıtları görür.
- **Telif:** yalnız YAPI verisi (ünite adı + test adedi = olgusal veri) alınır;
  soru içeriği asla. Kaynak: koçun kendi kitabının fotoğrafı veya yayınevinin
  kendi yayınladığı tanıtım/örnek PDF'i. Rakip platform veritabanı kazınmaz.
- **Maliyet:** içindekiler kişisel veri değil → `personal_data=False`
  (ücretsiz Gemini anahtarları, kota dolunca ücretli) → koçtan **kredi düşmez**;
  ölçüm için 0 kredilik UsageKind satırı yazılır + günlük okuma tavanı.

## 2. Mimari özet — katalog 3 kanaldan dolar

```
[Süper admin seed]        [Koç katkısı]              [Koç günlük akışı]
örnek PDF / foto  ──┐   ilk tanımlayan koçun    ┌──  kitap adı yaz / kapak tarat
                    │   yapısı (pending)        │         │
                    ▼          ▼                │         ▼
              ┌─────────────────────────┐       │   katalogda VAR → tek tıkla al
              │  ORTAK KİTAP KATALOĞU   │ ◄─────┘   (birebir test sayıları)
              │  (verified kayıtlar)    │
              └─────────────────────────┘           katalogda YOK → içindekiler
                         ▲                          fotoğrafı oku → kitap oluşur
                         └────── (onaylı, anonim) ── + kataloğa aday olarak düşer
```

Okuma motoru her iki tarafın (admin seed + koç ilk-tanım) ortak aracıdır.
Zamanla katalog kapsamı büyür → fotoğraf ihtiyacı kendiliğinden azalır.

## 3. Veri modeli — `book_templates` genişletmesi (YENİ TABLO YOK)

`BookTemplate` docstring'i zaten planlamış: "İleride paylaşım açılırsa NULL
teacher_id system-template olarak yorumlanabilir" (`app/models/book.py:187`).
Kitap oluşturma ucu `template_id`'den bölüm kopyalamayı ZATEN yapıyor
(`library.py:494-540`). Katalog = global BookTemplate.

**Migration (tek, additive, downgrade'li; SQLite batch mode):**

`book_templates`:
- `teacher_id` → **nullable** (NULL = global katalog kaydı; dolu = kişisel şablon,
  mevcut davranış birebir korunur)
- `catalog_status` VARCHAR(16) NULL — NULL=kişisel · `pending` · `verified` · `hidden`
  (düz VARCHAR — PG enum yükü yok, mevcut desen)
- `name_normalized` VARCHAR(255) NULL + index — eşleştirme anahtarı
  (`curriculum_mapping.normalize` reuse: TR küçük harf + noktalama/ek temizliği)
- `publisher_normalized` VARCHAR(255) NULL + index
- `source` VARCHAR(24) NULL — `admin_seed` · `coach_contribution` · `ai_read`
- `contributed_by_id` FK users SET NULL (anonim gösterilir; yalnız denetim izi)
- `verified_by_id` FK users SET NULL + `verified_at` DateTime NULL
- `usage_count` INT NOT NULL default 0 (koçlar kaç kez kullandı — sıralama sinyali)

`book_template_sections`:
- `topic_id` FK topics SET NULL — **verified katalog kaydı müfredat eşleştirmesini
  de taşır** (yalnız builtin topic; koç kitabı katalogdan alınca test sayıları +
  eşleştirme birlikte gelir, kalanlar mevcut auto-map ile)

`AuditAction`:
- `BOOK_CATALOG_UPDATE` — PG'de `ALTER TYPE auditaction ADD VALUE IF NOT EXISTS`
  ([[feedback-postgres-enum-new-member-migration]] kuralı migration'da uygulanır).
  Admin moderasyon işlemleri (create/verify/hide/delete/update) bununla audit'lenir.

**Kurallar:**
- Kişisel şablon sorguları (`_get_owned_template` vb.) `teacher_id == user.id`
  filtresini KORUR → katalog satırları kişisel listelere sızmaz (test kapsar).
- Katalog kaydının `subject_id`'si yalnız **builtin** (teacher_id NULL) derse
  bağlanabilir; koç katkısında kişisel ders varsa NULL bırakılır (ad metni yeter).
- Kapak görseli SAKLANMAZ (v1): kapak tanıma = Gemini fotoğraftan ad/yayınevi
  okur → normalized arama. Görsel depolama gerekirse ayrı iş.

## 4. Okuma motoru — `app/services/ai_book_structure.py` (yeni)

Sözleşme:
```python
read_structure(files: list[tuple[bytes, str]], *, mode="toc") -> ReadResult
# ReadResult: {
#   book_title: str|None, publisher: str|None,
#   subject_hint: str|None, grade_hint: int|None,
#   sections: [{label, test_count: int|None, suspect: bool}],
#   warnings: [str], read_count: 1|2
# }
identify_cover(image: bytes, media_type: str) -> {title, publisher, subject_hint, grade_hint}
```

- **Girdi:** ≤6 fotoğraf (jpeg/png/webp, her biri ≤8MB) VEYA 1 PDF (≤10MB).
  Gemini inline parts (`ai_exam_import` deseni birebir).
- **Çift okuma:** 2 bağımsız çağrı **paralel** (ThreadPoolExecutor —
  exam_import dersi: uç SENKRON `def`, asla `async`). Birleştirme sıra-bazlı
  hizalama + etiket benzerliği; `test_count` çelişkisi → `suspect=True`
  (önizlemede amber). Bir okuma hata verirse tek okumayla devam + warning.
- **Uydurma koruması:** prompt "içindekilerde test sayısı YAZMIYORSA null döndür,
  tahmin ETME" der; `test_count=None` satır önizlemede boş gelir, koç doldurur.
- **`not_a_toc` kapısı:** <2 bölüm çıkarsa 422 (kapak/rastgele sayfa yüklenmiş).
- **Gemini ayarları:** `personal_data=False` (ücretsiz anahtar önce),
  `json_mode=True`, `max_output_tokens=16384` (düşünme payı dersi), timeout 90s.
- **Ölçüm + tavan:** yeni `UsageKind.AI_BOOK_READ = 0` kredi ("Kitap İçindekiler
  Okuma") — admin kullanım panosunda görünür; koç başına günlük **30 okuma**
  tavanı (bugünkü UsageEvent sayımı; aşımda 429 `daily_read_limit`).
  Süper admin tavandan muaf.

## 5. API yüzeyi

### Koç (library router, mevcut kapılar: auth + sahiplik)
| Uç | İş |
|---|---|
| `POST /library/book-structure/read` | multipart foto[]/PDF → ReadResult taslağı (SENKRON def; kredi 0 + günlük tavan) |
| `POST /library/book-structure/identify-cover` | kapak fotoğrafı → {ad, yayınevi, ders/sınıf ipucu} + katalog eşleşmeleri |
| `GET /library/book-catalog/search?q=&subject_id=&grade=` | YALNIZ `verified` kayıtlar; sıralama: normalized tam eşleşme > prefix > substring, sonra usage_count |
| `GET /library/book-catalog/{id}` | detay + sections (label/test_count/topic) |
| `POST /books` (MEVCUT) | `template_id` artık global verified kaydı da kabul eder (`_get_owned_or_catalog_template`); katalogdan oluşturuldu ise `usage_count++` |
| `POST /library/book-catalog/contribute` | sihirbaz taslağından veya `book_id`'den → `pending` kayıt (normalized ad+yayınevi dedup: eşleşen verified/pending varsa `already_in_catalog` bilgisiyle sessiz geç) |

### Süper admin (admin router, `_require_super_admin` + audit)
| Uç | İş |
|---|---|
| `GET /admin/book-catalog?status=&q=` | liste + sayımlar (pending rozeti) |
| `POST /admin/book-catalog/read` | aynı okuma motoru (seed için PDF/foto) |
| `POST /admin/book-catalog` | oluştur (okuma taslağından veya elle) → doğrudan `verified` |
| `POST /admin/book-catalog/{id}` | düzenle (ad/yayınevi/tür/ders/sınıf/bölümler) |
| `POST /admin/book-catalog/{id}/verify` | pending → verified |
| `POST /admin/book-catalog/{id}/hide` · `/delete` | moderasyon (hide geri alınabilir; delete yalnız hiç kullanılmamışsa, aksi hide öner) |

Hata kodları mevcut sözleşmeyle: 404 `template_not_found` (cross-tenant sızıntı
yok) · 422 `not_a_toc` / `invalid_media_type` / `file_too_large` · 429
`daily_read_limit` · 409 `already_in_catalog`.

## 6. Koç UX — tık sayımlarıyla

**Sihirbaz Adım 1 (Bilgiler):**
- Kitap adı yazılırken (debounce 400ms) katalog araması; eşleşme varsa yeşil kart:
  *"Katalogda bulundu: 4K TYT Matematik — 4K Yayınları · 34 bölüm · 412 test
  [Yapısını kullan]"*. Tıklanınca yayınevi/tür/ders/sınıf formu dolar, Adım 2
  bölümlerle dolu gelir, Adım 3 eşleştirme (topic'ler katalogdan + auto-map).
- Opsiyonel **"Kapağı tarat"** butonu (kamera, `capture=environment`): ad
  yazmak yerine kapak fotoğrafı → identify → form + katalog araması otomatik.
- **En kısa yol: 3 tık** — ① ad yaz/kapak tarat → "Yapısını kullan" ② Adım 4'te
  öğrenci seç (opsiyonel) ③ "Oluştur". Birebir test sayıları + müfredat eşli.

**Sihirbaz Adım 2 (Üniteler) — yeni yöntem kartı "Fotoğraftan oku":**
- Mevcut üç yöntemin (Resmi konular / AI önerisi / Elle) yanına eklenir;
  katalogda eşleşme yoksa ÖNERİLEN olarak vurgulanır.
- Akış: ① foto çek/PDF yükle ("İçindekiler sayfasını çek — genelde 1-2 sayfa")
  → "iki kez okunuyor" spinner → ② önizleme tablosu (satır düzenlenebilir;
  şüpheli amber; okunamayan test sayısı boş + uyarı bandı; **"test sayısını
  tümüne uygula"** toplu aracı) → ③ "Uygula". **3 tık.**
- Toplu "tümüne uygula" aracı Resmi konular yoluna da eklenir (fotoğraf
  istemeyen koç için sabit-sayı düzeltmesini tek hamleye indirir — yara bandı).

**Katkı (contribute):**
- Kitap katalog eşleşmesi OLMADAN oluşturulduysa (foto/elle/resmi konular),
  Özet adımında işaretli checkbox: *"Bu kitabın yapısını ortak kataloğa öner —
  diğer koçlar tek tıkla kullanır (adın görünmez)"* → arka planda contribute.
  Ek tık maliyeti 0 (checkbox varsayılan açık, istemeyen kapatır).

**Görünürlük kuralı:** koç yalnız `verified` katalog kayıtlarını görür;
kendi kişisel şablonları (mevcut özellik) ayrı listede aynen durur.

## 7. Süper admin UX — `/admin/book-catalog` ("Kitap Kataloğu")

- admin-shell "Sistem" grubuna nav + **pending sayısı rozeti** (mevcut badge
  deseni `book_catalog_pending` — işleyince azalır: onayla/reddet → düşer).
- Sayfa: 3 KPI (Yayında / Onay bekleyen / Gizli) + arama + durum filtresi +
  tablo (ad · yayınevi · ders/sınıf · bölüm/test toplamı · kaynak rozeti
  [seed/koç katkısı] · kullanım sayısı · durum).
- **"Yeni kitap (PDF/fotoğraftan)"** dialogu: dosya yükle → okuma → önizleme
  tablosu (düzenlenebilir) + üst bilgiler → "Kataloğa ekle (yayında)". Örnek
  PDF'lerle seed akışı budur — kitap satın alma GEREKMEZ.
- Pending satır: genişlet → bölümleri gör/düzelt → Onayla / Reddet (not'lu).
- Tüm moderasyon `BOOK_CATALOG_UPDATE` audit'i (op + before/after özeti).

## 8. Koruma rayları

- **Doğruluk:** çift okuma + şüpheli işaretleme + zorunlu önizleme; katalogda
  yalnız admin onaylı veri; `verified` kayıtta bile koç Adım 2'de düzeltebilir
  (kitap baskıları farklı olabilir — düzeltme koçun kendi kitabını etkiler,
  kataloğu DEĞİŞTİRMEZ).
- **İzolasyon:** kişisel şablon ↔ katalog ayrımı her sorguda explicit
  (`catalog_status IS NULL` vs `= 'verified'`); smoke testleri cross-erişimi
  kapsar. Contribute'ta koça ait kişisel veri taşınmaz (yalnız yapı + builtin
  topic bağları).
- **Kötüye kullanım:** okuma tavanı 30/gün/koç; contribute dedup (spam pending
  birikmez); pending kuyruğu yalnız admin görür.
- **KVKK/telif:** kişisel veri yok (`personal_data=False`); olgusal yapı verisi;
  kaynaklar koçun kendi kitabı veya yayınevinin kamuya açık tanıtım PDF'i.
- **Maliyet güvencesi:** ücretsiz anahtar havuzu önce; 0 kredi ama UsageEvent
  ölçümü sayesinde hacim admin panosunda izlenir; taşarsa tavan indirilir.

## 9. Test planı

1. `scripts/test_ai_book_structure.py` (~12): merge hizalama · test_count
   çelişkisi → suspect · null test_count korunur (uydurma yok) · not_a_toc ·
   dosya kapıları · tek-okuma fallback (Gemini monkeypatch).
2. `scripts/test_api_v2_book_catalog.py` (~25): arama sıralaması + normalized
   eşleşme · verified-only görünürlük (pending/hidden koça görünmez) · kişisel
   şablon katalog aramasına sızmaz + katalog kaydı kişisel listeye sızmaz ·
   `POST /books` global template ile bölüm+topic kopyalar + usage_count++ ·
   contribute → pending + dedup 409 · admin CRUD/verify/hide + audit ·
   rol kapıları (koç admin ucuna 403, anonim 401) · okuma tavanı 429.
3. Regresyon: `teacher_library` 24 · `book_grid_release_aware` 17 ·
   `curriculum_mapping` 18 · `tenant_isolation` 29 · web `tsc`+`eslint`.
4. **Gerçek doğrulama:** `scripts/sim_book_structure_real.py` — 2-3 gerçek
   içindekiler kaynağıyla (koçun kitabından foto + yayınevi örnek PDF'i)
   gerçek Gemini benchmark'ı; bölüm sayısı + test toplamı belgeyle birebir
   karşılaştırılır (exam_import benchmark deseni).
5. Playwright canlı: sihirbaz 3-tık katalog akışı · fotoğraftan oku önizleme ·
   contribute → admin pending → onay → ikinci koçta görünme (uçtan uca döngü).

## 10. Aşamalar ve deploy

1. **A1 — Çekirdek:** migration (onaya sunulur → uygulanır) + model + okuma
   motoru + koç/admin uçları + smoke 1-2.
2. **A2 — Admin seed:** `/admin/book-catalog` UI + rozet + audit; ilk 10-20
   popüler kitap örnek PDF'lerden seed edilip gerçek benchmark koşulur.
3. **A3 — Koç sihirbazı:** katalog kartı + kapak tarat + "Fotoğraftan oku"
   yöntemi + toplu uygula + contribute; Playwright.
4. **A4 — Deploy:** DB yedeği + web/worker/next rebuild; prod'da migration
   `upgrade head`; canlı smoke (uçlar 401/200, admin sayfa, örnek okuma).

Mobil: BİLİNÇLİ yok (kütüphane yönetimi web-only — PARITY.md notu güncellenir;
koç telefon fotoğrafını web sihirbazından `capture=environment` ile çeker).

## 11. Bu tasarımda verilmiş kararlar

- Katalog `BookTemplate` genişletmesiyle kurulur (yeni paralel tablo YOK) —
  kitap oluşturma yolu değişmez, kod yüzeyi küçük kalır.
- Okuma KREDİSİZ (0 kredilik ölçüm satırı + 30/gün tavan).
- Kapak görseli saklanmaz; kapağın tek rolü tanıma.
- Koç katkısı anonim + daima pending; verified rozetini yalnız admin verir.
- Verified kayıt topic eşleştirmelerini de taşır (builtin topic'ler global).
- Rakip sistemden veri çekilmez (hukuki + teknik risk — araştırma raporu:
  hazır API Türkiye'de yok; sohbet 2026-08-10).
