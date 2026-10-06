"""Rota Rehberi — PROGRAM serisi (koç). İçerik kaynağı.

`python -m scripts.guide_content.build` bu modülü okur ve
web/components/guide/coach-guide-content.json içindeki "Program" konusunu
yeniden yazar. Metinler yalnız GERÇEK ekranlarda görünen etiketleri kullanır
(envanter: 2026-10-05). Ekranlar: scripts/capture_guide_program.py.

Adım: (metin, ekran, vurgu kutusu, tıklama animasyonu, yakınlaştırma)
"""

MODULE = "Program"


def S(caption, shot=None, target=None, click=False, zoom=False, speech=None):
    d = {"caption": caption, "shot": shot, "target": target, "click": click, "zoom": zoom}
    if speech:
        d["speech"] = speech
    return d


CHAPTERS = [
    {
        "key": "prog-sayfa",
        "title": "Program sayfası ve yeni program",
        "subtitle": "Haftayı aç, sayfanın düzenini tanı",
        "action": {
            "label": "Öğrencini aç, haftalık programını kur",
            "href": "/teacher/students",
            "checkKey": "program-kur",
            "doneLabel": "Programın hazır",
            "hint": "Yol: sol menü → Öğrenciler → öğrencinin satırında \"Program\" ya da öğrenci sayfasında \"Haftalık Program\".",
            "optional": True,
        },
        "steps": [
            S("Sıra programda. Bu eğitimde Elif'in bir haftalık programını baştan sona birlikte kuracağız: haftayı açacağız, görev ekleyeceğiz, görevleri günler arasında taşıyacağız, her hafta tekrar eden düzeni iskelete çevireceğiz ve programı öğrenciye ve veliye ulaştıracağız."),
            S("Öğrenciler sayfasında Elif'in satırındaki Program düğmesine bastım. Haftalık program sayfası açıldı. Elif'in bu hafta için henüz bir programı yok; o yüzden ızgarada bütün günler boş görünüyor.", "p-bos", "baslik", zoom=True),
            S("Başlığın altındaki bu kart şu an izlediğin Program eğitimini açar. Bir bölümü yarıda bırakırsan kaldığın yerden devam edersin; hepsini izlediğinde kart küçük bir düğmeye dönüşür.", "p-bos", "rehber", zoom=True),
            S("Üst sıradaki düğmeler sayfanın kumandasıdır. Yeni Program, yeni bir hafta açar. Programlar, geçmiş haftalarına götürür. İskelet, her hafta tekrar eden düzeni kurar. Yazdır, programın kâğıda basılabilir hâlini açar. Veliye duyur da yayınladığın programı veliye gönderir.", "p-bos", "dugmeler", zoom=True),
            S("Yeni Program düğmesine basıyorum.", "p-bos", "yeni", click=True, zoom=True),
            S("Bu pencerede programın başlangıç ve bitiş tarihini seçersin. Bir program bir ile on dört gün arasında olabilir. Haftan pazartesi başlamak zorunda değil; öğrencinle perşembe görüşüyorsan haftayı perşembe başlatırsın. Bayram haftası gibi özel bir dönemse bir etiket de yazabilirsin. Oluştur'a basıyorum.", "p-yeni-program", "olustur", click=True, zoom=True),
            S("Program açıldı. Başlıkta kaç günlük olduğu ve tarih aralığı yazıyor. Tarihleri yanlış seçtiysen Tarihleri düzenle ile düzeltirsin; yeni program açmana gerek yok.", "p-program-acildi", "baslik", zoom=True),
            S("Programlar menüsü, öğrencinin bütün haftalarını listeler. Her satırda tarih aralığı ve kaç görev olduğu yazar; boş bir program boş diye işaretlenir. Satırdaki kalemle tarihleri düzeltir, çöp kutusuyla programı silersin. Programı silmek görevleri silmez; istersen görevleri de silme seçeneği ayrıca sorulur.", "p-programlar", "menu", zoom=True),
            S("Tarihleri düzenle penceresi böyle görünür. Tarihleri değiştirdiğinde görevler yerinde kalır, çünkü görevler programa değil, tarihine bağlıdır.", "p-tarih-duzenle", "pencere", zoom=True),
            S("Şimdi sayfanın düzenine bakalım. En üstte Hafta Izgarası var: haftanın bütün günleri yan yana, tek bakışta. Bir güne tıklayınca o günün düzenleyicisi aşağıda açılır. Görevleri günler arasında taşıma ve kopyalama da bu ızgarada yapılır.", "p-duzen-ust", "izgara", zoom=True),
            S("Aşağıda solda gün listesi var; her günün yanında kaç görevin bittiği yazar. Ortada seçtiğin günün kartı açılır. Aynı anda tek bir gün açıktır, böylece sayfa uzamaz.", "p-duzen-alt", "fihrist", zoom=True),
            S("Sağda Kaynak Durumu durur: Elif'in kitaplarında hangi ünitede kaç test kaldığını gösterir. En sağdaki ince şeritte de diğer paneller var: Müfredat, Sıradaki, Bloklar ve gerekirse Devret. Bunları ilerideki bölümlerde tek tek kullanacağız.", "p-duzen-alt", "serit", zoom=True),
        ],
    },
    {
        "key": "prog-gorev",
        "title": "Gün kartında görev ekle",
        "subtitle": "Konuyu ara, kaynağı seç, adedi gir",
        "action": None,
        "steps": [
            S("Bugünün kartı açık ve henüz görev yok. Kartın altındaki Yeni görev ekle kutusuna tıklıyorum. Görev eklemenin en hızlı yolu konu aramaktır: öğrencinin ne çalışacağını yazarsın, sistem uygun kaynağı önüne getirir."),
            S("Arama kutusuna tıkladığımda daha bir şey yazmadan öneriler açıldı. Üç grup var. Müfredatta sıradaki: Elif'in kitaplarında sırası gelen konular. Zayıf, tekrar gereken: denemelerde ya da yanlış arşivinde sorun çıkan konular. Son çalıştıkların: son günlerde çalıştığı konular.", "p-ara-oneriler", "liste", zoom=True),
            S("Her konunun altında o konuyu içeren kitapları ve ünitede kaç test kaldığını görürsün. Kapasitesi dolmuş bir ünite gizlenmez, kapasite doldu diye işaretlenir.", "p-ara-oneriler", "liste", zoom=True),
            S("Şimdi aramayı deneyelim. Kutuya Doğrusal yazdım. Doğrusal Denklemler konusu geldi; altında 3D L G S Matematik kitabının ilgili ünitesi ve kalan test sayısı var.", "p-ara-sonuc", "liste", zoom=True),
            S("Kaynağa tıkladım. Mavi şeritte seçimim görünüyor: konu, ders ve kitap. Adet kutusu kendiliğinden doldu. Bu sayı, senin bu derste genelde verdiğin test sayısından gelir; sağda nedenini yazar. İstersen değiştirirsin.", "p-ara-secildi", "adet", zoom=True),
            S("Ekle'ye bastım. Görev bugünün kartına düştü. Satırda ders, konu ve test sayısı görünüyor. Bu üç test, kitabın o ünitesinden ayrıldı; yani başka bir güne aynı testleri yanlışlıkla bir daha veremezsin.", "p-eklendi", "kart", zoom=True),
            S("Bazen öğrenci o konuyu kendi kaynağından ya da okulda çalışır. O zaman konunun altındaki Kaynak belirtmeden ver seçeneğini kullan. Görev yine konuya bağlanır ve müfredat takibine girer, ama hiçbir kitaptan test ayrılmaz.", "p-kaynaksiz", "buton", zoom=True),
            S("Test dışında bir görev vermek istersen kutunun altındaki tiplerden birini seç ya da Ayrıntılı form'a geç. Burada yedi görev tipi var: Test, Deneme, Blok, Video, Özet, Tekrar ve Diğer. Örneğin bir L G S denemesini kitapsız, yalnız adı ve soru sayısıyla verebilir, bir video dersini bağlantısıyla ekleyebilirsin.", "p-ayrintili", "tipler", zoom=True),
            S("Görevin gün içindeki yerini de belirleyebilirsin. Ayrıntılı formdaki Periyot seçeneğiyle Sabah, Öğle ya da Akşam seçersin. Salı gününe bir sabah, bir de akşam görevi ekledim. Gün kartı artık bölümlere ayrıldı ve her bölüm kendi rengiyle görünüyor.", "p-periyot", "kart", zoom=True),
            S("Her bölümün altındaki düğmeyle doğrudan o bölüme ekleme yaparsın; örneğin Sabaha ekle. Görevleri sürükleyerek bir bölümden diğerine de taşıyabilirsin. Satırlardaki turuncu taslak etiketi, görevin henüz öğrenciye gitmediğini söyler; yayınlamayı ayrı bir bölümde göreceğiz.", "p-periyot", "ekle", zoom=True),
        ],
    },
    {
        "key": "prog-panel",
        "title": "Kaynak Durumu ve Müfredat'tan görev",
        "subtitle": "Kalan testi gör, oradan ver; konuyu kapat",
        "action": None,
        "steps": [
            S("Görev vermenin ikinci yolu sağdaki Kaynak Durumu paneli. Çarşamba gününü seçtim. Panelde Matematik'i, sonra 3D L G S Matematik kitabını açtım. Her ünitenin satırında çözülen, programdaki ve kalan test sayısı yazar.", "p-kaynak", "panel", zoom=True),
            S("Kalan testi olan bir ünitenin yanındaki artı düğmesi o üniteden görev verir. Veri Analizi'nin artısına basıyorum.", "p-kaynak", "arti", click=True, zoom=True),
            S("Satırın hemen altında bir seçici açıldı: kaç test? Mavi işaretli sayı, bu derste genelde verdiğin adettir. Bir sayıya tıklamak görevi doğrudan yazar; başka bir adet istersen kutuya yazarsın. Kapasiteyi aşacak sayılar turuncu görünür. Uyarı verilir ama engellenmez, çünkü kitabın test sayısı gerçeği her zaman yansıtmayabilir.", "p-kaynak-sec", "secici", zoom=True),
            S("İkiye bastım. Görev seçili güne, yani çarşambaya yazıldı ve paneldeki sayılar aynı anda güncellendi.", "p-kaynak-eklendi", "kart", zoom=True),
            S("Şimdi Müfredat paneline geçelim. Sağdaki şeritte Müfredat'a tıkladım. Panel düzenleyicinin üstünde geçici olarak açıldı. Ders seçiciyle dersi değiştirirsin. Liste, dersin müfredat sırasındaki konulardır; her konunun yanında durumu yazar.", "p-mufredat", "panel", zoom=True),
            S("Eşitsizlikler konusuna tıkladım. Konunun ayrıntısı açıldı. En üstteki uyarıya dikkat et: son denemelerde bu konudan bir yanlış var, kapatmadan önce bakmak gerekir. Altında çözülen test, doğruluk oranı, kalan test, denemedeki ve arşivdeki yanlışlar yazar. Bir konuyu bitirip bitirmediğine karar verirken ihtiyacın olan her şey burada.", "p-mufredat-konu", "panel", zoom=True),
            S("Kaynak bölümünde bu konuyu içeren kitaplar listelenir. Birden çok kitap varsa sistem yarıda kalanı devam rozetiyle öne alır. Test ver düğmesine bastım; aynı seçici açıldı. Sayıyı seçince görev seçili güne yazılır.", "p-mufredat-ver", "secici", zoom=True),
            S("Öğrenci bir konuyu bitirdiyse Konuyu kapat düğmesine basarsın. Kapatılan konu müfredatta tamamlanmış sayılır ve sıradaki konu önerilerinde bir daha çıkmaz. Kararı sen verirsin; istersen sonradan Yeniden aç dersin. Üslü İfadeler'de testler bitmiş, ama denemede yanlışlar var; bu yüzden sistem önce bakmanı öneriyor.", "p-mufredat-kapat", "kapat", zoom=True),
            S("Şeritteki her panel iki şekilde açılır. Raptiyesi dolu olan paneller sağda her zaman açık durur; Kaynak Durumu böyle. Diğerleri şeritten tıkladığında geçici açılır ve Esc ile kapanır. Bir paneli sık kullanıyorsan açıkken Sabitle'ye bas; artık her açılışta yerinde olur.", "p-serit", "serit", zoom=True),
        ],
    },
    {
        "key": "prog-izgara",
        "title": "Hafta ızgarası: taşı, kopyala, yay",
        "subtitle": "Görevleri günler arasında yönet",
        "action": None,
        "steps": [
            S("Hafta Izgarası haftanın bütün görevlerini yan yana gösterir. Görevler derse göre gruplanır; her satırın başındaki işaret yapılıp yapılmadığını söyler. Bir görevin üzerine gelince kitabı, ünitesi ve ünitede kalan test sayısı görünür.", "p-izgara", "izgara", zoom=True),
            S("Bir görevi başka güne almanın en kolay yolu sağ tık. Pazartesideki görevin üzerine sağ tıkladım. Menüde dört seçenek var: başka güne taşı, başka güne kopyala, günü düzenle ve görevi sil.", "p-sagtik", "menu", zoom=True),
            S("Başka güne kopyala'yı seçtim. Izgara hedef gün seçme moduna geçti: seçebileceğin günler turuncu çerçeveyle işaretlendi, geçmiş günler soluk. Alttaki şerit ne yaptığını hatırlatır; vazgeçmek için Esc'ye basarsın.", "p-hedef", "bant", zoom=True),
            S("Perşembeye tıkladım. Görevin bir kopyası perşembeye eklendi. Kopyalar taslak olarak eklenir; yani yayınlayana kadar öğrenci görmez. Aynı görev o günde zaten varsa sistem ikinci kez eklemez.", "p-kopyalandi", "hucre", zoom=True),
            S("Taşıma da aynı şekilde çalışır. Çarşambadaki bir görevi sağ tıkla Başka güne taşı ile cumaya aldım. Fareyle de yapabilirsin: görevi sürükleyip başka bir güne bırakırsan taşınır, Ctrl tuşuna basılı tutarak bırakırsan kopyalanır.", "p-tasindi", "hucre", zoom=True),
            S("Her gün tekrar eden bir çalışma için Haftaya yay özelliğini kullan. Gün kartında görevin satırındaki takvim simgesine basıyorum.", "p-yay-dugme", "dugme", click=True, zoom=True),
            S("Pencerede görevin çoğaltılacağı günleri seçersin. Kaynak gün ve geçmiş günler seçilemez. Ben hafta sonunu çıkardım. Altındaki kutu önemli: bölüm biterse kitabın sıradaki bölümünden devam et. Ünitede yeterli test kalmazsa kopyalar kitabın sıradaki ünitesinden devam eder. Dört güne yay'a basıyorum.", "p-yay", "pencere", zoom=True),
            S("Görev seçtiğim günlere taslak olarak çoğaltıldı. Perşembeye zaten kopyaladığım için o gün atlandı; aynı görev bir güne iki kez yazılmaz. Her gün kitaptan ayrı testler ayrıldı. Kaynak yetmeyen gün olursa sistem bunu açıkça söyler.", "p-yayildi", "izgara", zoom=True),
        ],
    },
    {
        "key": "prog-iskelet",
        "title": "İskelet ve öneriler",
        "subtitle": "Her hafta tekrar eden düzen, kendiliğinden",
        "action": None,
        "steps": [
            S("Çoğu öğrencinin haftası birbirine benzer: hangi gün hangi ders çalışılacağı, günlük paragraf rutini, dershanede işlenen dersler. Her hafta programı sıfırdan kurmamak için iskelet kullanırsın. İskelet görev değildir; programa kesik çizgili öneriler düşürür, sen onaylayınca görev olur."),
            S("Üstteki İskelet oluştur düğmesine bastım. Haftalık iskelet penceresi açıldı. Solda haftanın günleri, sağda seçtiğin günün satırları var. İskeleti elle de kurabilirsin, ama en hızlısı Bu haftayı iskelet yap düğmesi.", "p-iskelet-bos", "yap", click=True, zoom=True),
            S("Bastığımda bu haftanın görevlerinden her gün için ders ve kaynak satırları çıkarıldı. Soldaki listede her günün satırları görünüyor. Salı'yı seçtim.", "p-iskelet-gun", "gunler", zoom=True),
            S("Her satır bir kart. Ders, satır türü, gün içindeki yeri ve günlük test sayısı burada. Ana kaynak, konunun hangi kitaptan devam edeceğini söyler. İkinci kaynak seçersen konu ana kitapta bitince ikinci kitapta da tamamlanır. Kartın altındaki cümle bu satırın ne yapacağını sade bir dille anlatır.", "p-iskelet-satir", "satir", zoom=True),
            S("Üç satır türü var. Konu satırı kitapta kaldığı konudan devam eder. Okul ya da dershane dersi, o gün okulda işlenen derstir; sistem o gün hangi konunun işlendiğini sorar. Salı gününe Fen Bilimleri için böyle bir satır ekledim.", "p-iskelet-capa", "satir", zoom=True),
            S("Üçüncü tür rutin: her gün aynı şekilde yapılan çalışma, örneğin paragraf. Türkçe için bir rutin ekledim, kaynağını Zoom Türkçe kitabı yaptım ve günde iki test yazdım. Karışık seçeneğinde her gün kitabın farklı bölümlerinden birer test gelir; sırayla seçeneğinde kaldığı yerden devam eder.", "p-iskelet-rutin", "satir", zoom=True),
            S("Bir günün düzenini başka günlere de aktarabilirsin. Bu günü başka günlere kopyala'ya basınca günleri seçersin. Dikkat: seçtiğin günlerin mevcut satırları değişir. Ayarları bitirip Kaydet'e bastım.", "p-iskelet-kopya", "panel", zoom=True),
            S("İskeletin gücü gelecek haftada görünür. Gelecek hafta için yeni bir program açtım. Izgarada boş günlere kesik çizgili öneriler düştü; görev değiller, henüz hiçbir kitaptan test ayrılmadı.", "p-oneri-izgara", "izgara", zoom=True),
            S("Salı'yı açtım. Kartta İskeletten öneriler bölümü var. Her satırda ders, kaynak ve öneri rozeti görünüyor. Rutin satırlarını tek tek onaylamak zorunda değilsin: Rutinleri onayla düğmesi hepsini birden yazar.", "p-oneri", "oneriler", zoom=True),
            S("Matematik önerisine tıkladım. Altında seçenekler açıldı. Her seçenek bir konu: devam, sıradaki, yeni konu ya da tekrar. Yanında hangi kitaptan kaç test olduğu ve gerekçesi yazar; örneğin dünün devamı. Renkli rozetler bilgi verir: denemede kaç yanlış var, arşivde kaç açık yanlış var, görevlerde doğruluk ne. Bu sayede seçimi körü körüne değil, bilgiyle yaparsın.", "p-oneri-serit", "cip", zoom=True),
            S("İlk seçeneğe tıkladım. Öneri gerçek bir göreve dönüştü ve testler kitaptan ayrıldı. Böylece iki tıkla bir görev yazmış oldum.", "p-oneri-kabul", "kart", zoom=True),
            S("Okul ya da dershane dersi satırına tıklayınca sistem önce sorar: bugün bu derste hangi konu işlendi? Altındaki seçeneklerden işlenen konuyu seçersin.", "p-capa-soru", "serit", zoom=True),
            S("Konuyu seçince Konuyu yay penceresi kendiliğinden açıldı. Konunun kalan testleri sonraki boş günlere dağıtılır. Her günün kapasitesi, o gün zaten yazılı testler ve dershane payı hesaba katılır. Günlük adedi değiştirebilir, bir günü çıkarabilirsin. Onaylayınca testler seçtiğin günlere yazılır.", "p-konu-yay", "pencere", zoom=True),
            S("Rutinleri onayla'ya basınca hiçbir şey hemen yazılmaz; önce bu önizleme açılır. Hangi gün hangi kitaptan kaç test yazılacağını görürsün. Günlük test sayısı olağandışı yüksekse kırmızı uyarı çıkar. Kontrol edip onaylarsın.", "p-rutin-onizle", "pencere", zoom=True),
        ],
    },
    {
        "key": "prog-yayin",
        "title": "Taslak, yayın ve veliye duyuru",
        "subtitle": "Programı öğrenciye ve veliye ulaştır",
        "action": {
            "label": "Programını yayınla ve veliye duyur",
            "href": "/teacher/students",
            "checkKey": "yayinla-duyur",
            "doneLabel": "Programın yayında",
            "hint": "Yol: öğrencinin Program sayfası → üstte \"Tüm haftayı yayınla\" → \"Veliye duyur\".",
            "optional": True,
        },
        "steps": [
            S("Gelecek günlere eklediğin görevler taslak olarak başlar. Taslak görev senin panelinde görünür ama öğrencinin paneline inmez. Böylece haftayı rahatça kurar, hazır olunca tek seferde açarsın. Sayfanın üstündeki turuncu bant kaç görevin taslakta beklediğini söyler.", "p-taslak", "bant", zoom=True),
            S("İstersen günü tek tek yayınlarsın: taslak görevi olan günün kartında Bu günü yayınla düğmesi çıkar.", "p-gun-yayinla", "dugme", zoom=True),
            S("Bütün haftayı yayınlamak için üstteki Tüm haftayı yayınla düğmesine basıyorum. Sistem onay ister; onayladım.", "p-taslak", "dugme", click=True, zoom=True),
            S("Bütün görevler öğrenciye açıldı; taslak bandı kayboldu. Yayınlamak veliye bildirim göndermez. Veliye ayrıca duyurman gerekir.", "p-yayinlandi", "izgara", zoom=True),
            S("Veliye duyur düğmesine bastım. Hiçbir şey gönderilmeden önce bu önizleme açılır. Üstte kaç yayınlanmış görevin iletileceği, altında alıcı veliler ve hangi kanaldan gideceği yazar. Sonra velinin göreceği program gün gün listelenir. Kontrol edip Velilere gönder dersin. Aynı veliye son yirmi dört saatte duyuru gittiyse tekrar gönderilmez.", "p-veli", "pencere", zoom=True),
            S("Yazdır düğmesi programın kâğıda basılabilir hâlini yeni sekmede açar. Haftanın bütün günleri tek sayfada, yatay olarak yer alır. Öğrencin bilgisayar kullanmıyorsa bu sayfayı yazdırıp verirsin.", "p-yazdir", "sayfa", zoom=True),
        ],
    },
    {
        "key": "prog-takip",
        "title": "Hafta boyunca takip",
        "subtitle": "Kim ne yaptı, hafta nereye gidiyor",
        "action": None,
        "steps": [
            S("Elif bugünün görevini kendi panelinden tamamladı olarak işaretledi. Izgarada o görevin başındaki işaret onay işaretine döndü ve günün altında kaç görevin bittiği yazıyor. Kısmen yapılan görevler yarım daireyle görünür.", "p-takip-izgara", "bugun", zoom=True),
            S("Gün kartında görevin yanında tamam yazıyor. Öğrenci doğru ve yanlış sayısını girdiyse burada görünür; girmediyse sen de ekleyebilirsin. Gün listesinde her günün çubuğu tamamlanma oranına göre yeşil, turuncu ya da kırmızı olur.", "p-takip-gun", "kart", zoom=True),
            S("Izgaranın altındaki Haftanın Ders Dengesi şeridi emeğin hangi derse gittiğini gösterir. Test ya da görev sayısına göre yüzdeyi değiştirebilirsin. Bir dersin payı çok düşükse programı kurarken bunu fark edersin.", "p-denge", "denge", zoom=True),
            S("Hafta notları, o haftayla ilgili kısa hatırlatmalar içindir; örneğin perşembe dersine son denemeyi getir. Öğrenci de bu notları görür ve yapılanlar işaretlenir.", "p-notlar", "notlar", zoom=True),
            S("Bazen öğrenci sistemde olmayan bir kaynaktan ödev alır; örneğin özel ders öğretmeninin verdiği kırk test. Bunun için şeritteki Bloklar panelinde bir serbest blok açarsın. Blok, toplam testi ve günlere dağıttığın kısmı ayrı ayrı sayar; ne kadar kaldığını hep görürsün.", "p-bloklar", "panel", zoom=True),
            S("Bir hafta biterken yapılmadan kalan görevler varsa şeritte Devret paneli çıkar. Bu görevleri sürükleyerek ya da Ekle ile yeni haftaya taşırsın; taşınan görev listeden düşer. Hepsi bu kadar. Programla ilgili her şeyi gördün; sıradaki konu denemeler."),
        ],
    },
]
