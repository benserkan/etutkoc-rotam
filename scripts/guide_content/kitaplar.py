"""Rota Rehberi — KİTAPLAR serisi (koç). İçerik kaynağı.

`python -m scripts.guide_content.build` bu modülü okur ve
web/components/guide/coach-guide-content.json içindeki "Kitaplar" konusunu
yeniden yazar. Metinler yalnız GERÇEK ekranlarda görünen etiketleri kullanır
(envanter: 2026-10-05). Seslendirme bu metinlerden üretilir (generate_guide_audio).

Adım: (metin, ekran, vurgu kutusu, tıklama animasyonu, yakınlaştırma)
"""

MODULE = "Kitaplar"


def S(caption, shot=None, target=None, click=False, zoom=False, speech=None):
    d = {"caption": caption, "shot": shot, "target": target, "click": click, "zoom": zoom}
    if speech:
        d["speech"] = speech
    return d


CHAPTERS = [
    {
        "key": "kitap-kutuphane",
        "title": "Kütüphane sayfası",
        "subtitle": "Kitapların nerede, hangi durumda",
        "action": None,
        "steps": [
            S("Merhaba, ben Rota. Bu eğitimde kitaplarla ilgili her şeyi gerçek ekranlar üzerinde birlikte yapacağız. Neden kitaptan başlıyoruz? Çünkü Etütkoç Rotam'da program kitaptan kurulur. Öğrencine verdiğin her test, bir kitabın bir ünitesinden gelir. Kalan test sayısı, müfredat ilerlemesi ve deneme analizleri de bu ünitelere bağlıdır."),
            S("Sol menüden Kitaplar'a tıklıyorum. Karşımıza kütüphane çıkıyor. Öğrencilerine görev verdiğin bütün kitaplar burada durur.", "k-kutuphane", "nav", click=True),
            S("Sayfanın başındaki cümleyi aklında tut. Bir kitabın üniteleri ve test sayıları ne kadar doğruysa, programdaki kalan test de o kadar doğru olur. Kitabı bir kez doğru tanıtırsan, sonraki haftalarda hiç uğraşmazsın.", "k-kutuphane", "baslik", zoom=True),
            S("Başlığın altındaki bu kart, şu an izlediğin eğitimi açar. Bir bölümü yarıda bırakırsan kaldığın yeri hatırlarım. Eğitimin tamamını izlediğinde kart küçük bir düğmeye dönüşür; istediğin zaman yeniden izlersin.", "k-kutuphane", "rehber", zoom=True),
            S("Üstteki dört sekme kütüphanenin bölümleri. Kitaplar, bütün kitapların. Kitap setleri, birkaç kitabı paket yapıp öğrencilere tek seferde atamak için. Kitap şablonları, bir kitabın ünite yapısını başka bir kitaba aktarmak için. Görev şablonları da sık verdiğin görevleri programa tek tıkla eklemek için.", "k-kutuphane", "sekmeler", zoom=True),
            S("Bu dört kart kütüphanenin özeti. İlki toplam kitap, ünite ve test sayısı. İkincisi en az bir öğrencide kullanılan kitaplar, üçüncüsü henüz kimseye atanmamış kitaplar. Dördüncüsü en önemlisi: eksiği olan kitaplar. Bir karta tıklayınca liste o gruba süzülür.", "k-kutuphane", "durum", zoom=True),
            S("Eksiği olanlar kartına tıkladım. Bir kitabın hiç ünitesi yoksa ya da bazı üniteleri müfredat konusuna bağlanmamışsa kartında bu turuncu uyarı çıkar. Ünitesi olmayan kitaptan görev verilemez. Bağlanmamış ünite ise konu analizlerinde sayılmaz. Bu grubu boş tutmak, sistemin doğru çalışması demektir.", "k-kutuphane-eksik", "uyari", zoom=True),
            S("Kitap çoğaldıkça süzgeçler işine yarar. Üstteki şerit müfredatı seçer: L G S, Maarif ya da sınav müfredatı gibi. Arama kutusuna kitap ya da yayınevi adı yazarsın; klavyede eğik çizgi tuşu aramayı doğrudan açar. Yanındaki listelerle ders, kitap türü ve sınıfa göre süzer, sıralamayı değiştirirsin.", "k-kutuphane", "suzgec", zoom=True),
            S("Bir kitap kartını okuyalım. Üstte türü ve sınıf seviyesi yazar; katalogdan geldiyse Katalogdan etiketi görünür. Ortada ünite ve test sayısı var. Altındaki çubuk, kaç ünitenin müfredat konusuna bağlandığını gösterir; hepsi bağlıysa yeşildir. En altta kaç öğrencide kullanıldığı yazar. Karta tıklarsan kitabın sayfası açılır.", "k-kutuphane-kart", "kart", zoom=True),
            S("Sağ üstteki düğmeyle liste görünümüne geçebilirsin. Çok kitabın varsa bu tablo daha hızlıdır. Bir sütun başlığının üzerine gelince o sütunun neyi saydığını anlatan açıklama çıkar.", "k-kutuphane-liste", "tablo", zoom=True),
        ],
    },
    {
        "key": "kitap-katalog",
        "title": "Hazır kitap ekle",
        "subtitle": "Ortak katalogdan, yaklaşık on saniyede",
        "action": {
            "label": "Kütüphaneye git, ilk kitabını ekle",
            "href": "/teacher/library/new",
            "checkKey": "kitap-ekle",
            "doneLabel": "Kitabın eklendi",
            "hint": "Yol: sol menü → Kitaplar → sağ üstte \"Yeni kitap\" → \"Hazır bir kitap ekle\".",
        },
        "steps": [
            S("Yeni bir kitap eklemek için kütüphanenin sağ üstündeki Yeni kitap düğmesine tıklıyorum.", "k-kutuphane", "yeni", click=True, zoom=True),
            S("Karşımıza bir sihirbaz çıktı. Dört adımı var: Başlangıç, Üniteler, Eşleştirme ve Öğrenci. Hangi adımda olduğunu bu şeritten takip edersin; biten adımlar yeşile döner.", "k-sihirbaz-yol", "adimlar", zoom=True),
            S("İlk soru: ne yapmak istiyorsun? Dört yol var. Hazır bir kitap ekle, en hızlısı. Kitabım elimde, tarat. Kitabı kendim tanımlayacağım. Ve kayıtlı bir şablonun varsa, kendi şablonumdan başla. Yanlış yolu seçersen dert etme; istediğin an geri dönüp değiştirirsin.", "k-sihirbaz-yol", "secenekler", zoom=True),
            S("En hızlı yoldan başlayalım: hazır bir kitap ekle. Ortak katalogda yüzlerce kitabın üniteleri ve test sayıları hazır duruyor. Bunlar kitapların içindekiler sayfalarından tek tek okunup doğrulandı.", "k-sihirbaz-yol", "hazir", click=True),
            S("Katalogda kitaplar sınav gruplarına ayrılmış: L G S ve ortaokul, T Y T ve A Y T. Bir gruba dokununca liste daralır. Altındaki listelerle ders, tür ve yayınevine göre de süzebilirsin.", "k-katalog", "gruplar", zoom=True),
            S("En kısa yol aramak. Kitabın adından birkaç kelime yazman yeterli; ben Zoom Türkçe yazdım. Kelimelerin sırası önemli değil.", "k-katalog-ara", "arama", zoom=True),
            S("Kitaba dokununca bütün bölümleri test sayılarıyla açılır. Oktan sonra yazan ad, o bölümün bağlı olduğu resmi müfredat konusudur. Elindeki kitapla karşılaştır: bölümler ve test sayıları tutuyorsa doğru kitap budur.", "k-katalog-acik", "bolumler", zoom=True),
            S("Doğruysa Kütüphaneme ekle düğmesine basıyorum. Kitap bütün üniteleri, test sayıları ve müfredat eşleşmeleriyle birlikte kütüphaneme geliyor.", "k-katalog-acik", "ekle", click=True, zoom=True),
            S("İkinci adım, üniteler. Sistem ünitelerin eklendiğini ve kaçının müfredata eşli olduğunu söylüyor. Burada yapacak bir şey yok; Devam düğmesine basıyorum.", "k-katalog-uniteler", "hazir", zoom=True),
            S("Üçüncü adım, müfredat eşleştirme. Katalogdan gelen kitapta eşleşmeler hazır gelir; göz atıp devam edersin. Bu adımın ayrıntısını birazdan, taratarak eklediğimiz kitapta göreceğiz.", "k-katalog-esles", "devam"),
            S("Dördüncü adım: kitabı hangi öğrencilere atayalım? Elif'i işaretliyorum ve öğrenciye ata ve bitir düğmesine basıyorum. Şimdi atamak istemezsen Atla dersin; sonra öğrencinin sayfasından da atayabilirsin.", "k-katalog-ogrenci", "ata", click=True, zoom=True),
            S("Kitap hazır. Özet, kaç ünite eklendiğini, kaçının müfredata eşli olduğunu ve kaç öğrenciye atandığını gösteriyor. Hepsi bu kadar: yaklaşık on saniyede, test sayıları birebir doğru bir kitap.", "k-katalog-ozet", "ozet", zoom=True),
        ],
    },
    {
        "key": "kitap-tarat",
        "title": "Kitabı taratarak ekle",
        "subtitle": "Katalogda yoksa: kapak ve içindekiler",
        "action": None,
        "steps": [
            S("Kitabın katalogda yoksa ikinci yol: kitabım elimde, tarat. Kapağın ve içindekiler sayfalarının fotoğrafını çekersin ya da kitabın P D F dosyasını yüklersin. Telefondan girdiysen kamera doğrudan açılır. Bu okuma kredi harcamaz.", "k-tarat-yol", "yukle", click=True, zoom=True),
            S("Fotoğrafları yükledim. Sistem önce kapaktan kitabı tanır. Kitap katalogda varsa hazır kaydı önüne getirir; okuma yapmadan onu eklersin. Yoksa içindekiler sayfası birbirinden bağımsız iki kez okunur. Bu yarım dakika ile bir dakika sürer; bu sırada sayfadan ayrılma.", "k-tarat-isleniyor", "durum", zoom=True),
            S("Bu kitap katalogda yokmuş; içindekilerden bölümler okundu. Kitabın adı ve yayınevi kapaktan otomatik dolduruldu. Aşağıda okunan bölümleri görüyorsun.", "k-tarat-sonuc", "bar", zoom=True),
            S("Kitap adı ve yayınevi kapaktan geldi. Ben yalnız dersi seçip Oluştur ve bölümlere geç düğmesine basıyorum. Kitap oluşuyor ve okunan bölümler bir sonraki adımda kontrolüne geliyor.", "k-tarat-form", "olustur", click=True, zoom=True),
            S("Bu mavi not önemli. İçindekiler sayfasında test sayısı yazmıyordu, yalnız sayfa numaraları vardı. Sistem her testin yaklaşık iki sayfa olduğunu varsayarak test sayısını sayfa aralığından tahmin etti. Bu yüzden satırlarda tahmini etiketi var. Tahmin bir başlangıçtır; kitabı açıp karşılaştırman gerekir.", "k-tarat-tahmini", "not", zoom=True),
            S("Bir satırın sayısını düzelttiğinde o satırdaki tahmini etiketi kalkar. İki okumanın uyuşmadığı satırlar sarı, test sayısı hiç bulunamayan satırlar kırmızı görünür. Kaydetmeden önce bunlara bak.", "k-tarat-duzelt", "satir", zoom=True),
            S("Bütün bölümlerde test sayısı aynıysa sağ alttaki kutuya sayıyı yazıp Tümüne uygula dersin; hepsi tek seferde düzelir.", "k-tarat-duzelt", "tumu", zoom=True),
            S("Kontrolü bitirince bölümleri kitaba ekle düğmesine basıyorum ve Devam diyorum.", "k-tarat-duzelt", "tumu"),
            S("Eşleştirme adımına geldik. Burada her ünitenin hangi resmi müfredat konusu olduğunu işaretliyoruz. Sistem bölüm adlarını resmi konularla karşılaştırıp çoğunu kendisi eşledi.", "k-tarat-esles", "tablo", zoom=True),
            S("Eşleşmeyenler için Yapay zekâ ile öner düğmesine basıyorum. Öneriler sarı renkte gelir; her satırı kontrol eder, yanlışsa açılır listeden doğru konuyu seçersin. Karşılığı olmayan bölüm, örneğin karışık bir tarama testi, eşleşmemiş kalabilir. Bu bir hata değildir.", "k-tarat-esles-ai", "tablo", zoom=True),
            S("Kitabı sen oluşturduğun için son adımda bir seçenek daha çıkar: bu kitabın yapısını ortak kataloğa öner. Onaylanırsa diğer koçlar bu kitabı tek tıkla kullanır. Adın görünmez, öğrenci verisi paylaşılmaz.", "k-tarat-ogrenci", "katalog", zoom=True),
        ],
    },
    {
        "key": "kitap-elle",
        "title": "Kitabı kendin tanımla",
        "subtitle": "Föyler ve katalogda olmayan kaynaklar",
        "action": None,
        "steps": [
            S("Üçüncü yol: kitabı kendim tanımlayacağım. Kendi hazırladığın föyler ya da katalogda olmayan kaynaklar için. Önce kitabın adını yazıyorum. Sonra hedef sınıf seviyesini seçiyorum: L G S, lise, mezun ya da tüm seviyeler. İnce ayar ile özel bir sınıf aralığı da verebilirsin.", "k-elle-form", "form", zoom=True),
            S("Ders listesi müfredat gruplarına ayrılmıştır ve hedef seviyene göre süzülür. Y K S kitabı ekliyorsan dersi sınav müfredatı grubundan, yani T Y T ya da A Y T dersinden seç. Deneme analizleri ve konu takibi en doğru bu derslerde çalışır.", "k-elle-ders", "liste", zoom=True),
            S("Kitap oluştu, sıra ünitelerde. Dört yöntem var. Fotoğraftan oku, önerilen yol: içindekiler sayfasından üniteler ve test sayıları birebir okunur. Resmi konulardan ekle: dersin müfredat konuları hazır gelir. Yapay zekâ önersin: ücretli pakette çalışır ve yalnız tahmin üretir. Elle gir: üniteleri tek tek yazarsın.", "k-elle-yontem", "yontemler", zoom=True),
            S("Ben resmi konulardan ekliyorum. Kitabın hedefine göre sınıf ön seçili gelir. Her konu varsayılan bir test sayısıyla eklenir; sonra kendi kitabına göre düzeltir, fazlalıkları çıkarırsın.", "k-elle-resmi", "panel", zoom=True),
            S("Resmi konulardan eklenen ünitelerin hepsi otomatik eşlenir; bu adımda yapacak bir şey kalmaz. Bu bağın anlamı şu: öğrencinin müfredatta nerede olduğunu ve hangi konuyu ne kadar çalıştığını sistem bu bağdan bilir.", "k-elle-esles", "mesaj", zoom=True),
        ],
    },
    {
        "key": "kitap-detay",
        "title": "Kitap sayfası",
        "subtitle": "Bölümleri düzelt, dersi değiştir",
        "action": None,
        "steps": [
            S("Kütüphanede bir kitaba tıklayınca kitabın sayfası açılır. Başlığın altında bölüm, test ve öğrenci sayısı yazar. Sağ üstte Dersi değiştir ve Kitabı sil düğmeleri var.", "k-detay", "baslik", zoom=True),
            S("Bölümler sekmesinde her ünite bir satırdır. Bağlı olduğu müfredat konusunu, test sayısını, rezervde ve tamamlanmış testleri görürsün. Düzenle ile adını ya da test sayısını değiştirirsin. Rezervde ya da tamamlanmış testi olan bölüm silinemez; çöp kutusu bu yüzden soluk görünür.", "k-detay", "satir", zoom=True),
            S("Üstteki düğmelerle yeni bölüm ekler, katalog konularından toplu ekleme yaparsın. Müfredata eşleştir düğmesindeki turuncu sayı, kaç bölümün henüz bağlanmadığını gösterir.", "k-detay", "dugmeler", zoom=True),
            S("Müfredata eşleştir penceresi böyle görünür. Her kitap ünitesi için bir resmi konu seçilir. Kaynak sütunu eşleşmenin nereden geldiğini söyler: zaten eşli, otomatik, yapay zekâ önerisi ya da öneri yok. Kontrol edip Uygula dersin.", "k-detay-esles", "tablo", zoom=True),
            S("Kitabı yanlış derse bağladıysan Dersi değiştir düğmesini kullan. Örneğin bir Y K S kitabını sınav müfredatındaki derse taşırsın. Ders değişince eski eşleşmeler sıfırlanır, bölümler ve öğrencilerin ilerlemesi korunur. Sonra müfredata yeniden eşlersin.", "k-detay-ders", "pencere", zoom=True),
            S("Bir kitap hiçbir öğrenciye atanmamışsa sayfanın üstünde bu uyarıyı görürsün: atanmayan kitap, program yaparken öğrencinin listesinde görünmez. Öğrenci ata düğmesi seni Öğrenciler sekmesine götürür; öğrencileri işaretleyip Kaydet dersin. Rezervi olan öğrenci kilitli görünür ve çıkarılamaz.", "k-detay-uyari", "uyari", zoom=True),
        ],
    },
    {
        "key": "kitap-ata",
        "title": "Öğrenciye ata",
        "subtitle": "Tek tek ya da kitap setiyle",
        "action": {
            "label": "Öğrenci ekle ve kitabını ata",
            "href": "/teacher/students",
            "checkKey": "ogrenci-ata",
            "doneLabel": "Öğrenci eklendi ve kitap atandı",
            "hint": "Yol: sol menü → Öğrenciler → \"Yeni öğrenci\" ile ekle → öğrencinin sayfasında Kitaplar sekmesi → \"Kitap ata\".",
        },
        "steps": [
            S("Kitap atamanın en rahat yeri öğrencinin sayfasıdır. Öğrenciler sayfasından Elif'i açtım ve Kitaplar sekmesine geçtim. Bu bölümün adı Kaynaklar: Elif'in bütün kitapları ve her kitapta ne kadar ilerlediği burada.", "k-ogr-kitaplar", "panel", zoom=True),
            S("Sağ üstteki Kitap ata düğmesine basıyorum.", "k-ogr-kitaplar", "ata", click=True, zoom=True),
            S("Bu pencerede kitap adı, yayınevi ya da derse göre ararsın. Kaynak çipleriyle katalogdan, şablondan ya da elle oluşturulan kitapları ayırırsın. Yalnız öğrencinin sınıfına uygun kutusu varsayılan olarak açıktır; böylece başka sınıfın kitabı listeye karışmaz.", "k-ata-pencere", "suzgec", zoom=True),
            S("Her satırda yayınevi, bölüm ve test sayısı ile kaç öğrencide kullanıldığı yazar. Aynı adla iki kitabın varsa sistem bunu söyler ve kayıt tarihini gösterir; doğru olanı seçersin.", "k-ata-pencere", "liste", zoom=True),
            S("İki kitap seçtim. Alttaki şeritte seçimlerim görünüyor. İki kitabı ata düğmesine bastığımda ikisi de Elif'in kaynaklarına eklenir.", "k-ata-secili", "alt", click=True, zoom=True),
            S("Set'ten uygula sekmesinde, hazırladığın bir kitap setini öğrenciye tek seferde atarsın. Seti seçince içindeki kitaplar listelenir; Elif'te zaten olan kitaplar zaten atalı diye işaretlenir, yalnız eksik olanlar seçili gelir.", "k-ata-set", "panel", zoom=True),
            S("Setleri kütüphanedeki Kitap setleri sekmesinden kurarsın. Örneğin sekizinci sınıf paketi adında bir set yapar, içine o sınıfın kitaplarını koyarsın.", "k-setler", "liste", zoom=True),
            S("Bir setin sayfasında Öğrencilere uygula düğmesi seti birden çok öğrenciye, hatta bir şubenin tamamına tek seferde atar. Sınıfı setin hedefine uymayan öğrenci için uyarı görürsün. Zaten atalı kitaplar atlanır.", "k-set-uygula", "pencere", zoom=True),
        ],
    },
    {
        "key": "kitap-ilerleme",
        "title": "İlerlemeyi takip et",
        "subtitle": "Zaten çözülmüş testler, bağımsız çalışma, arşiv",
        "action": None,
        "steps": [
            S("Kaynaklar sayfasının üstündeki özet, öğrencinin soru bankalarındaki toplam ilerlemesidir. Yeşil çözülen testler, sarı programda bekleyen testler, gri ise programa verilebilecek kalan testlerdir. Deneme kitapları ayrı sayılır.", "k-ogr-ozet", "ozet", zoom=True),
            S("Her kitap kartında yüzde ilerleme ve en önemlisi şu satır var: sıradaki ünite ve oradan kaç test atanabilir. Program yaparken hangi üniteden devam edeceğini buradan görürsün.", "k-ogr-kart", "sirada", zoom=True),
            S("Üniteler satırını açınca her ünitenin durumu görünür: kaç test çözülmüş, kaç test programda, kaç test atanabilir.", "k-ogr-uniteler", "liste", zoom=True),
            S("Öğrenci bir üniteyi sisteme başlamadan önce çözdüyse, o ünitedeki Öğrenci bunu zaten çözmüştü bağlantısına tıkla. Çözdüğü test sayısını yazıp Kaydet dersin. Bu testler çözülmüş sayılır ve programa bir daha verilmez.", "k-ogr-zaten", "editor", zoom=True),
            S("Bu alan düzeltme için de kullanılır. Öğrenci aslında çözmediği bir testi işaretlediyse gerçek sayıyı yaz. Fark en yeni görevden geri alınır; o testler öğrencinin programında yeniden bekliyor olur. Görevi silmen gerekmez.", "k-ogr-azalt", "ipucu", zoom=True),
            S("Öğrenci tatilde ya da kursta, program dışında test çözdüyse Bağımsız çalışma kartından giriş yaparsın. Kitabı seçer, bölümlere çözülen sayıyı yazar, istersen tarih aralığı ve not eklersin. İlerlemeye işle dediğinde kayıt izli tutulur ve kitabın ilerlemesi güncellenir.", "k-bagimsiz", "pencere", zoom=True),
            S("Aynı bildirimi öğrenci de kendi ekranından yapabilir. O zaman beyan senin onayına düşer: Onayla dersen ilerlemeye işlenir, Reddet dersen işlenmez.", "k-bagimsiz-beyan", "beyan", zoom=True),
            S("Bitmiş ya da artık kullanılmayan kitabı Arşivle düğmesiyle listeden kaldırırsın. Arşiv silme değildir: görev geçmişi ve ilerleme korunur, istediğin an arşivden çıkarırsın. Kaldır ise atamayı tamamen siler; rezervi olan kitapta buna izin verilmez.", "k-ogr-kart", "dugmeler", zoom=True),
        ],
    },
    {
        "key": "kitap-kapasite",
        "title": "Test sayısı ve koltuk ızgarası",
        "subtitle": "Kapasite uyarısı, rezerv ve geri alma",
        "action": None,
        "steps": [
            S("Kitaptaki test sayısı artık bir sınır değil, bir yol göstericidir. Bir üniteye kalan kapasiteden fazla test verdiğinde sistem seni uyarır: kayıtlı kapasite aşılacak. Ama görevi yine de oluşturur. Çünkü kitabın test sayısı her zaman gerçeği yansıtmayabilir; karar senindir.", "k-kapasite", "uyari", zoom=True),
            S("Bir kitabın test test durumunu görmek için haftalık program sayfasındaki Kaynak Durumu panelinde, kitabın yanındaki ızgara simgesine tıklıyorum.", "k-kaynak-durumu", "izgara", click=True, zoom=True),
            S("Bu, sinema koltuğu görünümü. Her kutu bir test. Yeşil kutular çözülmüş, sarı kutular programda bekleyen, gri kutular henüz boş testlerdir. Üstte toplamlar yazar. Bir kutunun üzerine gelince hangi tarihte verildiğini görürsün.", "k-koltuk", "sayaclar", zoom=True),
            S("Yeşil bir kutuya tıkladım. Altında bir şerit açıldı: bu test hangi tarihli görevde çözüldü olarak işaretlenmiş. Öğrenci aslında çözmediyse bir test geri al ya da bu görevin tümünü geri al dersin. Görev silinmez; geri alınan test yeniden atanabilir olur.", "k-koltuk-yesil", "serit", zoom=True),
            S("Sarı bir kutuya tıklayınca rezervden çıkarma seçenekleri gelir. Bir test rezervden çıkar dersen görevin test sayısı bir azalır; görevde başka test kalmazsa görev programdan silinir. O günün programında göster bağlantısı seni ilgili güne götürür ve görevi renkli olarak işaretler.", "k-koltuk-sari", "serit", zoom=True),
            S("Nadiren kayıtlı sayaçlarla gerçek görev listesi uyuşmazsa ızgaranın üstünde bir sayaç uyumsuzluğu uyarısı çıkar. Sayaçları düzelt düğmesine bir kez basman yeterlidir; programdaki aktif görevlere dokunulmaz.", "k-koltuk", "sayaclar"),
        ],
    },
    {
        "key": "kitap-sablon",
        "title": "Şablonlar",
        "subtitle": "Kitap şablonu ve görev şablonu",
        "action": None,
        "steps": [
            S("Kitap şablonları sekmesi, bir kitabın ünite yapısını kayıtlı tutar. Aynı yapıdaki başka bir kitabı eklerken, sihirbazda kendi şablonumdan başla yolunu seçersin; üniteler hazır gelir.", "k-sablonlar", "liste", zoom=True),
            S("Şablonu kitabın sayfasındaki Şablon sekmesinden kaydedersin. Aynı sekmeden kayıtlı bir şablonu başka bir kitaba uygulayabilirsin.", "k-detay-sablon", "panel", zoom=True),
            S("Görev şablonları ise başka bir şeydir. Sık verdiğin görevleri kitap, bölüm ve test sayısıyla kaydedersin; örneğin günlük yirmi matematik testi. Program yaparken Şablondan düğmesiyle tek tıkla eklersin.", "k-gorev-sablon", "form", zoom=True),
            S("Kitaplar eğitiminin sonuna geldik. Özetle: kitabı katalogdan, taratarak ya da kendin ekle. Ünitelerini müfredata bağla. Öğrencine ata ve ilerlemesini Kaynaklar sayfasından takip et. Sıradaki eğitim haftalık program; orada bu kitaplardan görev vermeyi göreceğiz."),
        ],
    },
]
