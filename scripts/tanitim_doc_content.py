# -*- coding: utf-8 -*-
"""ETÜTKOÇ Rotam — tanıtım kılavuzu içeriği (eğitimci dili, fayda odaklı).

Her özellik: başlık · ne yapar · kime ne kazandırır · ekran görüntüsü.
Görseller: app/static/guide/shots (rehber turlarından, gerçek panel) +
scratchpad/docshots (bu doküman için çekilenler).
"""
from __future__ import annotations

# ---------------------------------------------------------------- GİRİŞ
INTRO = {
    "lead": (
        "Rotam, sınav hazırlığında koçun, öğrencinin, velinin ve kurumun aynı "
        "veriye bakmasını sağlayan bir çalışma takip ve planlama sistemidir. "
        "Amacı yeni bir defter, yeni bir tablo ya da yeni bir mesajlaşma grubu "
        "eklemek değil; hepsinin yaptığı işi tek yerde toplayıp öğrenmenin "
        "kanıtını görünür kılmaktır."
    ),
    "problem_title": "Çözmeye çalıştığımız üç sorun",
    "problems": [
        ("Emek görünmüyor",
         "Koç saatlerini programa, takibe, veli iletişimine harcıyor; ama elinde "
         "gösterebileceği somut bir kanıt olmuyor. Veli “nasıl gidiyor?” diye "
         "sorduğunda cevap çoğu zaman izlenime dayanıyor."),
        ("Veri dağınık",
         "Program bir yerde, ödevler başka yerde, deneme sonuçları bambaşka bir "
         "klasörde. Dağınık veri analiz edilemez; analiz edilemeyen süreç de "
         "yönetilemez."),
        ("Kopuş geç fark ediliyor",
         "Bir öğrenci sessizce geri kalmaya başladığında bunu haftalar sonra "
         "fark ederiz. Oysa erken fark edilen bir duraklama, birkaç haftalık "
         "kayıptan çok daha kolay telafi edilir."),
    ],
    "cycle_title": "Sistem nasıl işler? — altı adımlı döngü",
    "cycle": [
        ("Kaynak", "Koç, öğrencinin çalışacağı kitapları sisteme tanıtır; her "
                   "kitabın üniteleri ve test sayıları bilinir hale gelir."),
        ("Program", "Haftalık program kurulur. Her görev gerçek bir kitabın "
                    "gerçek bir ünitesine bağlıdır; sistem kalan kapasiteyi bilir."),
        ("Uygulama", "Öğrenci günlük ekranından görevlerini işaretler, doğru ve "
                     "yanlış sayılarını girer."),
        ("Ölçüm", "Her işaret veriye dönüşür: konu doğrulukları, tempo, "
                  "tutarlılık, deneme netleri."),
        ("Müdahale", "Sistem geride kalanı, duraklayanı, unutmaya başlayanı "
                     "işaretler; koç zamanında müdahale eder."),
        ("Şeffaflık", "Veli olan biteni sade bir dille görür; kurum bütün "
                      "koçları tek panodan izler."),
    ],
    "audience_title": "Bu belge kimin için?",
    "audiences": [
        ("Bağımsız koç", "Kendi öğrencileriyle çalışan eğitim koçları için — "
                         "planlamadan tahsilata kadar tüm iş akışı."),
        ("Kurum", "Dershane, etüt merkezi, özel okul ve kurs yönetimleri için — "
                  "koç kadrosunun ölçülebilir yönetimi."),
        ("Öğrenci ve veli", "Sistemin öğrenciye ve aileye ne sunduğunu merak "
                            "eden herkes için."),
    ],
}

SHOTS = "guide"     # app/static/guide/shots
DOCS = "docs"       # scratchpad/docshots
KURUM = "kurum"     # scratchpad/video/kurum


def F(title, what, benefits, img=None, src=SHOTS, cap=None, note=None):
    """Özellik bloğu."""
    return {"title": title, "what": what, "benefits": benefits,
            "img": img, "src": src, "cap": cap, "note": note}


