"""ETÜTKOÇ Rotam — Sistem Özellikleri PDF'i oluşturma scripti.

Tüm rollere göre (Öğrenci, Öğretmen, Veli, Kurum Yöneticisi, Süper Admin)
sistem üzerinde yapılabilecek tüm işlemleri listeleyen kapsamlı kullanıcı
referansı. Çıktı: D:\\LGS-Program\\ETUTKOC_Rotam_Sistem_Ozellikleri.pdf
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from fpdf import FPDF


OUT = Path(__file__).resolve().parent.parent / "ETUTKOC_Rotam_Sistem_Ozellikleri.pdf"


# ============================================================================
# İçerik tanımları — her rol için kategori + özellik listesi
# ============================================================================


STUDENT_SECTIONS = [
    ("Kayıt, Oturum ve Profil İşlemleri", [
        ("Bağımsız öğrenci kaydı",
         "Davetiye olmadan e-posta + şifre ile öğrenci hesabı açma. KVKK onayı zorunlu."),
        ("Davetiyeli kayıt",
         "Öğretmen tarafından gönderilen davet linki üzerinden hesap açma; sınıf ve ders programı otomatik."),
        ("Oturum açma / kapatma",
         "E-posta + şifre. 5 başarısız denemede hesap geçici kilitlenir."),
        ("Şifre değiştirme",
         "Mevcut şifre + yeni şifre. İlk girişte zorunlu değişim akışı."),
        ("Hesap bilgilerim",
         "Kendi profilini görüntüleme; KVKK haklarına göre veri ihracı (export) ve silme talebi açma."),
        ("Veri ihracı talebi",
         "Tüm kişisel verilerin JSON dosyası olarak indirilebilmesi (KVKK madde 11)."),
        ("Hesap silme talebi",
         "30 günlük grace period ile hesap silme talebi. İptal edilebilir; süper admin onayında uygulanır."),
    ]),
    ("Günlük / Haftalık Program", [
        ("Günlük görünüm",
         "Seçilen güne ait görevler, ders bazında planlama özeti, 30 günlük trend grafiği."),
        ("Haftalık görünüm",
         "7 günlük program penceresi, gün bazında planlanan/tamamlanan dağılımı."),
        ("Haftalık veli raporu (yazdırılabilir)",
         "Veliye paylaşılabilir A4 yazdırılabilir özet — ders kırılımı, başarı yüzdeleri."),
        ("Geçmiş gün navigasyonu",
         "Önceki/sonraki gün ve hafta okuna tıklayarak hızlı geçiş."),
    ]),
    ("Görev İşlemleri", [
        ("Görevi tek tıkla tamamlama",
         "Görev kartında 'Tamamlandı' butonu; tüm soru sayısı tamamlanmış sayılır."),
        ("Görev tamamlamayı geri alma",
         "Yanlışlıkla tamamlanan görevi geri açma (pending duruma çevirir)."),
        ("Kalem bazında ilerleme",
         "Kitap öğesi başına 'şu kadar soru çözdüm' girerek kısmi tamamlama (partial)."),
        ("Görev değişikliği talebi",
         "Planlanan sayıyı azalt/artır, kitabı veya bölümü değiştir, görevden çıkar — öğretmen onayı ile."),
        ("Yeni görev ekleme talebi",
         "Programa olmayan ek bir görev önerisi gönder; öğretmen kabul/red verir."),
        ("Görev hakkında soru sorma",
         "Belirli bir görevle ilgili öğretmene mesaj gönderme; öğretmen cevap yazınca bildirim alır."),
        ("Talep geri çekme",
         "Henüz öğretmen cevaplamadıysa açılmış talebi iptal etme."),
    ]),
    ("Kitap ve Bölüm Görünümü", [
        ("Kitap envanteri",
         "Atanan tüm kitapların ders bazında listesi, kalan/tamamlanmış yüzdeleri."),
        ("Kitap detay (sinema-koltuk grid)",
         "Seçilen kitabın tüm bölümlerinin renk kodlu görselleştirilmesi (tamamlanan/kalan)."),
        ("Önceden çözülmüş test bilgisi",
         "Öğretmenin atama anında belirttiği baseline — sıfırdan başlamayan kitaplar."),
    ]),
    ("Aralıklı Tekrar (Spaced Repetition)", [
        ("Bugünkü tekrar kartları",
         "Vadesi gelmiş veya gecikmiş tekrar kartlarının listesi; konu, ders ve durum etiketi."),
        ("Kart değerlendirmesi",
         "Her kart için 4 seviye puan (Tekrar / Zor / İyi / Kolay). FSRS algoritması bir sonraki tekrar tarihini hesaplar."),
        ("Kart durumu özeti",
         "Yeni / Öğreniyor / Tekrar / Yeniden-öğreniyor kategorilerinde toplam sayı."),
    ]),
    ("Çalışma DNA ve Burnout (Stage 13)", [
        ("Çalışma DNA profili",
         "7×24 saatlik çalışma ısı haritası, en verimli saat dilimi (kronotip), haftalık trend."),
        ("Burnout sinyalleri",
         "5 sinyal: gece kuşu, hafta sonu mola yok, yoğunluk artışı, tamamlama düşüşü, streak kırılması. Risk skoru 0-100."),
    ]),
    ("Pomodoro Odak ve Gamification (Stage 14)", [
        ("Pomodoro session başlatma",
         "Planlanan süre (5-120 dk), tür (work/break), etiket gir. Sayaç sunucu zamanına göre çalışır."),
        ("Pomodoro session bitirme",
         "Gerçekleşen süre + kesinti durumu (interrupted). Otomatik rozet kontrolü tetiklenir."),
        ("Bugün özeti",
         "Bugünkü iş dakikası, session sayısı, kesintili sayısı, mola dakikası."),
        ("Streak göstergesi",
         "Kesintisiz aktif gün sayısı; en uzun streak ve mevcut streak."),
        ("Puan sistemi",
         "Görev × 10 + pomodoro × 5 + tekrar × 2 + rozet × 25 puan hesaplaması."),
        ("Rozet galerisi",
         "10 rozet: ilk adım, streak 3/7/30, görev maratonu, erken kuş, pomodoro pro, hafta sonu savaşçısı, tekrar ustası, yüzlerin kulübü. Kazanılmış + kilitli görünüm."),
    ]),
    ("Hedef Yönetimi", [
        ("Hedef ağacı görünümü",
         "Sınav hedefi → ders hedefleri → alt hedefler. Durum (devam/tamamlandı/terk) ve ilerleme çubuğu."),
        ("Hedef ilerleme güncellemesi",
         "Yaprak hedef için sayısal değer (örn. deneme puanı) girerek mevcut durumu güncelleme."),
        ("Hedef özeti",
         "Toplam hedef sayısı, tamamlanan oranı, devam eden ders hedefleri."),
    ]),
    ("Veli Paylaşımı", [
        ("Veli daveti onayı",
         "Öğretmenin gönderdiği veli daveti üzerinden ebeveynin sisteme katılması — öğrenci tarafında onay gerekmez."),
        ("Haftalık raporu yazdırma",
         "Haftalık programı PDF olarak yazdırıp veliye verme."),
    ]),
    ("Mobile API (API v1) — JSON Endpoint'ler", [
        ("Bugünkü görevler (JSON)",
         "GET /api/v1/student/today — mobile uygulama için JSON görev listesi ve özet."),
        ("Görev tamamlama (mobile)",
         "POST /api/v1/student/tasks/{id}/complete — tek tıkla tamamlama."),
        ("Review kartları (JSON)",
         "GET /api/v1/student/review — vadesi gelmiş kartlar + breakdown."),
        ("Rating gönderme (mobile)",
         "POST /api/v1/student/review/{id} — JSON body ile 1-4 puan."),
        ("Pomodoro kontrol (mobile)",
         "GET /api/v1/student/focus + POST /focus/start, /focus/{id}/end."),
        ("Profil bilgisi",
         "GET /api/v1/me — JWT token ile mevcut kullanıcı bilgisi."),
    ]),
]


TEACHER_SECTIONS = [
    ("Kayıt, Oturum ve Plan", [
        ("Bağımsız öğretmen kaydı",
         "E-posta + güçlü şifre ile kayıt. 14 günlük Solo Pro deneme otomatik başlar."),
        ("Davetiyeli kayıt",
         "Kurumun gönderdiği davet linki üzerinden kayıt; institution_id otomatik atanır."),
        ("Mevcut plan / deneme durumu",
         "Aktif plan, deneme kalan gün, plan geçmişi, bir sonraki yenileme tarihi."),
        ("Fiyatlandırma görünümü",
         "Solo / Kurum planları + add-on'lar (WhatsApp Veli, AI Plus, Veli Portal). Plan karşılaştırma."),
        ("Add-on yönetimi",
         "WhatsApp Veli + AI Plus + Veli Portal aktive / iptal etme."),
    ]),
    ("Öğrenci Yönetimi", [
        ("Öğrenci listesi",
         "Tüm öğrenciler, sınıf/alan/aktiflik filtreleri, yeni ekleme butonu."),
        ("Manuel öğrenci oluşturma",
         "Ad, e-posta, sınıf (5-12 / Mezun), alan (Sayısal/EA/Sözel/Dil), akademik yıl, sınav hedefi."),
        ("Toplu CSV ithalatı",
         "CSV ile çoklu öğrenci yükleme. Önizleme + hata satırı raporu. Geçici şifreler otomatik üretilir."),
        ("Öğrenci detay",
         "Snapshot (bugün/hafta), ders dağılımı, 30 günlük trend, kitap envanteri, veliler, öğretmen notları."),
        ("Öğrenci düzenleme",
         "Ad, e-posta, sınıf, alan, sınav hedefi, müfredat modeli güncelleme."),
        ("Sınıf yükseltme / mezun etme",
         "Öğrenciyi bir üst sınıfa veya mezun durumuna geçirme; akademik yıl güncellemesi."),
        ("Öğrenciyi pasifleştirme",
         "is_active=False — hesabı kapat, veri saklanır."),
    ]),
    ("Akademik Yıl ve Dönem", [
        ("Akademik yıl oluşturma",
         "Yıl başlangıç-bitiş; otomatik ad üretimi (2025-2026)."),
        ("Akademik dönem (faz) oluşturma",
         "Dönem adı, başlangıç/bitiş, tür: Olağan / Yarıyıl Tatili / Yaz Kampı / Sınav Hazırlık."),
        ("Yaz kampı yönetimi",
         "Tatil dönemleri ve yaz kampı dönem-tipi; programa farklı oran uygulanır."),
    ]),
    ("Program / Görev Yönetimi", [
        ("Haftalık program görünümü",
         "Seçili öğrencinin 7 günlük programı, gün bazında özet, ders dağılımı."),
        ("Günlük kart (expandable)",
         "Bir gün için tüm görevler, öğrenme motoru önerileri, maturity skoru."),
        ("Görev oluşturma",
         "Tarih, başlık, tür (test/video/özet/tekrar), kitap + bölüm + planlanan sayı."),
        ("Görev düzenleme",
         "Başlık, kitap, bölüm, sayı, tür değişikliği — açılan formdan."),
        ("Görev silme",
         "Kitap rezervasyonunu serbest bırakır."),
        ("Toplu görev önerisi (öğrenme motoru)",
         "Öğrencinin geçmiş davranışından otomatik öneri seti — kabul/red ile göreve dönüşür."),
        ("Öneri kabul/red",
         "Maturity skoru ve gerekçeyle gelen öneriyi tek tıkla göreve çevir veya feedback ile reddet."),
        ("Tanı paneli (diagnostics)",
         "Öğrencinin öğrenme modeli iç verisi: en sık çalışılan gün/ders, tipik sayı, güven skoru."),
    ]),
    ("Kitap / Soru Bankası", [
        ("Kitap kütüphanesi",
         "Tüm kitaplar; ders/tip/sınıf seviyesine göre filtre + arama."),
        ("Kitap oluşturma",
         "Ad, yayınevi, tür (Soru Bankası / Fasikül / Konu Anlatımlı / Branş Denemesi / Genel Deneme), hedef sınıf aralığı, mezun uyumu."),
        ("Bölüm yönetimi",
         "Kitaba bölüm ekle (etiket + konu + soru sayısı); tek-tek veya kataloglardan toplu."),
        ("Kataloglardan ünite toplu seçme",
         "MEB müfredatına göre konu ağacından bölümleri kitaba bir tıkla ekleme."),
        ("Kitap silme",
         "Atanmadıysa hard delete; aksi halde soft delete."),
        ("Kitap setleri (template'ler)",
         "Sınıf seviyesine göre kitap paketleri; tek tıkla öğrenciye toplu atama."),
        ("Öğrenciye kitap atama",
         "Seçili kitabı öğrenciye ekle; önceden çözülmüş test sayısını baseline olarak kaydet."),
        ("Atamadan çıkarma",
         "Kitabı öğrencinin envanterinden çıkar (ilerleme bilgisi korunur)."),
    ]),
    ("AI ve İçgörü", [
        ("AI içerik önerileri",
         "Öğrencinin geçmişine göre akıllı görev önerileri (AI Plus add-on)."),
        ("Filo geneli içgörüler",
         "Tüm öğrencilerin trendi, dikkat çeken paternler."),
    ]),
    ("Analitik / Raporlar", [
        ("Öğretmen dashboard",
         "Filo özet (kırmızı/sarı/yeşil), bugün/hafta özetleri, bekleyen talepler, at-risk uyarıları."),
        ("Öğrenci snapshot",
         "Bugün/hafta planlama-tamamlama, 7/30g başarı oranı, uyarılar, ders dağılımı."),
        ("Ders bazında istatistik",
         "Planlama vs tamamlama, eksik konular, performans sıralaması."),
        ("30 günlük trend grafikleri",
         "Çizgi grafikler — tamamlanan vs planlanan günlük seri."),
        ("Konu bazında doğruluk",
         "TaskBookItem.correct_count / wrong_count toplama — yanlış öğrenilen konuların tespiti."),
        ("Risk paneli (at-risk)",
         "Risk puanı sıralı öğrenci listesi; sustur (mute) / aç (unmute)."),
        ("At-risk mute kaldırma",
         "7 günlük geçici susturmayı iptal etme."),
    ]),
    ("Spaced Repetition Yönetimi", [
        ("Review dashboard",
         "Tüm öğrencilerin tekrar yükü, acil müdahale sıralaması."),
        ("Öğrencinin kart durumu",
         "Seçili öğrencinin tüm kartları, durum breakdown, takvim."),
        ("Toplu kart ekleme (seed)",
         "Bir ders seçerek o dersin tüm konularını öğrenciye review kartı olarak ekle (idempotent)."),
    ]),
    ("Çalışma DNA ve Burnout (Öğretmen Görünümü)", [
        ("Öğrencinin DNA profili",
         "Öğrencinin çalışma haritası, kronotipi, burnout sinyalleri."),
        ("Burnout paneli (filo)",
         "Tüm öğrencilerin risk puanı, kritik öğrenciler, sinyal kırılımı."),
    ]),
    ("Pomodoro ve Gamification (Öğretmen Görünümü)", [
        ("Öğrencinin odak istatistikleri",
         "Bugün dakika, session sayısı, streak, puanlar, rozetler, 30 günlük iş dakikası."),
        ("Rozet listesi",
         "Öğrencinin kazandığı rozetler, kazanım tarihleri."),
    ]),
    ("Hedef Yönetimi", [
        ("Hedef ağacı (öğretmen görünümü)",
         "Sınav hedefi → ders → alt hedefler. Öğretmen oluşturabilir, düzenleyebilir, tamamladı işaretler."),
        ("Otomatik hedef seed",
         "Öğrencinin sınav hedefinden ders hedeflerini bir tıkla otomatik türetme."),
        ("Hedef oluşturma",
         "Başlık, tür (sınav hedefi / ders hedefi / özel), hedef değer, son tarih, birim (puan / soru sayısı)."),
        ("Hedef güncelleme",
         "Tüm alanları değiştir; ilerleme manuel veya otomatik."),
        ("Hedefi tamamlandı / terk işaretle",
         "Status: ACHIEVED veya ABANDONED."),
        ("Hedef silme",
         "Hedefi kalıcı kaldır (log'da kalır)."),
    ]),
    ("Veli İletişimi", [
        ("Veli davet etme",
         "Öğrenci için veli e-postası + ilişki (anne/baba/diğer) gir; davet token gönder."),
        ("Davet iptali",
         "Kullanılmamış daveti expire et."),
        ("Veli bağını kaldırma",
         "Aktif veli linkini sonlandır (veli hesabı kalır)."),
        ("Öğretmen notu (veliye)",
         "Seçili öğrenci hakkında veliye not yaz; bildirim olarak iletilir."),
        ("Veli iletişim geçmişi",
         "Öğrenci başına veliye gönderilen notlar listesi."),
    ]),
    ("Öğrenci Talep Yönetimi", [
        ("Talep listesi",
         "Tüm öğrencilerin gönderdiği talepler (CHANGE/REPLACE/REMOVE/ADD/QUESTION); pending/onaylandı/reddedildi filtresi."),
        ("Talebi onayla",
         "Form: cevap (opsiyonel), notlar. Görev otomatik güncellenir."),
        ("Talebi reddet",
         "Reddetme gerekçesi + cevap; öğrenci bildirim alır."),
        ("Soruya cevap ver",
         "Öğrencinin sorduğu soruya yazılı cevap yazma."),
    ]),
    ("Ayarlar / Profil", [
        ("Bildirim cron zamanlaması",
         "Günlük özet, haftalık rapor, düşüş uyarısı cron'larının saat ayarı (TR saati gösterimi)."),
        ("Test e-postası gönder",
         "Ayar testi için örnek bildirim gönderme."),
        ("Kredi paneli (bağımsız öğretmen)",
         "Aylık kredi tüketim, uyarı/kilitlenme banner'ları, eski dönem geçmişi."),
        ("WhatsApp opt-in",
         "Aktive edilen WhatsApp Cloud API ile veli bildirim kanalı."),
    ]),
    ("Mobile API (API v1) — Öğretmen JSON Endpoint'leri", [
        ("Öğrenci listesi (JSON)",
         "GET /api/v1/teacher/students — özet bilgiler ile öğrenci listesi."),
        ("Öğrenci detay (JSON)",
         "GET /api/v1/teacher/students/{id} — snapshot + uyarılar JSON."),
    ]),
]


PARENT_SECTIONS = [
    ("Kayıt ve Daveti Kabul", [
        ("Davet linkine erişim",
         "Öğretmenin gönderdiği davet URL'i ile davet bilgisini görme (öğrenci adı, ilişki tipi)."),
        ("Daveti kabul + hesap aç",
         "Ad-soyad, şifre, KVKK onayı. Mevcut PARENT hesabınız varsa link eklenir, yoksa yeni hesap açılır."),
    ]),
    ("Dashboard ve Çocuk Görünümü", [
        ("Veli ana paneli",
         "Bağlı tüm çocukların özet kartları (tamamlama yüzdesi, risk durumu)."),
        ("Çocuk detay sayfası (read-only)",
         "Öğrencinin metrikler, haftalık tamamlama, ders bilgileri, öğretmen notları."),
        ("Çocuk haftalık programı",
         "Seçili haftanın görevleri ve durumu — sadece okuma."),
    ]),
    ("Bildirimler", [
        ("Bildirim geçmişi",
         "Son 100 bildirim (email/WhatsApp) — başlık, içerik, gönderim zamanı."),
        ("Tek tıkla bildirim kapatma",
         "Token-tabanlı unsubscribe linki ile login yapmadan tüm bildirimleri kapatabilme."),
    ]),
    ("Bildirim Tercihleri", [
        ("Ayarlar sayfası",
         "Mevcut tercih durumları ve sessiz saatler (do-not-disturb)."),
        ("Bildirim türü toggle",
         "7 tür: günlük özet, haftalık rapor, boş gün uyarısı, yeni program, düşüş uyarısı, öğretmen notu, sınav uyarısı."),
        ("Sessiz saatler",
         "HH:MM-HH:MM aralığında bildirim almama (ör. 22:00-08:00)."),
        ("Çocuk başına mute",
         "Belirli bir öğrenci için tüm bildirimleri kapatma (boşanma vb. durumlar için)."),
    ]),
    ("WhatsApp Doğrulama", [
        ("Telefon ekleyip OTP isteme",
         "+90... veya 0532... formatında telefon. 60sn cooldown, 6 haneli kod gönderilir."),
        ("OTP doğrulama",
         "6 haneli kodu gir; 5 deneme limiti, 10 dakika geçerlilik. Brute-force koruma."),
        ("WhatsApp kanalını kapat",
         "Telefon kaydını sil; doğrulama düş, WhatsApp bildirimi kesilir."),
    ]),
    ("Yasal", [
        ("KVKK aydınlatma metni (Veli)",
         "Public erişimli aydınlatma sayfası; auth gerektirmez."),
    ]),
]


INSTITUTION_ADMIN_SECTIONS = [
    ("Kurum Profili ve Abonelik", [
        ("Kurum dashboard",
         "Risk panelinde kritik öğrenci sayısı, pasif öğretmen uyarısı, hızlı erişim panelleri."),
        ("Abonelik yönetimi",
         "Mevcut plan (akademik yıl / aylık), yaz pause durumu, 60 günlük performans garantisi."),
        ("Aylıktan akademik yıla geçiş",
         "Plan tipini akademik yıl tabanlı olarak değiştir."),
        ("Yaz pause moduna geçme",
         "Temmuz-Ağustos arası fatura pause edilebilir; sadece tarih penceresinde aktif."),
        ("Pause'dan devam",
         "Manuel olarak pause'dan çıkış; ödeme dönemine devam."),
        ("Performans garantisini aktive et",
         "60 günlük performans garantisi etkinleştirme; başarı kriterleri sağlanmazsa iade hakkı."),
    ]),
    ("Öğretmen Yönetimi", [
        ("Öğretmen listesi",
         "Tüm öğretmenler tablosu (ad, öğrenci sayısı, son aktivite, statü)."),
        ("Öğretmen ekleme",
         "Ad + e-posta; sistem güçlü geçici şifre üretir, ilk girişte değişim zorunlu. Kuota kontrolü."),
        ("Öğretmen kartı",
         "Öğretmenin roster (öğrenci ad/sınıf), haftalık tamamlama oranları. Programa link YOK (gizlilik)."),
        ("Öğretmeni pasifleştirme",
         "is_active=False; login engellenir, veri korunur."),
        ("Öğretmeni aktifleştirme",
         "Pasif öğretmeni geri etkinleştirme."),
    ]),
    ("Davetiye Yönetimi", [
        ("Davetiye listesi",
         "Tüm davetler (pending/accepted/revoked/expired) durumları."),
        ("Davetiye oluşturma",
         "Ad + e-posta (boş bırakılırsa açık davet); kuota kontrolü ile token oluştur."),
        ("Davetiyeyi iptal etme",
         "Bekleyen daveti revoke; token geçersizleşir."),
    ]),
    ("Roster ve Öğrenci Görünümleri", [
        ("Kurum roster",
         "Tüm aktif öğrenciler; öğretmen, sınıf ve alan filtreleri."),
        ("Risk paneli (kurum)",
         "Tüm öğrenciler arasında risk skoru sıralı tablo. Öğretmen-öğrenci eşlemesi görünür."),
    ]),
    ("Agrega Analitik Paneller", [
        ("Aktivite ısı haritası",
         "Öğretmen aktiviteleri (login, görev oluşturma, veli notu) — son 4 veya 12 hafta heatmap."),
        ("Aktivite haritası yazdırılabilir (A4 landscape)",
         "Yatay A4 PDF olarak indirme/print."),
        ("Kohort karşılaştırması",
         "4 sekme: sınıf seviyesi / alan (11+/Mezun) / müfredat modeli / hedef sınav. Hafta-hafta (WoW) değişim."),
        ("Kohort yazdırılabilir",
         "4 kohort tipinin birleşik A4 landscape raporu."),
        ("At-risk raporu yazdırılabilir",
         "Risk altındaki öğrenciler tablosu A4 portrait."),
    ]),
    ("Haftalık Yönetici Özeti (Admin Digest)", [
        ("Özet arşivi",
         "Son 12 haftanın yönetici özet listesi; manuel tetikleme butonu."),
        ("Şimdi gönder",
         "Bu haftanın özetini hemen email ile kuruma gönder (idempotent)."),
        ("Özet detayı",
         "Tek bir hafta özeti — toplam görev, tamamlama oranı, risk öğrenci sayısı, öğretmen aktivitesi."),
    ]),
    ("Kuota ve Kredi", [
        ("Kuota dashboard",
         "Öğretmen / öğrenci / admin sayımları + plan limitleri."),
        ("Kredi kullanım paneli",
         "Aylık kredi tüketim, tür bazlı kırılım (bildirim, AI, vs.), günlük seri, son 50 olay."),
    ]),
]


SUPER_ADMIN_SECTIONS = [
    ("Sistem Dashboard", [
        ("Ana panel",
         "Sistem geneli sayım: kurum, kullanıcı (rol bazlı), kurum sağlık özeti, en kritik 3 kurum, son 10 audit, 24h başarısız login."),
    ]),
    ("Kurum Yönetimi (CRUD)", [
        ("Kurum listesi",
         "Tüm kurumlar, sağlık skoru sıralı; filtreler (health/name/created)."),
        ("Kurum oluşturma",
         "Ad, slug, e-posta, plan (free default)."),
        ("Kurum detayı",
         "Temel bilgi, öğretmen listesi, kurum admin'leri, öğrenci sayısı, sağlık skoru."),
        ("Kurum düzenleme",
         "Ad, e-posta, plan (free/pro/enterprise), is_active."),
        ("Kurum silme (soft)",
         "Soft delete; bağlı kullanıcılar bağımsız olur."),
        ("Kurum verisi backup (JSON)",
         "Tüm kurum verisinin JSON dosyası olarak indirme (password REDACTED, 30g bildirim, 90g audit)."),
    ]),
    ("Kullanıcı Yönetimi (CRUD)", [
        ("Tüm kullanıcılar",
         "Filtre: rol, kurum, isim/e-posta arama (limit 500)."),
        ("Kullanıcı oluştur",
         "Ad, e-posta, rol, kurum (kurum admin için zorunlu). Rol-bazlı güçlü şifre üretimi."),
        ("Kullanıcı detayı",
         "Temel bilgi, kurum, son audit olayları (10)."),
        ("Kullanıcı düzenle",
         "Ad, e-posta, kurum, is_active."),
        ("Şifre sıfırla",
         "Geçici şifre üret, kilit aç (failed_login_count=0)."),
        ("Rol değiştir",
         "Yeni rol seç + kurum güncelle. Kendini değiştiremez."),
        ("Kullanıcı sil",
         "Hard delete (kendi hesabını silemez)."),
    ]),
    ("Sahte Oturum (Impersonate)", [
        ("Kullanıcı olarak gir",
         "Başka bir kullanıcı olarak oturum aç; session impersonator_id kaydedilir. Audit: IMPERSONATE_START."),
        ("Sahte oturumu sonlandır",
         "Admin hesabına geri dön. Audit: IMPERSONATE_END."),
    ]),
    ("Audit Log", [
        ("Log listesi",
         "Filtreler: action, actor_id, tarih aralığı. 50/sayfa pagination."),
    ]),
    ("Sistem Kullanım", [
        ("Kullanım paneli",
         "Tüm kurumlar + bağımsız öğretmenler kredi tüketim tablosu."),
        ("Hard-block toggle",
         "Kurum kredi engelini aç/kapat."),
        ("Bonus kredi ekleme",
         "Kuruma veya bağımsız öğretmene manuel bonus (1-100000 aralığı)."),
    ]),
    ("Feature Flags", [
        ("Flag listesi",
         "Tüm flag'ler; global durum + override sayısı."),
        ("Flag detayı",
         "Global durum + kurum-spesifik override'lar."),
        ("Global toggle",
         "enabled_globally değerini ters çevirme."),
        ("Override ekle",
         "Belirli bir kurum için bu flag'i zorla aç/kapat."),
        ("Override sil",
         "Override'ı sil; global ayara döner."),
    ]),
    ("Sistem Duyuruları", [
        ("Duyuru listesi",
         "Aktif + geçmiş duyurular; severity (info/warning/error), audience, dismissible."),
        ("Duyuru oluşturma",
         "Başlık, mesaj, severity, audience (all/institutions/users), başlangıç-bitiş."),
        ("Duyuru silme",
         "Aktif duyuruyu kaldırma; cache invalidate."),
    ]),
    ("Kuota Yönetimi", [
        ("Kuota dashboard",
         "Tüm kurumlar kuota tablosu + override yönetimi."),
        ("Kuota override",
         "Kuruma özel kuota değeri (-1 sınırsız, 0 kapalı, 1-1M aralık)."),
        ("Override silme",
         "Plan default'una döndürür."),
    ]),
    ("Sistem Sağlığı", [
        ("Sağlık paneli",
         "Cron job durumu, dispatcher durumu, DB sağlığı snapshot'ı, ortalama gecikmeler."),
    ]),
    ("KVKK Yönetimi", [
        ("KVKK dashboard",
         "Talep durum sayımları, bekleyen (50) ve son (20) talepler."),
        ("Silme talebini hemen uygula",
         "Grace period (30g) atla, hemen sil. Geri alınamaz."),
        ("Talebi reddet",
         "Gerekçeyle (500 char) red; status=rejected."),
    ]),
    ("Yasal Sayfalar (Public)", [
        ("KVKK aydınlatma",
         "Madde 11 hakları (auth YOK, public)."),
        ("Gizlilik politikası",
         "Public erişimli policy sayfası."),
    ]),
]


# ============================================================================
# PDF üretimi
# ============================================================================


class FeaturesPDF(FPDF):
    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.add_font("Arial", "", "C:/Windows/Fonts/arial.ttf", uni=True)
        self.add_font("Arial", "B", "C:/Windows/Fonts/arialbd.ttf", uni=True)
        self.add_font("Arial", "I", "C:/Windows/Fonts/ariali.ttf", uni=True)
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(left=18, top=18, right=18)
        self.alias_nb_pages()
        self._is_cover = False

    def header(self) -> None:  # noqa: D401
        if self._is_cover or self.page_no() == 1:
            return
        self.set_font("Arial", "", 8.5)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, "ETÜTKOÇ Rotam — Sistem Özellikleri", border=0, align="L")
        self.cell(0, 8, f"Sayfa {self.page_no()} / {{nb}}", border=0, align="R")
        self.ln(10)
        self.set_text_color(0, 0, 0)

    def footer(self) -> None:  # noqa: D401
        if self._is_cover or self.page_no() == 1:
            return
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(
            0, 8,
            f"© {date.today().year} ETÜTKOÇ Rotam · Otomatik üretilmiş referans dokümanı",
            align="C",
        )
        self.set_text_color(0, 0, 0)

    # -------- helpers --------

    def h1(self, text: str, color: tuple[int, int, int] = (30, 64, 175)) -> None:
        self.ln(4)
        self.set_text_color(*color)
        self.set_font("Arial", "B", 18)
        self.multi_cell(0, 9, text, align="L")
        # underline bar
        self.set_draw_color(*color)
        self.set_line_width(0.8)
        y = self.get_y() + 1
        self.line(self.l_margin, y, self.l_margin + 30, y)
        self.set_text_color(0, 0, 0)
        self.ln(6)

    def h2(self, text: str) -> None:
        self.ln(2)
        self.set_text_color(15, 23, 42)
        self.set_font("Arial", "B", 12.5)
        self.multi_cell(0, 7, text, align="L")
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def feature_item(self, title: str, desc: str) -> None:
        # Sığma kontrolü — title + desc en az 12mm gerekiyor
        if self.get_y() > self.h - 30:
            self.add_page()
        self.set_font("Arial", "B", 10)
        self.set_text_color(15, 23, 42)
        # bullet + title
        self.cell(4, 5.5, "•", border=0)
        self.multi_cell(0, 5.5, title, align="L")
        self.set_font("Arial", "", 9.5)
        self.set_text_color(60, 60, 60)
        # Açıklama hafif indent
        cur_x = self.l_margin + 4
        self.set_x(cur_x)
        self.multi_cell(self.w - self.l_margin - self.r_margin - 4, 5, desc, align="L")
        self.set_text_color(0, 0, 0)
        self.ln(1.5)

    def role_intro(self, role_name: str, summary: str, color: tuple[int, int, int]) -> None:
        # Renkli accent bar arka plan
        self.set_fill_color(*color)
        self.rect(self.l_margin, self.get_y(), 4, 22, "F")
        # Başlık + özet
        self.set_xy(self.l_margin + 7, self.get_y() + 1)
        self.set_font("Arial", "B", 22)
        self.set_text_color(*color)
        self.cell(0, 10, role_name, ln=1)
        self.set_x(self.l_margin + 7)
        self.set_font("Arial", "", 10.5)
        self.set_text_color(70, 70, 70)
        self.multi_cell(self.w - self.l_margin - self.r_margin - 7, 5.5, summary)
        self.set_text_color(0, 0, 0)
        self.ln(6)

    def cover(self) -> None:
        self._is_cover = True
        self.add_page()
        # arka plan accent
        self.set_fill_color(30, 64, 175)
        self.rect(0, 0, self.w, 70, "F")
        # logo / başlık
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", "B", 30)
        self.set_xy(0, 22)
        self.cell(0, 12, "ETÜTKOÇ Rotam", align="C", ln=1)
        self.set_font("Arial", "", 14)
        self.cell(0, 8, "Sistem Özellikleri ve Kullanıcı Referansı", align="C", ln=1)
        # tarih bilgisi
        self.set_xy(0, 92)
        self.set_text_color(70, 70, 70)
        self.set_font("Arial", "", 10.5)
        self.cell(0, 6, f"Sürüm tarihi: {date.today().strftime('%d.%m.%Y')}", align="C", ln=1)

        # role özetleri
        self.set_xy(20, 110)
        self.set_text_color(15, 23, 42)
        self.set_font("Arial", "B", 14)
        self.cell(0, 8, "Bu belge nedir?", ln=1)
        self.set_font("Arial", "", 10.5)
        self.set_text_color(60, 60, 60)
        intro = (
            "ETÜTKOÇ Rotam; bağımsız öğretmenler ve eğitim kurumları için "
            "tasarlanmış, LGS / YKS hazırlık dönemi boyunca öğrencilerin "
            "günlük çalışma rotalarını yöneten, analitik ve veli iletişimi "
            "sağlayan bir platformdur. Bu belgede sistemin 5 farklı kullanıcı "
            "rolü için sağladığı tüm özellikler, kategorilere ayrılmış şekilde "
            "yapılabilen işlemlerle birlikte listelenmiştir."
        )
        self.multi_cell(0, 5.5, intro, align="J")

        # roller özet kutusu
        self.ln(8)
        self.set_x(20)
        self.set_font("Arial", "B", 14)
        self.set_text_color(15, 23, 42)
        self.cell(0, 8, "İçindekiler", ln=1)
        self.set_font("Arial", "", 10.5)
        self.set_text_color(60, 60, 60)
        toc = [
            ("1. Öğrenci", "Günlük rota, görev, tekrar, pomodoro, hedefler"),
            ("2. Öğretmen", "Öğrenci, kitap, program, analitik, AI, veli iletişimi"),
            ("3. Veli", "Çocuk görüntüleme, bildirim tercihleri, WhatsApp"),
            ("4. Kurum Yöneticisi", "Öğretmen yönetimi, kohort, agrega analitik, abonelik"),
            ("5. Süper Admin", "Kurum/kullanıcı CRUD, audit, feature flag, KVKK"),
        ]
        for title, desc in toc:
            self.set_x(20)
            self.set_font("Arial", "B", 10.5)
            self.cell(55, 6, title)
            self.set_font("Arial", "", 10.5)
            self.cell(0, 6, desc, ln=1)

        # API katmanı notu
        self.ln(8)
        self.set_x(20)
        self.set_fill_color(245, 247, 250)
        self.set_text_color(50, 50, 50)
        self.set_font("Arial", "B", 11)
        self.cell(0, 7, "Mobile API katmanı", ln=1, fill=True)
        self.set_font("Arial", "", 10)
        self.set_x(20)
        self.multi_cell(
            self.w - 40, 5.5,
            "Tüm öğrenci ve öğretmen işlemleri /api/v1 prefix'i altında JWT "
            "kimlik doğrulamalı JSON endpoint'ler olarak da kullanılabilir. "
            "Native mobile uygulaması, PWA veya 3rd-party entegrasyonları "
            "bu API katmanı üzerinden çalışır.",
            align="J",
        )
        self.set_text_color(0, 0, 0)
        self._is_cover = False

    def render_role(
        self,
        role_name: str,
        summary: str,
        sections: list[tuple[str, list[tuple[str, str]]]],
        color: tuple[int, int, int],
    ) -> None:
        self.add_page()
        self.role_intro(role_name, summary, color)
        total = sum(len(items) for _, items in sections)
        self.set_font("Arial", "I", 9.5)
        self.set_text_color(120, 120, 120)
        self.cell(
            0, 5,
            f"Toplam {len(sections)} kategori · {total} özellik",
            ln=1,
        )
        self.set_text_color(0, 0, 0)
        self.ln(2)
        for cat_title, items in sections:
            self.h2(cat_title)
            for title, desc in items:
                self.feature_item(title, desc)
            self.ln(2)


def main() -> None:
    pdf = FeaturesPDF()
    pdf.cover()

    pdf.render_role(
        "1. Öğrenci",
        "Öğrencinin sistem üzerinde yapabileceği tüm işlemler. Günlük rotanın "
        "takibinden, FSRS-tabanlı aralıklı tekrara, pomodoro odak modundan "
        "gamification ve hedef yönetimine kadar.",
        STUDENT_SECTIONS,
        color=(34, 139, 230),  # mavi
    )
    pdf.render_role(
        "2. Öğretmen",
        "Bağımsız veya kurum bünyesinde çalışan öğretmenin yapabileceği tüm "
        "işlemler. Öğrenci yönetiminden program oluşturmaya, AI içgörülerden "
        "veli iletişimine kadar tam erişim.",
        TEACHER_SECTIONS,
        color=(245, 124, 0),  # turuncu
    )
    pdf.render_role(
        "3. Veli",
        "Çocuğunun çalışma sürecini takip eden velinin görebileceği ve "
        "ayarlayabileceği işlemler. Read-only öğrenci görünümü, esnek bildirim "
        "tercihleri ve WhatsApp doğrulaması.",
        PARENT_SECTIONS,
        color=(56, 142, 60),  # yeşil
    )
    pdf.render_role(
        "4. Kurum Yöneticisi",
        "Eğitim kurumunun yöneticisi sıfatıyla yapılabilen işlemler. "
        "Öğretmen yönetimi, agrega panelle, abonelik ve performans garantisi. "
        "Öğretmen verilerinin detayına erişmez (gizlilik kuralı).",
        INSTITUTION_ADMIN_SECTIONS,
        color=(123, 31, 162),  # mor
    )
    pdf.render_role(
        "5. Süper Admin",
        "Sistem genelinde tam yetkili kullanıcının yapabileceği işlemler. "
        "Kurum/kullanıcı CRUD, audit log, feature flag, kuota, sistem "
        "sağlığı, KVKK talep yönetimi ve impersonate.",
        SUPER_ADMIN_SECTIONS,
        color=(198, 40, 40),  # kırmızı
    )

    pdf.output(str(OUT))
    print(f"[OK] PDF üretildi: {OUT}")
    total_features = sum(len(items) for _, items in (
        *STUDENT_SECTIONS, *TEACHER_SECTIONS, *PARENT_SECTIONS,
        *INSTITUTION_ADMIN_SECTIONS, *SUPER_ADMIN_SECTIONS,
    ))
    print(f"[INFO] Toplam özellik sayısı: {total_features}")


if __name__ == "__main__":
    main()
