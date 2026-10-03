# Koç (öğretmen) — bağımsız koç ve kuruma bağlı öğretmen

## Paket: hangi paket bana uygun?
chip: Hangi paket bana uygun?
rule: which
pages: /teacher/plan

Paket önerisi aktif öğrenci sayına göre yapılır: Patika 10, Rota 25 öğrenciye kadar, Zirve sınırsız. Ücretsiz Keşif 3 öğrencidir ve yapay zekâ kapalıdır.

## Paket: deneme bitince ne olur?
chip: Deneme bitince ne olur?
rule: trial_end
pages: /teacher/plan, /teacher/dashboard

14 günlük deneme bitince ödeme yapılmazsa ücretsiz pakete geçilir; veriler silinmez.

## Paket: ödemem neden geçmedi?
chip: Ödemem neden geçmedi?
rule: payment_failed
pages: /teacher/plan

Son ödeme denemesinin bankadan dönen sebebi sade dille anlatılır.

## Paket: abonelik yenileme
chip: Aboneliğim nasıl yenilenir?
rule: renew
pages: /teacher/plan

Web aboneliği kendiliğinden yenilenmez; bitişten 3 gün önce e-posta gelir, Paketim sayfasından ödenir. Erken ödeme kalan günleri yakmaz.

## Paket: iptal
chip: Aboneliği nasıl iptal ederim?
rule: cancel
pages: /teacher/plan

Paketim sayfasının altındaki "Diğer işlemler" bölümünden iptal edilir; dönem sonuna kadar her şey açık kalır.

## Paket: yapay zekâ kredisi
chip: Yapay zekâ kredim nasıl harcanıyor?
rule: credits
pages: /teacher/plan, /teacher/usage
link: /teacher/plan | Paketim

Karne okuma, seans içgörüsü, veli yorumu gibi işler kredi harcar; paket kredisi ay başında yenilenir.

## Paket: ödeme güvenliği
rule: pay_safe
pages: /teacher/plan

Ödeme yalnız kartla, iyzico 3D Secure ile alınır.

## Panel ve öğrencilerin durumu
chip: Panodaki renkler ne anlama geliyor?
pages: /teacher/dashboard, /teacher/students
link: /teacher/dashboard | Panoya git

Pano öğrencilerini üç duruma ayırır: Kritik (kırmızı), Uyarı (turuncu) ve Yolunda (yeşil). Kırmızı genelde programı bitmiş ya da programlı günleri üst üste boş geçen öğrencidir; turuncu tamamlama düşüşü, uzun süre giriş yapmama ya da bir dersi aksatma gibi uyarılardır. Uyarı Akışı'nda her uyarının "Neden?" açılır kanıtı vardır. Bir uyarıyı işlediysen "Gördüm" (3 gün) ya da "7 gün" ile erteleyebilirsin; koşul sürerse uyarı geri gelir, koşul düzelirse kendiliğinden kaybolur.

## Öğrenci ekleme
chip: Nasıl öğrenci eklerim?
pages: /teacher/students, /teacher/dashboard
link: /teacher/students | Öğrencilerim

Öğrenciler sayfasında "Yeni öğrenci" ile ad, e-posta ve sınıf girersin; sistem güçlü bir geçici şifre üretir, öğrenci ilk girişte şifresini değiştirir. Çok sayıda öğrenci için "Toplu işlemler → Listeden toplu ekle" ile CSV yükleyebilirsin; bu yolda şube, telefon ve veli bilgileri de girilebilir, veli e-postası varsa veli daveti otomatik gider. İçe aktarma bitince giriş kartlarını yazdırabilir ya da Excel'e indirebilirsin; geçici şifreler yalnız o ekranda bir kez gösterilir. Ücretsiz pakette 3 öğrenci sınırı vardır.

## Öğrenciyi pasife alma, yaz molası
chip: Öğrenciyi nasıl pasife alırım?
pages: /teacher/students

Öğrenci satırındaki üç nokta menüsünden ya da öğrenci sayfasındaki "İşlemler" menüsünden öğrenciyi pasife alabilir, yeniden aktif edebilirsin. Pasif öğrenci varsayılan listede görünmez, verisi silinmez. Yaz tatili gibi dönemler için "Yaz molası" uyarıları susturur ve öğrencinin ileri tarihli olmayan rezervlerini serbest bırakır; "Takibe devam" ile geri dönersin.

## Kütüphane: kitap ekleme
chip: Kütüphaneme nasıl kitap eklerim?
pages: /teacher/library, /teacher/library/new
link: /teacher/library/new | Kitap ekle

