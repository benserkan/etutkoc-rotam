"""Rota Rehberi — HAVUZ serisi (koç, "Haftalık havuz" yolu). İçerik kaynağı.

`python -m scripts.guide_content.build` bu modülü okur ve coach-guide-content.json
içindeki "Havuz" konusunu yeniden yazar. Bölümlerin hepsi `branch: "havuz"` —
Program girişindeki (prog-mod) yol seçiminde "Haftalık havuz" seçen koç bu yolla
devam eder. Metinler yalnız GERÇEK ekranlarda görünen etiketleri kullanır
(envanter: 2026-10-16). Ekranlar: scripts/capture_guide_havuz.py
(demo veri: scripts/seed_guide_demo_havuz.py — Deniz Arslan, Ece Yıldız).

Adım: (metin, ekran, vurgu kutusu, tıklama animasyonu, yakınlaştırma, konuşma metni)
"""

MODULE = "Havuz"
BRANCH = "havuz"


def S(caption, shot=None, target=None, click=False, zoom=False, speech=None):
    d = {"caption": caption, "shot": shot, "target": target, "click": click, "zoom": zoom}
    if speech:
        d["speech"] = speech
    return d


CHAPTERS = [
    {
        "key": "havuz-giris",
        "branch": BRANCH,
        "title": "Havuz nedir, ilk dönem nasıl açılır?",
        "subtitle": "Dönem, havuz, kap — ve dönem kartı",
        "action": {
            "label": "Bir öğrencini havuz moduna al, ilk dönemini aç",
            "href": "/teacher/students",
            "checkKey": "program-kur",
            "doneLabel": "Havuzun hazır",
            "hint": "Yol: sol menü → Öğrenciler → öğrencinin sayfasında İşlemler → Haftalık havuz modu.",
            "optional": True,
        },
        "steps": [
            S("Haftalık havuz yolundasın. Üç kavramı bilmen yeter. Dönem: iki seans arasındaki süre, genelde bir hafta. Havuz: o dönemde yapılacak işlerin listesi. Kap: öğrencinin her gün havuzdan aldığı, o günün görevleri."),
            S("Bir öğrenci havuz moduna geçince sayfasında Haftalık Havuz düğmesi çıkar. Geçişi İşlemler menüsünden yaparsın; pencere hangi görevin silinip hangisinin kalacağını önceden gösterir.", "hv-mod-pencere", "pencere", zoom=True),
            S("Ece'nin dönemi dünkü seansta kapandı ve yeni dönem henüz açılmadı. Üstte seans günü ve beklenen sonraki seans var. Beklenen gün çakılı değildir; öğrenci gelmezse dönem uzar, tempo yeni güne göre hesaplanır.", "hv-donem-ac", "ac", zoom=True),
            S("Son dönemden kalan kalemler Devredilecek kalemler listesinde. Yeni haftaya taşıyacaklarını tek tek işaretlersin, gerekirse miktarı yeniden yazarsın. Toplu düğme bilinçli olarak yok; her kalem için karar sensin. Üçüncü kez devredilen kalem kaçınılan diye işaretlenir.", "hv-donem-ac", "devir", zoom=True),
            S("Dönem açıldığında havuz sayfasının en üstünde dönem kartı durur. Deniz'in dönemi beşinci gününde. Altındaki şerit dönemi gün gün gösterir: geçen günler, bugün, kalan günler ve seans günü.", "hv-donem-kart", "takvim", zoom=True),
            S("Dört ölçü dönemin özeti. Tamamlanan: havuzun yüzde kırk yedisi yapıldı; çubuktaki çizgi bu güne kadar beklenen yeri gösterir. Biten kalem, seansa kalan gün ve günde gereken birim. Her ölçünün altında ne anlama geldiği yazar.", "hv-donem-kart", "olcu", zoom=True),
            S("Sağ üstteki İzle ve Düzenle anahtarı sayfayı ikiye ayırır. İzle, seansa kadar öğrencinin ne yaptığını görmek içindir. Düzenle, havuza kalem eklemek ve havuzu yönetmek içindir. Önce havuzu yazmayı görelim.", "hv-donem-kart", "gorunum", zoom=True),
        ],
    },
    {
        "key": "havuz-kalem",
        "branch": BRANCH,
        "title": "Havuza kalem eklemek",
        "subtitle": "Ders, nereden, miktar — ya da tek satırda yaz",
        "action": None,
        "steps": [
            S("Düzenle görünümüne geçtim. Solda Havuza kalem ekle paneli, sağda havuzun kendisi var. Havuz yazıldığı anda öğrenciye açılır; ayrıca yayınlaman gerekmez.", "hv-duzenle", "ekle", zoom=True),
            S("Birinci adım ders. Dersler okul, T Y T ve A Y T başlıklarıyla gruplanır. Öğrencinin kitabı olan dersler rozetle işaretlidir; havuzda kalemi olan derslerde kaç kalem olduğu yazar. T Y T Matematik'e tıklıyorum.", "hv-kalem-ders", "mat", zoom=True, click=True),
            S("İkinci adım: nereden? İki yol var. Öğrencinin kitabından: kitabın kendi bölümleri listelenir, her bölümde kaç test kaldığı yazar. Son kalem verilen bölüm SON diye işaretlenir. Kitaptan verilen kalemde öğrenci işaretledikçe kitap sayacı da ilerler.", "hv-kalem-kitap", "kitap", zoom=True),
            S("Çarpanlara Ayırma bölümünü seçtim. Üçüncü adımda miktarı seçersin; birim kitaptan gelir. Kalanı ver düğmesi bölümde kalan bütün testleri tek seferde yazar. Havuza ekle'ye basınca kalem listeye düşer.", "hv-kalem-miktar-kitap", "ekle", zoom=True),
            S("İkinci yol: Müfredat konusundan, yani kaynaksız. Öğrencinin elinde olmayan bir kaynaktan ya da okul ödevinden çalışacaksa resmi konuyu seçer, sayıyı sen yazarsın. Konular sınıfa göre gruplanır; kendi sınıfı önde gelir. Arama kutusu bütün sınıflarda arar.", "hv-kalem-konu", "konular", zoom=True),
            S("Bir konu seçtim. Birim olarak test, soru, sayfa, deneme ya da etkinlik seçebilirsin. Test ve soru kalemi mutlaka bir konuya bağlanır; böylece konu performansına ve müfredat haritasına işler. Ek seçeneklerde gün etiketi ve ders öğretmeni ödevi işareti var.", "hv-kalem-miktar", "birim", zoom=True),
            S("Kalem eklendi. Havuz listesi derslere göre gruplu ve her ders kendi renginde. Üstteki çubuk birimlerin derslere nasıl dağıldığını gösterir. Her kalemde kaç birimin yapıldığı, kitaptan geliyorsa kitapta kaç testin çözüldüğü yazar.", "hv-kalem-liste", "liste", zoom=True),
            S("Rozetlere dikkat et: Devir iki, bu kalemin iki dönemdir taşındığını söyler. Kaç kez kaba girdi, öğrencinin onu kaç kez seçip geri bıraktığını gösterir. Eğik yazılı kalem ders öğretmeninin ödevidir.", "hv-kalem-liste", "liste", zoom=True),
            S("Listenin altında Bu havuzda kalemi olmayan dersler var. Zorunlu değil, bir kontrol listesi. Bir derse tıklarsan ekleme paneli doğrudan o derse geçer.", "hv-kalem-eksik", "eksik", zoom=True),
            S("Daha hızlı bir yol var: Hızlı yaz. Doğal yazarsın, ayraç gerekmez. Fizik hareket üç test yazıp Ayrıştır'a bastım. Sistem dersi, konuyu, sayıyı ve birimi buldu; sonucu önce sana gösterir, onaylamadan hiçbir şey yazılmaz.", "hv-hizli", "okunan", zoom=True),
            S("Bu kez yalnız paragraf dört test yazdım. Ders T Y T Türkçe olarak bulundu, konu için bir tahmin geldi: Paragraf Karma. Tahmin sarı renkle işaretlenir; doğru değilse değiştirirsin, doğruysa Böyle ekle'ye basarsın. Birden çok konuya uyan sözcüklerde seçenekler listelenir.", "hv-hizli-secenek", "okunan", zoom=True),
            S("En altta Gün gün nasıl görünür önizlemesi var. Havuzun kalan birimlerini şubenin ders programına göre günlere dağıtır: bir dersin kalemi önce o dersin dershanede işlendiği güne yerleşir. Bu yalnız bir öneridir; günleri öğrenci kendisi seçer.", "hv-onizleme", "onizleme", zoom=True),
        ],
    },
    {
        "key": "havuz-sube",
        "branch": BRANCH,
        "title": "Şube ve dershane ders programı",
        "subtitle": "Hangi gün hangi ders işleniyor",
        "action": None,
        "steps": [
            S("Havuz öğrencin bir şubede ise, örneğin On İki A, şubenin dershane ders programını bir kez girersin. Tabloda her satır bir ders, her sütun bir gün. Hücreye dokununca o gün o ders işleniyor demektir.", "hv-sube", "tablo", zoom=True),
            S("Bu tablo iki yerde işe yarar. Birincisi önizleme: kalemler dersin işlendiği güne yerleşir. İkincisi öğrencinin sabah hatırlatması: bugün dershanede Biyoloji vardı ve havuzunda Biyoloji kalemin var diye konuşur. Program şubeye bağlıdır; aynı şubedeki bütün öğrencilerde geçerlidir.", "hv-sube", "sube", zoom=True),
        ],
    },
    {
        "key": "havuz-ogrenci",
        "branch": BRANCH,
        "title": "Öğrenci tarafı: günün kabı",
        "subtitle": "Kaba al, işaretle, gece havuza döner",
        "action": None,
        "steps": [
            S("Şimdi öğrencinin ne gördüğüne bakalım. Deniz Bugün sayfasını açtığında en üstte haftanın havuzu kartı var: yüzde kaç bittiği, seansa kaç gün kaldığı, bugün kabında kaç kalem olduğu. Havuzu aç düğmesi Havuzum sayfasına götürür.", "hv-ogr-bugun", "kart", zoom=True),
            S("Havuzum sayfasında haftanın özeti ve tempo cümlesi var. Dil yargılamaz: tempo biraz geride, bugün bir fazla yapmak haftayı rahatlatır der. Bugün dershanede işlenen dersler de burada yazar.", "hv-ogr-havuzum", "ozet", zoom=True),
            S("Aşağıda havuzdaki kalemler derslere göre listelenir. Her kalemin yanında Kaba al düğmesi var. Kaba almak, o kalemi bugünün görevi yapmak demektir.", "hv-ogr-liste", "liste", zoom=True),
            S("Kaba al'a basınca Bugün kaç tane diye sorar. Seçilebilecek sayılar kalemde kalan kadardır. Öğrenci çok büyük bir sayı seçerse sistem gerçekten çözecek misin diye nazikçe sorar; engel değildir.", "hv-ogr-kaba-al", "pencere", zoom=True),
            S("Kalem artık Bugünün kabında. Kapta her görevin dersi, kaç birim olduğu ve ilerleme çubuğu görünür. Hiç dokunulmamış görevi geri ok ile havuza geri alabilir.", "hv-ogr-kap", "kap", zoom=True),
            S("İşaretleme Bugün sayfasında yapılır, gün gün programdaki gibi: testleri işaretler, doğru, yanlış ve boş sayısını girer. Bugün yapılmayan kısım gece kendiliğinden havuza döner; kısmen yapılanın yapılan kısmı kalır.", "hv-ogr-gorev", "gorev", zoom=True),
            S("Öğrenci havuza kendisi de kalem ekleyebilir, örneğin kendi bulduğu bir paragraf denemesi ya da öğretmeninin verdiği bir ödev. Senin onayın gelene kadar bu kalem yüzdeye girmez.", "hv-ogr-kalem-ekle", "pencere", zoom=True),
            S("Haftaya nasıl dağılır kartı, senin önizlemenle aynı kuralla öğrencinin işini günlere böler. Bu da bir öneridir. Öğrenci sabah kabı boşsa ve akşam işaretlemediği kalem varsa hatırlatma alır."),
        ],
    },
    {
        "key": "havuz-izle",
        "branch": BRANCH,
        "title": "Seansa kadar izlemek",
        "subtitle": "Gün gün, derslere göre, uyarılar",
        "action": None,
        "steps": [
            S("İzle görünümüne dönelim. Dönem kartının altında uyarı kartı durur. Deniz için tempo geride diyor: kalan yirmi dokuz birim için günde dokuz virgül yedi birim gerekiyor, son üç dönemde günde ortalama üç birim yaptı.", "hv-izle-uyari", "uyari", zoom=True),
            S("Neden düğmesi kanıtı açar: kalan birim, gereken tempo, öğrencinin alışkanlığı ve kural. Uyarı, gereken tempo alışkanlığın bir buçuk katını aşınca çıkar; ilk iki dönem susar. Öğrenciye kırmızı uyarı gitmez, yalnız yargılamayan bir ipucu gider.", "hv-izle-uyari", "kanit", zoom=True),
            S("Gün gün şeridi öğrencinin her gün ne yaptığını gösterir. Her gün renkli dilimlere ayrılır; her renk bir derstir. Altında o gün yapılan birim yazar. Gelecek günler soluk, seans günü kesikli çerçevelidir.", "hv-izle-gunler", "gunler", zoom=True),
            S("Bir güne dokununca o günün görevleri açılır: hangi kalemden kaç birim yapıldığı, doğru, yanlış ve boş sayıları. Seansa girmeden önce haftanın nasıl geçtiğini burada okursun.", "hv-izle-gun-detay", "detay", zoom=True),
            S("Derslere göre ilerleme kartları her dersin yüzdesini gösterir. Koyu renk öğrencinin kendi kaydı, açık renk seansta senin işaretlediğin kısımdır. Kaçınılan kalemi olan ders ayrıca işaretlenir.", "hv-izle-dersler", "dersler", zoom=True),
            S("Onayını bekleyen öğrenci kalemleri burada listelenir. Öğrenci kaynağını seansta gösterince Onayla'ya basarsın; o andan sonra yüzdeye girer.", "hv-izle-onay", "onay", zoom=True),
            S("Bütün havuz öğrencilerini tek yerde görmek için Görüşmeler sayfasının üstündeki Bugünkü görüşme listesine bak. Seansı bugün olanlar en üsttedir; her öğrencide tek bir ana sinyal, gerisi ek altında. Gördüm, sinyali üç gün gizler; durum sürerse geri gelir.", "hv-gorusme-listesi", "liste", zoom=True),
        ],
    },
    {
        "key": "havuz-seans",
        "branch": BRANCH,
        "title": "Seans ekranı ve Seansı bitir",
        "subtitle": "Kalem kalem bak, işaretle, yeni dönemi aç",
        "action": None,
        "steps": [
            S("Seans günü dönem kartındaki Seans ekranı düğmesine basarsın. Bu ekran tek sayfadır, sekme yok. En üstte tek cümlelik özet: havuzun yüzde kırk yedisi, kaçınma ve onay bekleyen kalem.", "hv-seans-ust", "ozet", zoom=True),
            S("Kalem kalem bölümünde her kalemde öğrencinin kendi kaydı, senin seansta işaretlediğin ve kalan görünür. Öğrenci kâğıt üzerinde çözmüş ama sisteme girmemişse kaynağına bakar, seansta kutusuna sayıyı yazarsın. Kitaptan gelen kalemde bu sayı kitap sayacına da yazılır.", "hv-seans-kalem", "kalemler", zoom=True),
            S("Kitaba bak bağlantısı öğrencinin kitap sayfasını açar. Konuyu kapat düğmesiyle öğrencinin bitirdiği konuyu müfredatta tamamlanmış sayarsın. Etkinlik kaleminde sayı yerine yapıldı düğmesi var.", "hv-seans-kalem", "kalemler", zoom=True),
            S("Sağda kaçınılan kalemler listelenir: üç kez kaba girip geri dönen, üçüncü kez devredilen ya da günlerdir hiç kaba alınmayan kalem. Seansta konuş: zor mu geldi, kaynak mı yok, zaman mı kalmadı? Denemesi varsa son denemenin şeridi de burada görünür.", "hv-seans-kacinilan", "kacinilan", zoom=True),
            S("Görüşme bitince Seansı bitir'e basarsın. Tek işlemde dönem kapanır, seans kaydı yazılır ve bugün yeni dönem açılır.", "hv-seans-ust", "bitir", zoom=True, click=True),
            S("Pencerede kalanı olan kalemler listelenir. Devredeceklerini tek tek işaretler, miktarı değiştirirsin. Beklenen sonraki seansı seçersin. Seans kaydı yaz kutusu açıksa gündem ve notun Seanslar sekmesine ve tahsilata geçer.", "hv-seans-bitir", "pencere", zoom=True),
            S("Yeni dönemde devredilen kalem Devir rozetiyle görünür ve kaç kez devredildiği sayılır. Üçüncü devir kaçınma sinyali üretir; o kalemi seansta ayrıca konuşmak gerekir."),
        ],
    },
    {
        "key": "havuz-donem",
        "branch": BRANCH,
        "title": "Ara, dönem geçmişi ve gün güne dönüş",
        "subtitle": "Seanssız kapatma, veli özeti, geçmiş, mod geçişi",
        "action": None,
        "steps": [
            S("Bazen seans yapılmaz: öğrenci tatildedir ya da görüşme olmamıştır. Bunun için dönem kartında Seanssız kapat var. Pencerede iki seçenek çıkar: görüşmesiz kapat ya da ara, yani tatil. Seans yapılmadığını onaylaman gerekir; görüşmesiz kapatmada kısa bir gerekçe de yazarsın.", "hv-seanssiz", "pencere", zoom=True),
            S("Kapanan her dönem Dönem geçmişi'nde bir kart olur: tarih aralığı, yüzde, ders ders ilerleme, devir girişi ve çıkışı. Geçmiş sınırsız saklanır. Dönem kapanınca veli özeti hazırlanır; kendiliğinden gitmez.", "hv-gecmis", "gecmis", zoom=True),
            S("Veli özetini önizle'ye basınca özet açılır. Cümleleri tek tek düzenler ya da silersin, sonra gönderirsin. Senin notun ve öğrencinin onaylanmamış kalemleri özete girmez.", "hv-veli-ozet", "satirlar", zoom=True),
            S("Bir dönem kartındaki Aç düğmesi o dönemi ayrıntısıyla gösterir. Havuz kalemleri sekmesinde ne verildiğini, ne bittiğini ve neyin devredildiğini görürsün.", "hv-donem-pencere", "pencere", zoom=True),
            S("Gün gün sekmesi o dönemde öğrencinin her gün ne çalıştığını, kaç test çözdüğünü, doğru, yanlış ve boş sayılarını gösterir. Gün gün programdaki geçmiş haftaların karşılığı budur.", "hv-donem-pencere-gun", "pencere", zoom=True),
            S("Öğrenciyi gün gün programa geri almak istersen bunu seansın sonunda yaparsın. Seansı bitir penceresinde Bu seansla gün gün programa geç kutusunu işaretle. Kutu, geçişte ne olacağını açıkça yazar: çözülenler müfredatta kalır, kalan kalemler devredilmez, dokunulmamış görevler silinir.", "hv-seans-gungune", "gecis", zoom=True),
            S("Hepsi bu kadar. Havuzla ilgili her şeyi gördün: dönemi açmak, havuzu yazmak, öğrencinin kabı, izlemek ve seans. Sıradaki konu denemeler."),
        ],
    },
]