# ---------------------------------------------------------------- KOÇ
COACH_GROUPS = [
    ("Kaynak ve müfredat temeli",
     "Sağlam bir takip, hangi kaynaktan ne kadar çalışıldığını bilmekle başlar. "
     "Rotam'da her görev gerçek bir kitaba ve gerçek bir müfredat konusuna bağlıdır.",
     [
      F("Kütüphane — kitapların tek yerde",
        "Öğrencilerinizle çalıştığınız tüm kitapları sisteme bir kez tanıtırsınız. "
        "Her kitabın üniteleri ve ünite başına test sayısı sistemde tutulur. Ders, "
        "sınav türü ve sınıf seviyesine göre süzebilir; kitapları setler halinde "
        "toplayıp yeni öğrenciye tek hamlede atayabilirsiniz.",
        [("Koça", "Aynı kitabı her öğrenci için baştan tanımlama derdi biter; "
                  "kütüphane bir kez kurulur, yıllarca kullanılır."),
         ("Öğrenciye", "Hangi kitaptan ne kadar ilerlediğini kendi panelinde görür."),
         ("Kuruma", "Kurum genelinde ortak kaynak havuzu; yeni gelen koç hazır "
                    "kütüphaneyle başlar.")],
        "kutuphane.png", SHOTS, "Kütüphane — ders, tür ve müfredata göre süzülebilir kitap listesi"),

      F("Kitap ekleme sihirbazı — dört adımda hazır kitap",
        "Yeni bir kitabı adım adım eklersiniz: bilgiler, üniteler, müfredat "
        "eşleştirmesi ve öğrenci ataması. Üniteleri elle girebilir, resmi konu "
        "kataloğundan seçebilir ya da yapay zekâdan öneri isteyebilirsiniz.",
        [("Koça", "Yüz sayfalık bir soru bankasının ünite listesini dakikalar "
                  "içinde kurar; el emeği yerine kontrol yapar."),
         ("Kuruma", "Kaynak tanımlama standardı oluşur; her koç aynı kaliteyle "
                    "kitap ekler.")],
        "sihirbaz-katalog.png", SHOTS,
        "Resmi konu kataloğu: sınıf ve derse göre hazır ünite listesi"),

      F("Müfredat eşleştirme — kitap bölümü ile resmi konu buluşur",
        "Kitabın ünite adları yayınevine göre değişir; müfredattaki resmi konu "
        "adları ise sabittir. Sistem bu ikisini otomatik eşleştirir, eşleşmeyenleri "
        "size sorar. Böylece “bu öğrenci müfredatın neresinde?” sorusunun cevabı "
        "kitap adlarından bağımsız hale gelir.",
        [("Koça", "Farklı yayınevlerinden kitaplar aynı müfredat çatısı altında "
                  "birleşir; ilerleme gerçekten karşılaştırılabilir olur."),
         ("Öğrenciye", "Deneme analizi ile çalışma kayıtları aynı konu adlarını "
                       "kullandığı için tavsiyeler tutarlı olur.")],
        "sihirbaz-esles.png", SHOTS,
        "Otomatik eşleştirme önerisi — koç onaylar, gerekirse elle düzeltir"),

      F("Öğrencinin müfredat haritası ve yetişme projeksiyonu",
        "Her öğrenci için müfredat konu konu listelenir: hangi konu işlendi, hangisi "
        "sırada, hangisinde kaynak yok. Ayrıca mevcut çalışma temposu sınava kadar "
        "sürerse müfredatın ne kadarının biteceği hesaplanır.",
        [("Koça", "“Yetişir mi?” sorusuna içgüdüyle değil, tempo hesabıyla cevap "
                  "verir; gerekiyorsa planı erkenden sıkılaştırır."),
         ("Veliye", "Kaygı yaratan belirsizlik yerine somut bir tablo görür."),
         ("Kuruma", "Sınıf/kohort düzeyinde müfredat kapsama oranı izlenebilir.")],
        "koc-mufredat.png", DOCS,
        "Ders ders müfredat ilerlemesi ve sınava yetişme projeksiyonu"),
     ]),

    ("Haftalık program kurma",
     "Program hazırlamak koçun en çok vakit harcadığı iştir. Rotam bu işi "
     "hızlandırır ve hatayı baştan engeller.",
     [
      F("Haftalık program ve hafta ızgarası",
        "Haftanın yedi günü tek bakışta görünür. Bir güne tıklayınca o günün "
        "düzenleyicisi açılır; görevler ders bazında gruplanır, istenirse sabah/"
        "öğle/akşam periyotlarına ayrılır. Görevler sürükle-bırak ile sıralanır.",
        [("Koça", "Haftanın dengesi bir bakışta görünür: hangi gün boş, hangi gün "
                  "aşırı yüklü."),
         ("Öğrenciye", "Günü karışık bir liste değil, dersine göre düzenlenmiş bir "
                       "akış olarak görür.")],
        "hafta-izgara.png", SHOTS, "Hafta ızgarası — yedi gün, görev sayısı ve tamamlanma durumu"),

      F("Kaynak durumu — sistem kalan testi sizden iyi bilir",
        "Bir üniteye görev atadığınızda o testler kitaptan düşülür. Kalan kapasite "
        "anlık görünür; biten üniteye yanlışlıkla yeni görev atanamaz. Ünite bazında "
        "hangi testin çözüldüğü, hangisinin rezerve edildiği ayrıntılı izlenir.",
        [("Koça", "Aynı testi iki kez atama, bitmiş kitaptan görev verme gibi "
                  "hatalar ortadan kalkar."),
         ("Öğrenciye", "Kaynağının ne kadarını bitirdiğini net olarak görür; "
                       "belirsizlik motivasyonu düşürmez."),
         ("Veliye", "Alınan kitabın gerçekten kullanıldığını görür.")],
        "kaynak-durumu.png", SHOTS, "Kaynak durumu — ders bazında çözülen, rezerv ve kalan test"),

      F("Akıllı öneriler — programı sistem taslaklar",
        "Sistem her gün için konu önerir. Öneriyi üç şey belirler: müfredattaki "
        "sıra, öğrencinin zayıf olduğu konular (deneme analizi ve yanlış arşivinden) "
        "ve öğrencinin gün deseni. Her önerinin yanında gerekçesi yazar; son karar "
        "her zaman koçundur.",
        [("Koça", "Boş sayfadan başlamaz; hazır bir taslağı düzenleyerek ilerler."),
         ("Öğrenciye", "Program rastgele değil, kendi verisine göre şekillenir.")],
        "oneriler-acik.png", SHOTS,
        "Öneri listesi — her satırda konu, gerekçe ve güven düzeyi"),

      F("Serbest bloklar — sistemde olmayan işler",
        "Özel ders ödevi, okulun verdiği föy, kurumun kendi denemesi gibi sistemde "
        "kaynağı olmayan işleri “blok” olarak tanımlar, günlere dağıtırsınız. "
        "Dağıtılan ve kalan miktar tek kartta izlenir.",
        [("Koça", "Dışarıdan gelen ödevler de takibin içine girer; öğrencinin "
                  "toplam yükü gerçekçi görünür.")],
        "blok-karti.png", SHOTS, "Serbest blok — kırk soruluk ödevin günlere dağıtımı"),

      F("Görev şablonları ve program arşivi",
        "Sık kullandığınız görev kalıplarını şablon olarak kaydeder, tek tıkla "
        "uygularsınız. Geçmiş haftaların programları arşivde durur; yapılmayan "
        "görevleri yeni haftaya taşıyabilirsiniz.",
        [("Koça", "Tekrar eden işler dakikalar yerine saniyeler alır; yapılmayan "
                  "iş unutulup kaybolmaz.")],
        "kutup-gorev-sablon.png", SHOTS, "Görev şablonları — kalıplaşmış görevler tek tıkla"),

      F("Yayınlama ve veliye duyurma",
        "Program hazır olana kadar taslak kalır; öğrenci göremez. Yayınladığınızda "
        "öğrencinin ekranına düşer. İsterseniz aynı anda velilere de bilgilendirme "
        "gönderilir — gönderim öncesi tam olarak neyin iletileceğini önizlersiniz.",
        [("Koça", "Yarım programı öğrenciye göstermeden hazırlar; iletişimi tek "
                  "tuşla yapar."),
         ("Veliye", "Yeni haftanın programından anında haberdar olur.")],
        "veliye-duyur.png", SHOTS, "Veliye duyurmadan önce gönderilecek içeriğin önizlemesi"),
     ]),

    ("Deneme sonuçları ve konu analizi",
     "Denemeler, hazırlığın en değerli verisidir — ama yalnızca doğru okunursa. "
     "Rotam denemeyi bir puan olmaktan çıkarıp konu düzeyinde bir yol haritasına çevirir.",
     [
      F("Deneme karnesini yükleyin — soruları tek tek girmeyin",
        "Yayınevinin verdiği konu analizli sonuç karnesini olduğu gibi sisteme "
        "bırakırsınız. Yapay zekâ belgeyi iki kez bağımsız okur, sonuçları "
        "karşılaştırır ve her soruyu sizin müfredatınızdaki konuya bağlar. "
        "Kaydetmeden önce her satırı görür, gerekirse düzeltirsiniz.",
        [("Koça", "Yüz yirmi soruluk bir denemenin konu analizi dakikalar içinde "
                  "sisteme girer; el ile giriş yükü ortadan kalkar."),
         ("Öğrenciye", "Her denemesi birikimli analize dönüşür, kâğıtta kalmaz."),
         ("Kuruma", "Kurum genelinde deneme verisi standart biçimde toplanır.")],
        "deneme-pdf.png", SHOTS, "Karne yükleme — sınıf ve tür beyanı, ardından belge"),

      F("Okuma önizlemesi — son söz koçun",
        "Sistem okuduğu her satırı gösterir: sorunun belgedeki konusu, sizin "
        "müfredatınızdaki karşılığı, doğru cevap, öğrencinin cevabı ve sonuç. "
        "İki okumanın çeliştiği satırlar işaretlenir.",
        [("Koça", "Yapay zekâya körü körüne güvenmek zorunda kalmaz; kontrol "
                  "mekanizması kendisindedir.")],
        "aktar-tablo.png", SHOTS, "Soru soru okuma sonucu — şüpheli satırlar işaretli"),

      F("Net fırsatı — hangi konu kaç net kazandırır?",
        "Sistem, kapanmamış konuların deneme başına kaç net kaybettirdiğini "
        "hesaplar ve sıralar. “Şu konu kapanırsa deneme başına şu kadar net gelir” "
        "cümlesi, program önceliğinizin cevabıdır.",
        [("Koça", "Çalışma önceliğini duyguyla değil getiriyle belirler."),
         ("Öğrenciye", "Emeğinin nereye harcandığında en çok işe yarayacağını görür."),
         ("Veliye", "“Neye çalışılıyor?” sorusunun gerekçesini anlar.")],
        "analiz-firsat.png", SHOTS, "Net fırsatı listesi — konu bazında kazanç tahmini"),

      F("Konu × deneme ısı haritası ve unutulan konular",
        "Her hücre, o denemede o konudan kaç doğru yapıldığını gösterir. Soldan sağa "
        "kızaran bir satır, önceden bilinen bir konunun unutulmaya başladığını "
        "söyler. Sistem bunu ayrıca “unutulan konular” olarak da işaretler.",
        [("Koça", "Unutmayı tahmin etmez, görür; tekrar planını buna göre kurar."),
         ("Öğrenciye", "Bir kez öğrenmenin yetmediğini somut olarak görür.")],
        "analiz-isi.png", SHOTS, "Konu × deneme ısı haritası — zaman içindeki değişim"),

      F("Net gelişimi ve deneme geçmişi",
        "Girilen tüm denemeler sınav türüne göre ayrı ayrı izlenir. Farklı ölçekteki "
        "denemeler (branş denemesi ile genel deneme gibi) birbirine karıştırılmaz.",
        [("Koça", "Gerçek eğilimi görür; yanıltıcı karşılaştırmalardan korunur."),
         ("Veliye", "Çocuğunun gidişatını grafikle takip eder.")],
        "denemeler-sonuc.png", SHOTS, "Deneme paneli — net gelişimi ve konu analizi"),
     ]),

    ("Öğrenciyi tanıma ve zamanında müdahale",
     "Bir koçun en değerli becerisi, sorunu erken görmektir. Sistem bu konuda "
     "koçun gözü olur.",
     [
      F("Öğrenci listesi ve erken uyarı",
        "Öğrenci listesinde renkler bir bakışta durumu söyler: bugün hiç işaret "
        "yapmayan, üst üste boş gün geçiren, temposu düşen ya da sınava yetişmeyecek "
        "görünen öğrenciler öne çıkar. Uyarının sebebi satırda yazar.",
        [("Koça", "Otuz öğrenci arasında kimin bugün ilgi istediğini saniyeler "
                  "içinde görür."),
         ("Kuruma", "Riskli öğrenci kurum panosuna da yansır; yönetim habersiz "
                    "kalmaz.")],
        "ogrenciler.png", SHOTS, "Öğrenci listesi — uyarı düzeyine göre renklendirilmiş satırlar"),

      F("Durum özeti — neden kırmızı, ne yapmalı?",
        "Öğrenci sayfasının en üstünde durum bir cümleyle özetlenir: acil, dikkat "
        "ya da yolunda. Her uyarının yanında kanıt sayfasına giden bağlantı vardır; "
        "iyi giden yönler de ayrıca listelenir.",
        [("Koça", "Uyarıyı görmekle kalmaz, kanıtına tek tıkla ulaşır."),
         ("Öğrenciye", "Görüşmeler somut veriye dayanır, genel nasihate değil.")],
        "durum-ozeti.png", SHOTS, "Durum özeti — dikkat gerektirenler ve iyi gidenler"),

      F("Analitik — tempo, tutarlılık ve gün deseni",
        "Öğrencinin günlük hızı, tutturma oranı, en uzun serisi, hangi günlerde "
        "verimli olduğu ve son otuz beş günün aktivite takvimi tek sayfada toplanır.",
        [("Koça", "Programı öğrencinin gerçek desenine göre kurar; verimsiz günlere "
                  "ağır yük bindirmez."),
         ("Öğrenciye", "Kendi çalışma karakterini tanır.")],
        "koc-analitik.png", DOCS, "Analitik — tempo, projeksiyon, haftalık eğilim"),

      F("Konu performansı — hangi konu sağlam, hangisi tekrar ister",
        "Görevlerde girilen doğru ve yanlış sayıları konu düzeyinde birikir. Her "
        "konunun doğruluk oranı ve son çalışma tarihi görünür.",
        [("Koça", "“Matematikte zayıf” gibi genel yargı yerine konu düzeyinde tanı "
                  "koyar."),
         ("Öğrenciye", "Hangi konuyu pekiştirmesi gerektiğini kendisi de görür."),
         ("Veliye", "Dersin ortalaması iyi görünse bile içindeki zayıf konuyu fark "
                    "eder.")],
        "koc-konu-perf.png", DOCS, "Konu performansı — ders ve konu bazında doğruluk"),

      F("Yanlış Soru Arşivi — kapanana kadar takip",
        "Öğrenci yanlış yaptığı sorunun fotoğrafını çeker. Sistem konusunu bulur, "
        "çözümü söylemeden yaklaşım ipucu verir. Soru, aralıklı tekrarla iki kez "
        "doğru çözülene kadar arşivde kalır; ancak o zaman “kapandı” sayılır.",
        [("Koça", "Öğrencinin hangi konularda ve hangi hata türünde takıldığını "
                  "toplu olarak görür."),
         ("Öğrenciye", "Yanlış defteri tutmanın zahmeti kalkar; sistem hatırlatır."),
         ("Veliye", "Yanlışların gerçekten kapandığını sayıyla görür.")],
        "koc-yanlislar.png", DOCS, "Koç görünümü — biriken konular ve hata türü dağılımı"),

      F("Çalışma DNA'sı, tekrar, hedef ve odak",
        "Öğrencinin en verimli çalıştığı saat dilimi (kronotip), aralıklı tekrar "
        "kuyruğu, hedefleri ve odak oturumları koç tarafından izlenebilir ve "
        "yönetilebilir.",
        [("Koça", "Öğrenciyi yalnız yaptığı test sayısıyla değil, çalışma "
                  "alışkanlığıyla tanır."),
         ("Öğrenciye", "Hedef ve tekrar sistemi kendi panelinde işler.")],
        "koc-dna.png", DOCS, "Çalışma DNA'sı — kronotip ve dönem dağılımı"),
     ]),

    ("Koçluk işletmesi",
     "Bağımsız koç için sistem yalnız akademik değil, işin kendisini de yönetir.",
     [
      F("Seans kayıtları ve yapay zekâ hazırlığı",
        "Her görüşmenin tarihi, kanalı, gündemi ve kararları kaydedilir. Notu "
        "yazmak yerine sesle söyleyebilir ya da kâğıt formun fotoğrafını "
        "çekebilirsiniz. Bir sonraki görüşme öncesi sistem, birikmiş notlardan "
        "size hazırlık özeti çıkarır.",
        [("Koça", "Görüşme geçmişi kaybolmaz; her seansa hazırlıklı girer."),
         ("Öğrenciye", "Konuşulanların takibi yapılır, aynı şeyler tekrar "
                       "konuşulmaz."),
         ("Kuruma", "Koçluk kalitesi kayıt altına alınır.")],
        "koc-seanslar.png", DOCS, "Seans listesi — yapılan ve ertelenen görüşmeler"),

      F("Tahsilat — ücret takibi",
        "Öğrenci başına seans ücreti tanımlanır; yapılan seanslar otomatik sayılır. "
        "Aylık tahakkuk, tahsil edilen ve kalan tutar tek tabloda görünür; ödeme "
        "girildiğinde ay kapanır.",
        [("Koça", "Kim ne kadar ödedi sorusu deftere değil sisteme sorulur."),
         ("Veliye", "Aynı hesabı kendi panelinden şeffafça görür — sürpriz olmaz.")],
        "koc-tahsilat.png", DOCS, "Aylık tahsilat panosu — tahakkuk, tahsilat ve kalan"),

      F("Online görüşme ve randevu",
        "Uygunluk pencerelerinizi tanımlarsınız; öğrenci veya veli boş saatlerden "
        "randevu talep eder, siz onaylarsınız. Görüşme bağlantısı ve hatırlatmalar "
        "sistem üzerinden yürür.",
        [("Koça", "Saat kararlaştırma yazışması ve gelmeyen randevu sorunu azalır."),
         ("Öğrenciye ve veliye", "Görüşme saatini ve bağlantısını tek yerde bulur.")],
        "koc-randevu.png", DOCS, "Randevu ekranı — uygunluk ve görüşme takibi"),

      F("Paket ve kullanım",
        "Bağımsız koç kendi paketini panelden görür ve yükseltir. Yapay zekâ "
        "kullanımı kredi olarak izlenir; hangi işlemin ne kadar kredi harcadığı "
        "şeffaftır.",
        [("Koça", "Maliyeti öngörülebilir; sürpriz fatura olmaz.")],
        "koc-paket.png", DOCS, "Paket ekranı — mevcut durum ve yapay zekâ kredisi"),
     ]),

    ("İletişim",
     "Sistem, koçun iletişim yükünü azaltmak için tasarlandı.",
     [
      F("Öğrenci talepleri",
        "Öğrenci bir görevin sayısını değiştirmek, kaynağını değiştirmek ya da "
        "görevi kaldırmak istediğinde bunu sistem üzerinden talep eder. Siz "
        "onaylar, reddeder ya da yanıt yazarsınız.",
        [("Koça", "Mesajlaşma trafiği yerine kayıtlı, izlenebilir talepler."),
         ("Öğrenciye", "İsteğini doğru kanaldan iletir; cevabı kaybolmaz.")],
        "koc-talepler.png", DOCS, "Talep kutusu — bekleyen istekler ve yanıtlar"),

      F("Toplu ve bireysel WhatsApp",
        "Hazır mesaj şablonlarıyla veliye ya da öğrenciye tek tıkla WhatsApp mesajı "
        "hazırlarsınız. Metin sizin adınıza doldurulur; göndermeden önce görürsünüz.",
        [("Koça", "Bayram kutlaması, duyuru, hatırlatma gibi tekrar eden mesajlar "
                  "dakikalar yerine saniyeler alır.")],
        "koc-toplu-wa.png", DOCS, "Toplu mesaj sihirbazı — hedef grubu ve şablon"),

      F("Anketler ve kariyer sentezi",
        "Öğrenciyi tanımak için hazır anketler gönderirsiniz: çoklu zekâ, öğrenme "
        "stilleri, sınav kaygısı, çalışma alışkanlıkları, mesleki ilgi ve beceri "
        "seti gibi. Sonuçlar görsel raporlara dönüşür; yapay zekâ bunları akademik "
        "veriyle birleştirip meslek ve bölüm önerisi üretir.",
        [("Koça", "Hedef belirleme görüşmesine hazır gündemle girer."),
         ("Öğrenciye", "Kendini tanır; tercih dönemine hazırlıksız yakalanmaz."),
         ("Veliye", "Çocuğunun eğilimlerini veriye dayalı görür.")],
        "koc-anketler.png", DOCS, "Anketler — gönderim ve sonuç raporu"),
     ]),
]