Kütüphane → Yeni kitap sihirbazı önce ne yapmak istediğini sorar: Hazır bir kitap ekle (yayın kataloğundan, test sayıları birebir gelir), Kitabım elimde, tarat (kapak ve içindekiler fotoğrafı ya da PDF; katalogda yoksa içindekiler okunur), Kendim tanımlayacağım (ünite ve test sayılarını elle girersin) ya da kendi şablonundan başla. Sonra bölümler müfredat konularına eşlenir ve kitap öğrencilere atanır. Kitabın test sayıları rezerv ve kalan test hesabının temelidir.

## Kitabı öğrenciye atama ve kitap setleri
pages: /teacher/library, /teacher/library/book-sets, /teacher/students
link: /teacher/library/book-sets | Kitap setleri

Kitabı öğrencinin Kaynaklar sekmesinden "Kitap ata" ile ya da kitap detayındaki öğrenciler bölümünden atarsın. Aynı kitapları birden çok öğrenciye vermek için kitap seti oluşturup "Öğrencilere uygula" ile şubeye göre topluca atayabilirsin. Öğrencinin daha önce çözdüğü testleri kitap panelindeki "çözülmüş test" alanına yazarsan programda tekrar atanmaz.

## Müfredat eşleştirme
chip: Müfredat eşleştirmesi ne işe yarar?
pages: /teacher/library

Kitap bölümlerini resmi müfredat konularına bağlamak; müfredat ilerlemesini, konu analizini ve öneri motorunu besler. Sistem birebir ya da öğrenilmiş eşleşmeleri kendisi yapar, emin olmadıklarını yapay zekâ önerisiyle sana sunar. Kitap detayındaki "Müfredata eşleştir" düğmesiyle tamamlarsın. Eşlenmeyen bölüm göreve engel değildir, yalnız analizlere girmez.

## Haftalık program kurma
chip: Haftalık programı nasıl hazırlarım?
pages: /teacher/students
link: /teacher/students | Öğrencilerim

Öğrencinin sayfasında "Haftalık Program"a gir. Yeni program açarken başlangıç ve bitiş tarihini seçersin (1-14 gün). Solda gün listesi, ortada seçili günün kartı, üstte haftanın ızgarası vardır. Görev eklerken bir konu yazarsın, kaynak (kitap) ve test sayısını seçersin; sistem koçun alışkanlığından adet önerir. Eklenen görevler önce taslaktır; öğrenci "Haftayı yayınla" dediğinde görür. Yayınlarken "Veliye duyur" ile veliye programın e-postası gider; neyin gideceğini önizleyip cümleleri düzenleyebilirsin.

## Rezerv ve kalan test
chip: Rezerv ve kalan test ne demek?
pages: /teacher/students, /teacher/library

Bir göreve test atadığında o testler kitapta öğrenci için ayrılır (rezerv). Kalan test = kitaptaki toplam − çözülen − rezerv. Böylece aynı testi iki kez vermezsin. Haftası geçmiş ama yapılmamış görevlerin rezervi her gece kendiliğinden serbest bırakılır. Kitabın sayısı yardımcıdır, engel değildir: dolu bölüme yine görev verebilirsin, sistem yalnız uyarır. Kitap ızgarasında "Sayaç uyumsuzluğu" görürsen "Sayaçları düzelt" ile onarırsın.

## Haftaya yay, taşı, kopyala
chip: Rutin görevi her güne nasıl veririm?
pages: /teacher/students

Bir görevi girip satırdaki takvim simgesiyle "Haftaya yay" dersen kalan günlere kopyalar; kaynak bölüm biterse kitabın sıradaki bölümünden devam eder. Hafta ızgarasında görevi sürükleyip başka güne taşıyabilir, Ctrl basılı bırakarak kopyalayabilir ya da sağ tıklayıp taşı, kopyala, sil yapabilirsin. Geçen haftadan yapılmayan blok ve etkinlik görevleri sağ şeritteki "Devret" bölümünden bu haftaya eklenir.

## Haftalık iskelet (kalıptan program)
chip: Haftalık iskelet nedir?
pages: /teacher/students

İskelet, öğrencinin haftanın her gününe hangi derslerin geldiğini tutan kalıptır. "İskelet oluştur" ile bu haftanın programından otomatik kurabilir ya da düzenleyebilirsin. Sonraki haftalarda boş günlerde kesikli "öneri" hücreleri çıkar; satıra tıklayınca dünün devamı, kitapta sıradaki konu, denemede yanlış yapılan konu gibi bilgili seçenekler gelir, tek tıkla göreve dönüşür. Paragraf ve problem gibi rutinler için "Rutinleri onayla" önce gün gün önizleme gösterir. Okul ya da dershane dönemi değişince yeni dönem açabilirsin.

