"""Rota Rehberi — DENEMELER serisi (koç). İçerik kaynağı.

`python -m scripts.guide_content.build` bu modülü okur ve
web/components/guide/coach-guide-content.json içindeki "Denemeler" konusunu
yeniden yazar. Metinler yalnız GERÇEK ekranlarda görünen etiketleri kullanır
(envanter: 2026-10-05). Ekranlar: scripts/capture_guide_denemeler.py.
"""

MODULE = "Denemeler"


def S(caption, shot=None, target=None, click=False, zoom=False, speech=None):
    d = {"caption": caption, "shot": shot, "target": target, "click": click, "zoom": zoom}
    if speech:
        d["speech"] = speech
    return d


CHAPTERS = [
    {
        "key": "den-aktar",
        "title": "Deneme sonucunu PDF'ten aktar",
        "subtitle": "Karneyi yükle, kontrol et, kaydet",
        "action": {
            "label": "Öğrencinin ilk deneme sonucunu aktar",
            "href": "/teacher/students",
            "checkKey": "deneme-gir",
            "doneLabel": "Deneme sonucun kayıtlı",
            "hint": "Yol: öğrencinin sayfası → Denemeler sekmesi → \"Deneme sonuç PDF'ini yükle\".",
            "optional": True,
        },
        "steps": [
            S("Son konumuz denemeler. Öğrencinin deneme sonucu sisteme girdiğinde neyi bildiği, neyi unuttuğu ve en çok nereden net kazanacağı ortaya çıkar. Bu eğitimde Elif'in yeni deneme karnesini yükleyecek, sonra bütün analiz tablolarını tek tek okuyacağız."),
            S("Elif'in sayfasında Denemeler sekmesindeyim. Deneme eklemenin iki yolu var. Mor düğme, yayınevinden ya da okuldan gelen konu analizli sonuç karnesini PDF olarak yükler. Sağdaki Elle deneme gir ise PDF'in yoksa netleri yazmak içindir.", "d-panel", "baslik", zoom=True),
            S("Başlığın altındaki kart bu Denemeler eğitimini açar. Kaldığın yeri hatırlarım; bütün bölümleri izleyince kart küçük bir düğmeye dönüşür.", "d-panel", "rehber", zoom=True),
            S("Elle girişte deneme adını, tarihini ve sınav türünü yazarsın. Toplam doğru, yanlış ve boşu girebilir ya da Ders kırılımı ile ders ders yazabilirsin. Net, sınav türüne göre kendiliğinden hesaplanır. Ama dikkat: elle girilen denemede soru bilgisi olmadığı için konu analizine girmez. Mümkünse her zaman PDF kullan.", "d-elle", "pencere", zoom=True),
            S("Şimdi asıl yolu kullanalım. Mor düğmeye bastım. Önce denemenin sınıfını ve türünü seçiyorum: sekizinci sınıf, L G S. Bunları bilmiyorsan Otomatik tespit bırakabilirsin, ama seçersen yanlış tür ihtimali sıfırlanır.", "d-pdf-sec", "beyan", zoom=True),
            S("Karne dosyasını seçtim. Yapay zekâ belgeyi okuyor. Uydurma olmasın diye belge birbirinden bağımsız iki kez okunur ve sonuçlar karşılaştırılır. Yirmi soruluk bir karne yarım dakikada biter; yüz yirmi soruluk bir karne üç ile beş dakika sürebilir. Bu sırada pencereyi kapatma.", "d-pdf-okunuyor", "pencere", zoom=True),
            S("Okuma bitti ve hiçbir şey henüz kaydedilmedi; önce kontrol ediyoruz. Üstte deneme adı, tarihi ve türü var; okunan adı istersen sadeleştirirsin. Altındaki yeşil etiket, yirmi sorunun hepsinin müfredat konusuna otomatik bağlandığını söylüyor.", "d-pdf-onizleme", "kimlik", zoom=True),
            S("Tabloda her soru bir satır: soru numarası, karnede yazan konu ve onun müfredattaki karşılığı, doğru cevap, öğrencinin cevabı ve sonuç. Yayınevi konuya farklı bir ad verdiyse sistem onu senin müfredatına çevirir. Bir konu yanlış bağlandıysa listeden düzeltirsin; düzeltmen öğrenilir ve aynı etiket bir dahaki sefere doğru gelir.", "d-pdf-tablo", "konu", zoom=True),
            S("İki okuma birbirini tutmazsa o satır sarı işaretlenir; belgeyle karşılaştırıp düzeltirsin. Alt çubukta canlı net hesabı görünür. Her şey tamamsa Kontrol ettim, kaydet'e basıyorum.", "d-pdf-alt", "kaydet", click=True, zoom=True),
            S("Deneme kaydedildi. Net on dört, on beş doğru, üç yanlış, iki boş. Konu bazlı hata birikimi de bu denemeyle güncellendi. Yanlışlar varsa altta Yanlışlardan arşive soru seç düğmesi çıkar.", "d-pdf-kaydedildi", "arsiv", click=True, zoom=True),
            S("Bu pencerede yanlış soruları tek tek seçip Yanlış Soru Arşivi'ne eklersin. Her soru için hata türünü de işaretleyebilirsin, örneğin bilgi eksiği ya da işlem hatası. Arşive giren soru aralıklı tekrar kuyruğuna girer ve öğrenci onu ileride yeniden çözer.", "d-arsiv", "pencere", zoom=True),
            S("Bir güvence daha: aynı karneyi yanlışlıkla ikinci kez yüklersem sistem belgeyi tanır. Bu PDF zaten aktarılmış der, belgeyi yeniden okumaz ve kredi harcamaz. Böylece bir deneme analizde iki kez sayılmaz.", "d-mukerrer", "uyari", zoom=True),
        ],
    },
    {
        "key": "den-liste",
        "title": "Deneme listesi ve deneme detayı",
        "subtitle": "Soru soru tablo, çeldirici, karne",
        "action": None,
        "steps": [
            S("Tüm Denemeler sekmesinde her deneme bir satırdır: büyük yazılan net, deneme adı, türü, tarih ve doğru, yanlış, boş sayıları. Sağdaki simgeler denemenin işlemleridir: detay, ders kırılımı, yanlışları arşive al, satırları düzelt, öğrenciyle paylaş, veliye duyur, düzenle ve sil.", "d-liste", "islemler", zoom=True),
            S("Göz simgesine bastım; deneme detayı açıldı. Üstte toplam net ve önceki denemeye göre farkı, doğru yanlış boş dağılımı, karnede yazıyorsa puan ve sıralama var. Altında ders bazında sonuç tablosu durur.", "d-detay", "pencere", zoom=True),
            S("Test içinde ilerleyiş bölümü, soruların ilk yarısıyla ikinci yarısındaki başarıyı karşılaştırır. İkinci yarıda belirgin bir düşüş varsa sona doğru düşüş uyarısı çıkar; bu genellikle süre ya da dikkat sorununa işaret eder.", "d-ilerleyis", "bolum", zoom=True),
            S("Soru soru bölümünde her sorunun konusu, cevap anahtarı, öğrencinin cevabı ve sonucu yazar. Üstteki düğmelerle yalnız yanlışları ya da yalnız boşları süzersin.", "d-soru-soru", "bolum", zoom=True),
            S("Çeldirici analizi, öğrencinin hangi şıkları ne sıklıkla işaretlediğini cevap anahtarındaki payla karşılaştırır. Örneğin yanlışların çoğu aynı şıkta toplanıyorsa ya da aynı şık üst üste işaretlendiyse burada yazar. Aynı denemeye senin başka öğrencilerin de girdiyse, soru bazında en çok seçilen yanlış şık da görünür.", "d-celdirici", "bolum", zoom=True),
            S("Mor dosya simgesi Satırları düzelt demektir. Kayıtlı denemenin soru tablosunu yeniden açar; PDF yeniden okunmaz ve kredi düşmez. Bir konuyu ya da sonucu düzeltip kaydedersin, net ve analizler yeniden hesaplanır.", "d-duzelt", "pencere", zoom=True),
            S("Deneme detayındaki Yazdır düğmesi bu A4 karneyi açar: netler, ders tablosu, öne çıkanlar, son denemelerdeki gelişim, net fırsatı ve yanlış sorular tek sayfada. Yazdırabilir ya da PDF olarak kaydedip paylaşabilirsin.", "d-karne", "sayfa", zoom=True),
        ],
    },
    {
        "key": "den-genel",
        "title": "Genel Bakış ve Net Gelişimi",
        "subtitle": "Son deneme ve netin seyri",
        "action": None,
        "steps": [
            S("Analizlerden önce iki seçiciye dikkat et. Dönem seçici, öğrencinin hangi sınıfının denemelerine baktığını belirler; varsayılan olarak bu dönemdir. Geçen yılın denemelerini görmek için o dönemi ya da Tümü'nü seçersin. Öğrencinin birden çok sınav türü varsa ayrıca bir tür seçici çıkar; çünkü L G S, T Y T ve A Y T netleri farklı ölçektedir ve birbirine karıştırılmaz.", "d-donem", "secici", zoom=True),
            S("Analiz yedi sekmeye ayrılır. Genel Bakış'ta son deneme özetlenir: toplam net ve önceki denemeye göre farkı, doğru yanlış boş dağılımı, puan ve sıralama.", "d-genel", "son", zoom=True),
            S("Öne çıkanlar kutusu sayılardan kendiliğinden cümle kurar: net ne kadar arttı, en çok hangi ders yükseldi ya da düştü, boşlar arttı mı. Yapay zekâ kullanılmaz, sayı uydurulmaz.", "d-one-cikan", "kutu", zoom=True),
            S("Ders bazında sonuç tablosunda son sütun, her dersin bir önceki denemeye göre farkını gösterir. Genel ortalama gir düğmesiyle, karnede yazan kurum ortalamasını elle girebilirsin; o zaman tabloya ortalamaya göre farkı da eklenir.", "d-ders", "tablo", zoom=True),
            S("Net Gelişimi sekmesindeki grafik, aynı türdeki son denemelerin netini sırayla gösterir. Elif'in matematik netleri on virgül otuz üçten on dörde çıkmış.", "d-net-grafik", "grafik", zoom=True),
            S("Ders çarpı deneme tablosunda satırlar dersler, sütunlar denemelerdir. Son sütun, dersin ilk denemesinden son denemesine değişimidir. Bir dersin sürekli düştüğünü buradan hemen görürsün. Bir uyarı: yirmi soruluk bir branş denemesiyle doksan soruluk genel denemeyi aynı grafikte kıyaslamak yanıltır; branş netleri doğal olarak düşük görünür.", "d-net-tablo", "tablo", zoom=True),
        ],
    },
    {
        "key": "den-konu",
        "title": "Konu Analizi",
        "subtitle": "Net fırsatı, unutulan konular, ısı haritası",
        "action": None,
        "steps": [
            S("Konu Analizi, PDF'ten aktarılan denemelerin soru satırlarından hesaplanır. Her soru karnedeki konusuyla müfredat konusuna bağlandığı için, sonuçlar konu konu toplanır. Elle girilen denemeler bu analize girmez."),
            S("Net fırsatı listesi şu soruyu cevaplar: bu konudaki yanlış ve boşlar doğru olsaydı deneme başına kaç net kazanırdı? Yanlış bir soru doğruya dönünce hem bir doğru eklenir hem de yanlışın götürdüğü ceza geri gelir. En büyük fırsat en üsttedir. Elif için ilk sıra Üslü İfadeler. Programda önceliği bu konulara vermelisin.", "d-firsat", "liste", zoom=True),
            S("Konu değişimleri bölümü denemeleri tarih sırasıyla ikiye böler: ilk denemeler ve son denemeler. Unutulan konular, ilk denemelerde bilinen ama son denemelerde düşen konulardır; tekrar planlanmalı. Gelişen konular ise doğruluğu belirgin artan konulardır. Bir konunun işaretlenmesi için her yarıda en az iki soru gelmesi ve doğruluğun en az otuz dört puan değişmesi gerekir.", "d-degisim", "kartlar", zoom=True),
            S("Her kartta ilk ve son denemelerdeki doğruluk yazar; noktalar her denemenin sonucudur. Sağ üstteki etiket kanıtın gücünü söyler: soru sayısı azsa az veri, çoksa güçlü kanıt. Kanıtı gör düğmesi kararın dayandığı soruları açar.", "d-degisim", "kartlar"),
            S("İşte kanıt: Eşitsizlikler konusunda ilk iki denemede dört sorunun hepsi doğru, son iki denemede ise dört sorudan biri doğru. Her denemede hangi soru, öğrenci ne işaretledi, doğru cevap neydi, tek tek görürsün. Boş bırakılan soru doğru sayılmaz.", "d-kanit", "pencere", zoom=True),
            S("Unutulan bir konunun kartındaki Seansa ekle düğmesi, bu konuyu sıradaki koçluk seansının gündemine ekler. Yeni seans açtığında madde işaretli gelir; görüşmede atlamazsın.", "d-seansa", "dugme", click=True, zoom=True),
            S("Konu çarpı deneme ısı haritası her konunun her denemedeki sonucunu tek tabloda gösterir. Hücrede doğru bölü soru sayısı yazar. Koyu yeşil hepsi doğru, açık yeşil yarısından fazlası, turuncu kısmen, kırmızı hiç doğru yok demektir. Nokta, o denemede bu konudan soru gelmediğini söyler. Soldan sağa kızaran bir satır, unutulan bir konudur.", "d-isi", "tablo", zoom=True),
        ],
    },
    {
        "key": "den-davranis",
        "title": "Sınav Davranışı ve Puan Tahmini",
        "subtitle": "Boş mu bırakıyor, sallıyor mu; yaklaşık puan",
        "action": None,
        "steps": [
            S("Sınav Davranışı sekmesi, öğrencinin emin olmadığı sorularda ne yaptığını gösterir. Kaçan sorular içinde yanlışların payı düşükse temkinli, yani boş bırakıyor; yüksekse riskli, yani emin olmadığını da işaretliyor; arada ise dengeli. Elif dengeli. Ders tablosunda her dersin boş oranı ve deneme başına kaçan net yazar. Altta denemeden denemeye boş ve yanlış sayıları var.", "d-davranis", "egilim", zoom=True),
            S("Puan Tahmini sekmesi, son denemenin netlerinden yaklaşık bir puan hesaplar ve karnede puan yazıyorsa onunla karşılaştırır. Bu ham bir tahmindir, yön göstermek içindir. Dikkat: tahmin tüm derslerin olduğu genel bir denemeden anlamlıdır. Elif'in son denemesi yalnız matematik olduğu için buradaki puan düşük çıkıyor; genel denemelerle doğru sonuç verir.", "d-puan", "kart", zoom=True),
        ],
    },
    {
        "key": "den-rapor",
        "title": "Gelişim Raporu ve hedef net",
        "subtitle": "Hedef koy, otomatik yorumu oku, aksiyon al",
        "action": None,
        "steps": [
            S("Gelişim Raporu sekmesinde önce hedef net koyarsın. Hedef belirle düğmesine bastım. Toplam hedef neti, istersen hedef tarihi ve öğrencinin de göreceği bir not yazdım. Ders ders hedef de verebilirsin.", "d-hedef-pencere", "pencere", zoom=True),
            S("Hedef kutusu artık şunu söylüyor: hedef on altı net, şu an son üç denemenin ortalaması on iki virgül altmış yedi, kalan üç virgül otuz üç net. Hedef tarihine kadar haftada ne kadar artış gerektiği ve bu tempoyla kaç deneme sonra hedefe ulaşılacağı da yazar.", "d-hedef", "kutu", zoom=True),
            S("Gelişim özeti dört sayıdır: ilk ve son net, son üç denemenin ortalaması, en iyi net ve eğim. Eğim, son denemelerde deneme başına ortalama net değişimidir; pozitifse öğrenci yükseliyor demektir.", "d-ozet", "kutu", zoom=True),
            S("Otomatik yorum, bu sayılardan sade cümleler kurar. Yeşil satırlar iyi giden şeyleri, turuncu satırlar dikkat gerekenleri söyler. Yapay zekâ kullanılmaz; her cümle bir sayıya dayanır.", "d-yorum", "kutu", zoom=True),
            S("Aksiyon planı, net fırsatlarından, unutulan konulardan, ders düşüşlerinden ve hedef farkından yapılacaklar listesi çıkarır. Her madde öncelikli, önemli ya da takip olarak işaretlenir. Seçtiklerini Seansa ekle ile sıradaki seansın gündemine aktarırsın.", "d-aksiyon", "kutu", zoom=True),
            S("Raporu yazdır düğmesi bu A4 gelişim raporunu açar: net gidişatı grafiği, ders gidişatı, değerlendirme ve aksiyon planı. Veli görüşmesine çıktı alıp götürebilir, ya da Raporu paylaş ile WhatsApp'tan gönderebilirsin.", "d-rapor-a4", "sayfa", zoom=True),
        ],
    },
    {
        "key": "den-paylas",
        "title": "Öğrenciyle paylaş ve veliye duyur",
        "subtitle": "Sonucu doğru dille ilet",
        "action": None,
        "steps": [
            S("Öğrenci denemesini zaten kendi panelinde görür. Öğrenciyle paylaş düğmesi ise ona özel bir değerlendirme notu göndermek içindir. Notu yazarsın, istersen uygulamasına bildirim de gider. Koça özel notların hiçbir zaman paylaşılmaz.", "d-ogrenci", "pencere", zoom=True),
            S("Zarf simgesi Veliye duyur demektir. Hiçbir şey gönderilmeden önce velinin göreceği e-posta önizlenir: net, önceki denemeye göre değişim, hedef ve tahmini puan kutuları.", "d-veli", "pencere", zoom=True),
            S("Bu deneme ne anlatıyor bölümündeki cümleleri sistem sayılardan kurar. Her cümleyi düzenleyebilir, istemediğini çöp kutusuyla silebilir, kendi cümleni ekleyebilirsin. Net ve doğru yanlış sayıları ise buradan değiştirilemez; onlar ölçümdür.", "d-veli-yorum", "yorum", zoom=True),
            S("Altta hangi tabloların maile gireceğini seçersin: ders bazında tablo, önceki denemelerle karşılaştırma ve nerede net kazanabilir tablosu. Son tablo, Konu Analizi'ndeki net fırsatıyla aynı kaynaktan gelir.", "d-veli-tablolar", "secim", zoom=True),
            S("Velilere gönder dersen mail gider ve denemenin yanında Duyuruldu etiketi çıkar; aynı deneme ikinci kez duyurulmaz. PDF olarak indir ile aynı içeriği PDF yapıp WhatsApp'tan da paylaşabilirsin. Hepsi bu kadar. Kitaplar, program ve denemelerle ilgili her şeyi gördün; şimdi sıra sende.", "d-veli-alt", "pdf", zoom=True),
        ],
    },
]