# ---------------------------------------------------------------- ÖĞRENCİ
STUDENT_GROUPS = [
    ("Günlük akış",
     "Öğrencinin sistemle kurduğu ilişki basittir: bugüne bak, yap, işaretle.",
     [
      F("Bugün ekranı",
        "Günün görevleri sırayla listelenir. Yapılan görev işaretlenir; manşetteki "
        "yüzde anında güncellenir. Video, özet, tekrar gibi görevler de aynı akışta yer alır.",
        [("Öğrenciye", "Ne yapacağını düşünmekle vakit kaybetmez; liste hazırdır."),
         ("Koça", "İşaretlemeler anlık olarak panele düşer.")],
        "ogr-bugun.png", SHOTS, "Bugün ekranı — günün görevleri ve tamamlanma oranı"),

      F("Doğru–yanlış girişi",
        "Test görevini bitiren öğrenci kaç doğru kaç yanlış yaptığını girer. Bu "
        "sayılar konu performansına, zayıflık analizine ve program önerilerine akar.",
        [("Öğrenciye", "Girdiği iki sayı, sonraki haftanın programını şekillendirir."),
         ("Koça", "Konu düzeyinde gerçek başarı verisi oluşur.")],
        "ogr-dy-gir.png", SHOTS, "Doğru–yanlış girişi — çözülen test ve sonuçlar"),

      F("Günün notu",
        "Öğrenci günün sonunda kısa bir not bırakabilir: neyi zor buldu, ne oldu. "
        "Not koçun gün panelinde görünür.",
        [("Öğrenciye", "Yalnızca sayı değil, halini de paylaşabilir."),
         ("Koça", "Sayıların arkasındaki hikâyeyi görür.")],
        "ogr-gun-notu.png", SHOTS, "Günün notu — öğrencinin kendi cümleleri"),
     ]),

    ("Kendi verisiyle çalışmak",
     "Öğrenci sistemde yalnız görev yapmaz; kendi gelişimini izler.",
     [
      F("Yanlışlarım — yanlış soru arşivi",
        "Yanlış yapılan sorunun fotoğrafı çekilir, hangi kaynaktan geldiği ve neden "
        "yanlış yapıldığı işaretlenir. Yapay zekâ konusunu bulur ve çözümü vermeden "
        "yaklaşım ipucu verir. Soru aralıklarla yeniden karşınıza gelir.",
        [("Öğrenciye", "Yanlış defteri tutma zahmeti biter; hangi soruyu ne zaman "
                       "tekrar çözeceğini sistem hatırlatır."),
         ("Koça", "Hata türü dağılımını görür: bilgi eksiği mi, dikkat mi, süre mi?")],
        "ogr-yanlis-ekle.png", SHOTS, "Yanlış ekleme — fotoğraf, kaynak ve hata türü"),

      F("Yaklaşım ipucu — cevabı değil yolu gösterir",
        "Sistem hazır çözüm vermez. “Hangi kavramı hatırla, ilk adım ne olmalı” "
        "biçiminde yönlendirir; öğrenci çözümü kendisi bulur.",
        [("Öğrenciye", "Kopya çekmiş olmaz; düşünme alışkanlığı korunur."),
         ("Veliye", "Yapay zekânın ödevi yapmadığını, öğretmeye çalıştığını bilir.")],
        "ogr-ai-ipucu.png", SHOTS, "Yaklaşım ipucu — çözüm değil, yönlendirme"),

      F("Denemelerim ve konu analizi",
        "Öğrenci kendi deneme karnesini yükleyebilir; sonuçları ve konu analizini "
        "kendi panelinde görür.",
        [("Öğrenciye", "Denemesinin ne anlama geldiğini kendi başına okuyabilir."),
         ("Koça", "Veri girişini paylaşır; öğrenci sürece ortak olur.")],
        "ogr-konu-analiz.png", SHOTS, "Öğrenci deneme analizi — net fırsatı ve ısı haritası"),

      F("Tekrar, hedef, odak ve DNA",
        "Aralıklı tekrar kuyruğu unutmayı önler; hedefler ilerlemeyi görünür kılar; "
        "odak sayacı çalışma seansını ölçer; çalışma DNA'sı en verimli saatleri gösterir.",
        [("Öğrenciye", "Çalışmayı yönetmeyi öğrenir; alışkanlık verisi kendisine "
                       "geri döner."),
         ("Koça", "Bu araçların çıktısı öneri motoruna girer.")],
        "ogr-dna.png", SHOTS, "Çalışma DNA'sı — kronotip ve verimli saatler"),

      F("Talepler, anketler ve bağımsız çalışma",
        "Öğrenci koçuna görev değişikliği talebi iletir, gönderilen anketleri "
        "doldurur ve program dışında yaptığı çalışmayı bildirir.",
        [("Öğrenciye", "Sürecin öznesi olur, izleyicisi değil."),
         ("Koça", "Program dışı emek de kayda geçer.")],
        "ogr-talep-doldur.png", SHOTS, "Talep formu — sayı değişikliği isteği"),
     ]),
]