## Müfredat paneli ve konuyu kapatma
pages: /teacher/students

Haftalık programdaki sağ şeritte Müfredat bölümü her konunun durumunu, çözülen testleri, doğruluğu, denemede o konudaki yanlışları ve kalan kapasiteyi gösterir. Konu bitti ise "Konuyu kapat" dersin; kapatılan konu önerilerde çıkmaz. "Kapatmadan önce bak" işareti denemede ya da arşivde açık yanlış olduğunu söyler.

## Deneme sonucu girme ve PDF karnesi
chip: Deneme sonucunu nasıl girerim?
pages: /teacher/students

Öğrencinin Denemeler sekmesinde elle toplam doğru, yanlış, boş girebilir ya da "PDF'ten aktar" ile yayınevi karnesini yükleyebilirsin. PDF iki kez okunur, sorular müfredat konularına eşlenir ve önizlemede kontrol edip kaydedersin; işlem 6 kredi harcar ve büyük karnelerde birkaç dakika sürebilir. Aynı karne ikinci kez yüklenirse sistem fark eder ve "var olanın yerine yaz" önerir. Kayıttan sonra Konu Analizi net fırsatlarını, ısı haritasını ve unutulan konuları gösterir.

## Deneme sonucunu veliye duyurma
pages: /teacher/students

Deneme satırındaki zarf simgesi veliye gidecek e-postanın önizlemesini açar: net, kıyas, koç yorumu, ders tablosu, önceki denemelerle karşılaştırma ve net fırsatları. Cümleleri düzenleyebilir, istemediğini silebilirsin; sayılar düzenlenemez. "PDF olarak indir" ile aynı içeriği WhatsApp'tan paylaşabilirsin. Duyurulmuş denemede gönderileni yeniden görüp PDF'ini alabilirsin.

## Yanlış soru arşivi
pages: /teacher/students

Öğrenci yanlış yaptığı soruların fotoğrafını Yanlışlarım bölümüne ekler; konu görev ya da kitaptan kendiliğinden gelir. Aralıklı iki doğru çözümde soru kapanır, yine yanlışsa yeniden açılır. Koç öğrencinin Yanlışlar sekmesinde biriken konuları, hata türlerini görür ve soruya açıklama yazabilir. Denemedeki yanlışlar "Yanlışlardan arşive soru seç" ile arşive eklenir.

## Seans kaydı
chip: Seans kaydı nasıl tutulur?
pages: /teacher/students, /teacher/appointments

Öğrencinin Seanslar sekmesinde "Yeni seans" ile görüşmeyi kaydedersin: gündem zorunlu, görüşme notu, değiştirilecek şeyler ve ruh hali isteğe bağlıdır. Programın tamamlama ve deneme bilgileri kayda kendiliğinden eklenir. Notunu fotoğraftan ya da sesle de doldurabilirsin (yapay zekâ, ücretli pakette). Notlar yalnız sana özeldir, veli ve öğrenci görmez. Haftalık rapor üretip gündemini seansa bağlayabilirsin.

## Koçluk içgörüsü ve haftalık rapor
pages: /teacher/students

İçgörü, seans notların ve son akademik durum üzerinden bir sonraki görüşme için özet, gündem önerisi ve dikkat edilecek noktalar hazırlar; bir kez üretilir, sonra kredisiz okunur, yeni seans eklenince yenilemen önerilir. Haftalık koç raporu öğrencinin haftasını ders, konu, deneme ve gündem maddeleriyle özetler; "Veli sürümü" sade ve olumlu dille veliye gönderilecek hâlidir.

## Tahsilat
chip: Öğrenci ücretlerini nasıl takip ederim?
pages: /teacher/billing
link: /teacher/billing | Tahsilat

Tahsilat sayfasında her öğrenci için seans ücretini belirlersin; ay içinde "Yapıldı" işaretli seanslar otomatik tahakkuk eder, ertelenen ve gelmedi seansları sayılmaz. Aldığın ödemeyi nakit, havale ya da diğer olarak girersin; "Ayı kapat" kalan tutarı tek seferde işler. Bu bölüm senin öğrencinden aldığın ücreti izler, platform aboneliğinle ilgisi yoktur.

## Online görüşme randevuları
chip: Randevu nasıl oluştururum?
pages: /teacher/appointments
link: /teacher/appointments | Görüşmeler