# ---------------------------------------------------------------- VELİ
PARENT_GROUPS = [
    ("Veli paneli",
     "Veliler için tasarım ilkesi tek cümledir: grafik okumak zorunda kalmasın.",
     [
      F("Panel — çocuğun durumu bir bakışta",
        "Her çocuk için bir kart: bugün kaç görev yapıldı, son yedi günde ne kadarı "
        "tamamlandı, son deneme neti kaç. Renkler durumu anlatır.",
        [("Veliye", "Uzun raporlar okumadan durumu anlar."),
         ("Koça", "“Nasıl gidiyor?” aramaları azalır.")],
        "veli-panel.png", SHOTS, "Veli paneli — çocuk kartları ve son deneme"),

      F("Rota'nın Yorumu — sayıları sizin dilinizde anlatır",
        "Yapay zekâ, çocuğun haftalık program ilerlemesini ve deneme sonuçlarını "
        "sade bir dille anlatır: neyin yapıldığı, neyin aksadığı, evde nasıl destek "
        "olunabileceği. İsterseniz okursunuz, isterseniz dinlersiniz.",
        [("Veliye", "Yüzdelerle değil cümlelerle bilgilenir; sesli dinleme seçeneği "
                    "vardır."),
         ("Öğrenciye", "Evdeki konuşma suçlayıcı değil, somut konular üzerinden olur.")],
        "veli-rota-yorum.png", SHOTS, "Rota'nın yorumu — bölümlü anlatım ve sesli dinleme"),

      F("Rota'ya Sor — yazarak ya da konuşarak soru sorun",
        "“Oğlum programa uyuyor mu?”, “Dün neler yapılmadı?” gibi soruları doğrudan "
        "sorabilirsiniz. Cevap uydurma değildir; çocuğunuzun gerçek verisinden "
        "üretilir. Mikrofona konuşarak da sorabilirsiniz.",
        [("Veliye", "Merak ettiğini beklemeden öğrenir; teknolojiye uzak olması "
                    "engel değildir."),
         ("Koça", "Rutin sorular sistemde yanıtlanır; koç asıl işine odaklanır.")],
        "veli-sor-cevap.png", SHOTS, "Rota'ya Sor — gerçek veriye dayalı cevap"),

      F("Haftalık rapor",
        "Geçen haftanın karnesi: tamamlama oranı, çözülen test, çalışılan gün — "
        "hepsi bir önceki haftayla kıyaslı. En çok çalışılan ve en çok aksatılan "
        "ders, gün gün döküm ve koç notları aynı sayfada.",
        [("Veliye", "Haftada bir bakış çoğu ihtiyacı karşılar."),
         ("Koça", "Düzenli bilgilendirme otomatikleşir.")],
        "veli-rapor.png", SHOTS, "Haftalık rapor — kıyaslamalı karne"),

      F("Program, konu performansı ve denemeler",
        "Koçun kurduğu haftalık programı gün gün görürsünüz. Konu performansı "
        "sayfası hangi konunun sağlam hangisinin tekrar istediğini renklerle "
        "gösterir. Deneme sayfasında netler ve ders kırılımı yer alır.",
        [("Veliye", "“Ders çalıştın mı?” yerine “doğrusal denklem testleri nasıl "
                    "gitti?” diye sorabilir."),
         ("Öğrenciye", "Evde daha isabetli destek görür.")],
        "veli-konu-fen-acik.png", SHOTS,
        "Konu performansı — dersin içindeki zayıf konu görünür"),

      F("Seans hareketleri ve ödeme şeffaflığı",
        "Yapılan koçluk seansları, ertelenenler ve ödemeler tek sayfada. Aylık "
        "tahakkuk, ödenen ve kalan tutar açıkça yazar. Koçun seans içi özel notları "
        "veliye gösterilmez.",
        [("Veliye", "Ne için ödeme yaptığını net görür."),
         ("Koça", "Ücret konuşması güven ilişkisini zedelemez.")],
        "veli-seans-genel.png", SHOTS, "Seans hareketleri — açık hesap ve seans listesi"),

      F("Koça talep ve bildirim ayarları",
        "Koça doğrudan mesaj gönderebilir, hangi bildirimleri hangi kanaldan "
        "alacağınızı kendiniz seçebilirsiniz.",
        [("Veliye", "İletişim tek yerde toplanır; bildirim yükünü kendisi ayarlar.")],
        "veli-ayarlar.png", SHOTS, "Bildirim tercihleri — kanal ve tür bazında"),
     ]),
]

# ---------------------------------------------------------------- KURUM
INST_GROUPS = [
    ("Yönetim panosu",
     "Kurum yöneticisi için soru şudur: hangi koçun süreci işliyor, hangi öğrenci "
     "kopuyor, hangi sınıf sonuç üretiyor? Rotam bunları tahmine bırakmaz.",
     [
      F("Kurum panosu",
        "Öğrenci ve öğretmen sayıları, haftalık planlanan ve çözülen test, riskli "
        "öğrenci sayısı ve koç bazında performans tek ekranda toplanır.",
        [("Kuruma", "Haftalık durum toplantısı için hazır tablo."),
         ("Koça", "Emeği görünür olur; iyi çalışan koç fark edilir.")],
        "kurum-panel.png", DOCS, "Kurum panosu — genel göstergeler"),

      F("Program uyumu",
        "Kurum genelinde programa uyum oranı, doğruluk yüzdesi, koç kırılımı ve "
        "programsız kalan öğrenciler haftalık olarak izlenir.",
        [("Kuruma", "Zayıf halka görünür hale gelir; müdahale hedefli olur."),
         ("Veliye", "Kurum standardı yükseldikçe hizmet kalitesi artar.")],
        "kurum-uyum2.png", DOCS, "Program uyumu — koç bazında tamamlama ve doğruluk"),

      F("Müdahale merkezi",
        "Bugün ilgi gerektiren durumlar öncelik sırasıyla tek listede toplanır: boş "
        "program, düşük uyum, riskli öğrenci. Her kartta önerilen aksiyon yazar; "
        "tek tıkla ilgili koça iletilir.",
        [("Kuruma", "Yönetici gününe “nereye bakmalıyım” sorusuyla değil, hazır "
                    "listeyle başlar."),
         ("Koça", "Kurumdan gelen uyarı somut ve gerekçelidir.")],
        "kurum-mudahale2.png", DOCS, "Müdahale merkezi — öncelikli aksiyon kartları"),

      F("Öğretmen etkililik karnesi",
        "Son haftaların verisinden koç başına birleşik bir etkililik skoru üretilir: "
        "tamamlama, doğruluk, program disiplini ve düşük risk bileşenleriyle.",
        [("Kuruma", "“Kim sonuç alıyor?” sorusunun ölçülebilir cevabı; en iyi "
                    "pratik yaygınlaştırılır.")],
        "kurum-karne2.png", DOCS, "Öğretmen karnesi — skor ve bileşenleri"),

      F("Akademik çıktı",
        "Deneme sonuçları kurum genelinde toplanır. Net başarı oranı sayesinde "
        "farklı sınav türleri karşılaştırılabilir hale gelir; gelişen ve gerileyen "
        "öğrenciler ayrıca listelenir.",
        [("Kuruma", "Akademik sonucu veliye ve yönetime rakamla anlatır.")],
        "kurum-akademik2.png", DOCS, "Akademik çıktı — net başarı eğilimi"),
     ]),

    ("Derinlemesine analiz",
     "Kurum panosunun altında, sorunun kaynağına inen ayrı analiz sayfaları vardır.",
     [
      F("Risk paneli ve tükenmişlik radarı",
        "Riskli öğrenciler seviye ve gerekçesiyle listelenir. Tükenmişlik radarı ise "
        "aşırı yüklenen ya da temposu ani düşen öğrencileri işaretler. Her satırdan "
        "ilgili koça müdahale talebi gönderilebilir.",
        [("Kuruma", "Öğrenci kaybını erken önler."),
         ("Öğrenciye", "Aşırı yük fark edilir; sürdürülebilir tempo korunur.")],
        "kurum-risk.png", DOCS, "Risk paneli — seviye, gerekçe ve sorumlu koç"),

      F("Kohort ve aktivite analizi",
        "Sınıf ve grup bazında karşılaştırma, haftalık değişim ve saat–gün bazında "
        "aktivite haritası kurumun ritmini gösterir.",
        [("Kuruma", "Etüt saatlerini ve kadro planını gerçek kullanım verisine göre "
                    "düzenler.")],
        "kurum-aktivite.png", DOCS, "Aktivite haritası — yoğunluk dağılımı"),

      F("Veli güveni",
        "Kaç velinin hesabı aktif, bildirimler ulaşıyor mu, bekleyen davet var mı — "
        "veli iletişiminin sağlığı ölçülür.",
        [("Kuruma", "Veli memnuniyetinin görünmeyen altyapısı izlenir."),
         ("Veliye", "İletişim kopukluğu fark edilip giderilir.")],
        "kurum-veli-guveni.png", DOCS, "Veli güveni — kapsama ve bildirim teslimi"),

      F("Haftalık yönetici özeti",
        "Her hafta kurum yöneticisine özet gönderilir: tamamlama, risk, öne çıkan "
        "ve geride kalan sınıflar, pasif öğretmenler.",
        [("Kuruma", "Panele girmeden haftalık nabzı tutar.")],
        "kurum-ozet.png", DOCS, "Haftalık özet arşivi"),

      F("Öğretmen yönetimi ve davet",
        "Yeni öğretmen davet edilir, hesap açılır, pasif hale getirilir. Kurumun "
        "kadro yapısı tek yerden yönetilir.",
        [("Kuruma", "Kadro değişikliği dakikalar içinde uygulanır; veri kaybolmaz.")],
        "kurum-ogretmenler.png", DOCS, "Öğretmen listesi ve davet yönetimi"),

      F("Bağımsız çalışma denetimi ve kullanım",
        "Program dışı işlenen ilerlemeler koç kırılımıyla raporlanır; deneme "
        "verisiyle çapraz doğrulama yapılır. Kredi ve limit kullanımı ayrıca izlenir.",
        [("Kuruma", "Veri güvenilirliği korunur; maliyet öngörülebilir olur.")],
        "kurum-bagimsiz.png", DOCS, "Bağımsız çalışma raporu — koç kırılımı"),
     ]),
]