Görüşmeler sayfasında tek seferlik ya da haftalık tekrarlayan randevu oluşturursun. Uygunluk saatlerini tanımlarsan öğrenci boş saatten görüşme isteyebilir, sen onaylarsın. Görüşme bağlantısını yapıştırabilir ya da Google hesabını bağlayarak otomatik Meet bağlantısı üretebilirsin. Öğrenciye ve veliye bir gün önce ve bir saat önce hatırlatma gider. Görüşme bitince "Seansı kaydet" ile seans kaydı ve tahsilat bağlanır.

## Öğrenci talepleri
pages: /teacher/requests
link: /teacher/requests | Talepler

Öğrenci bir görev için sayı değiştirme, kaynak değiştirme ya da görevi kaldırma talebi açabilir; onayla, gerekçeyle reddet ya da yanıtla. Soru ve notlar onay beklemez, "Gördüm" ile kapatılır. Talepler sayfasının rozeti bekleyenleri sayar.

## Veli daveti
chip: Veliyi sisteme nasıl eklerim?
pages: /teacher/students

Öğrencinin Veliler sekmesinden velinin e-postasıyla davet gönderirsin; veli bağlantıdan şifresini belirler ve bildirim tercihlerini seçer. Veli haftalık rapor, yeni program, deneme sonucu ve dikkat bildirimleri alır; koçun özel notlarını görmez.

## Gelişim araçları: hedef, tekrar, DNA, odak
pages: /teacher/students

Öğrenci sayfasının Gelişim sekmesinde dört araç vardır: Hedefler (öğrenciye hedef ekle, ilerlemeyi izle), Tekrar (aralıklı tekrar kartları, zorlandığı konular), Çalışma DNA'sı (en verimli saatleri, istikrar, tükenmişlik riski) ve Odak (odak oturumları ve seri).

## Anketler ve kariyer sentezi
pages: /teacher/students

Öğrencinin Anketler sekmesinden çoklu zeka, öğrenme stilleri, sınav kaygısı, mesleki ilgi gibi 11 tanıma anketinden birini gönderirsin; öğrenci doldurunca sonuç grafiklerle sana gelir. Mesleki ilgi ve beceri anketleri tamamlanınca yapay zekâ kariyer sentezi meslek ve bölüm önerisi üretir (ücretli pakette).

## Sınıf yükseltme ve dönem
pages: /teacher/grade-advance, /teacher/students
link: /teacher/grade-advance | Sınıf yükseltme

Yeni öğretim yılında Sınıf Yükseltme ile öğrencileri bir üst sınıfa geçirirsin; sistem yeni bir dönem açar, geçen yılın görev ve denemeleri silinmez ama "bu dönem" görünümünün dışında kalır. 8'den 9'a geçişte müfredat modeli değiştiği için sistem bir önizleme sihirbazı gösterir ve geçen yılın kitaplarını arşivlemeyi önerir.

## Toplu WhatsApp
pages: /teacher/bulk-wa
link: /teacher/bulk-wa | Toplu WhatsApp

Hazır şablonlardan seçip öğrencilerine ya da velilerine WhatsApp mesajı hazırlarsın; sistem mesajı doldurur, WhatsApp kendi telefonunda açılır ve son gönder tuşuna sen basarsın. Tek tek göndermek için öğrenci sayfasında "WhatsApp" düğmesi vardır. Hedefin telefonunun kayıtlı olması gerekir.

## Destek ve kuruma talep
pages: /teacher/support
link: /teacher/support | Destek

Teknik sorun, hesap ya da üyelik için Destek sayfasından talep açarsın. Bağımsız koçun talebi ETÜTKOÇ ekibine, kuruma bağlı öğretmenin talebi kurum yöneticisine gider; gerekirse kurum yöneticisi ETÜTKOÇ'a yönlendirir. Kurum yöneticisinin sana ilettiği "öğrenci hakkında" talepler Gelen Talepler'e düşer.

## Rehber
link: /teacher/guide | Rehberi aç
pages: /teacher/dashboard

Rehber sayfasında Rota sesli ve ekran görüntülü olarak kitap eklemeden deneme girmeye kadar her adımı gösterir; kaldığın yerden devam edebilirsin.

## Kuruma bağlı öğretmen
pages: /teacher/plan

Kuruma bağlı öğretmenin paketi ve ödemesi kurum tarafından yönetilir; paket ya da kota sorusunda kurum yöneticine başvurursun. Ekranlar ve e-postalar kurumun markasını taşır.