# ---------------------------------------------------------------- YAPAY ZEKÂ
AI_SECTION = {
    "lead": (
        "Rotam'da yapay zekâ bir gösteri unsuru değil, belirli işleri hızlandıran "
        "bir araçtır. Nerede kullanıldığı, ne yapmadığı ve verinin nasıl korunduğu "
        "açıkça tanımlıdır."
    ),
    "uses": [
        ("Deneme karnesi okuma",
         "Yayınevi karnesini soru soru okur ve konularınıza bağlar. Belge iki kez "
         "bağımsız okunur, çelişkili satırlar işaretlenir."),
        ("Yanlış soru etiketleme ve ipucu",
         "Soru fotoğrafından konuyu bulur; çözümü söylemeden yaklaşım ipucu verir."),
        ("Koçluk hazırlığı",
         "Birikmiş seans notlarından ve akademik veriden bir sonraki görüşme için "
         "gündem önerir."),
        ("Veli anlatımı ve soru–cevap",
         "Panel verisini velinin diline çevirir; sesli anlatım üretir ve velinin "
         "sorularını gerçek veriyle yanıtlar."),
        ("Kitap ünitesi önerisi",
         "Yeni eklenen kitabın ünite listesini önerir; koç düzenler."),
        ("Kariyer sentezi",
         "Anket sonuçlarını akademik veriyle birleştirip meslek ve bölüm önerisi "
         "üretir."),
    ],
    "limits_title": "Yapay zekânın YAPMADIKLARI",
    "limits": [
        "Öğrencinin ödevini çözmez; yanlış soruda cevabı değil yolu gösterir.",
        "Koçun yerine karar vermez; her öneri onaya açıktır ve gerekçesi görünür.",
        "Uydurma bilgi üretmemesi için yalnız sistemdeki gerçek veriyle beslenir.",
        "Konu ataması sizin müfredatınızla sınırlıdır; listede olmayan konu üretemez.",
    ],
    "privacy_title": "Veri güvenliği ve KVKK",
    "privacy": [
        ("Açık rıza", "Öğrenci verisiyle çalışan yapay zekâ özellikleri yalnız "
                      "koçun açık onayıyla çalışır."),
        ("Medya saklanmaz", "Sesli not ve fotoğraflar metne çevrildikten sonra "
                            "saklanmaz."),
        ("Veli ayrımı", "Koça özel seans notları veliye asla gösterilmez."),
        ("Hesap güvenliği", "İki adımlı doğrulama, oturum yönetimi, şifre "
                            "politikası ve kayıtlı işlem geçmişi standarttır."),
        ("Silme hakkı", "Kullanıcı hesabının silinmesini uygulama içinden talep "
                        "edebilir; yasal süre içinde geri alınabilir."),
    ],
}

MOBILE = {
    "lead": (
        "Öğrencilerin çoğunda bilgisayar yok; telefon var. Bu yüzden günlük akış "
        "mobil uygulamada da eksiksiz çalışır."
    ),
    "items": [
        ("Öğrenci", "Bugün ekranı, işaretleme, doğru–yanlış girişi, yanlış soru "
                    "arşivi, denemeler, tekrar, hedef ve odak."),
        ("Veli", "Panel, Rota'nın yorumu (sesli dahil), Rota'ya Sor, haftalık "
                 "rapor ve bildirimler."),
        ("Koç", "Öğrenci takibi, program görüntüleme ve görev ekleme, seans ve "
                "deneme girişi, talepler."),
        ("Kurum", "Panel, müdahale merkezi, analiz sayfaları ve talepler."),
    ],
    "note": "Bildirimler telefona anlık düşer: yeni program, haftalık rapor, "
            "deneme sonucu hazır, talep yanıtı ve koça iletilen uyarılar.",
}

START = {
    "lead": "Başlamak için karmaşık bir kurulum gerekmez.",
    "steps": [
        ("Hesap açın", "Bağımsız koçsanız on dört gün ücretsiz denersiniz; kart "
                       "bilgisi istenmez."),
        ("Kütüphanenizi kurun", "Kullandığınız kitapları ekleyin — sihirbaz "
                                "üniteleri sizin için hazırlar."),
        ("Öğrenci ekleyin", "Öğrenci hesabını açın, kitapları atayın, velisini "
                            "davet edin."),
        ("İlk programı kurun", "Öneriden yararlanarak haftayı kurun ve yayınlayın."),
        ("Rehberi izleyin", "Sistem içindeki sesli rehber, her rol için adım adım "
                            "kullanımı gösterir."),
    ],
    "inst_title": "Kurumlar için",
    "inst": (
        "Dershane, etüt merkezi ve okullarda kurulum bizim tarafımızdan yapılır: "
        "kurum hesabı, koç kadrosu, kütüphane ve raporlama düzeni hazır teslim "
        "edilir. Fiyatlandırma koç sayısına göre belirlenir."
    ),
}
