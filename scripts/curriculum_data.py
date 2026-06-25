"""Müfredat seed verisi — LGS + Klasik Lise + Maarif Modeli paralel.

Sistem 5-12. sınıf + mezun YKS hazırlığını destekler. Üç müfredat modeli
şu an paralel yaşıyor:

- **LGS** (5-8. sınıf): Mevcut MEB ortaokul müfredatı, LGS sınavına yönelik.
- **KLASIK_LISE** (11-12): Maarif öncesi son nesil (2026-27 son 12, sonra biter).
- **MAARIF_LISE** (9-12): Türkiye Yüzyılı Maarif Modeli — 2024-25'ten beri
  9 ve 10. sınıflarda; 11 Eylül 2026'da, 12 Eylül 2027'de devreye girecek.

Yapı:
    SUBJECT_NAME → {
        "min_grade": int, "max_grade": int,
        "exam_section": str (LGS/TYT/AYT_SAY/AYT_EA/AYT_SOZ/AYT_DIL),
        "curriculum_model": str (LGS/KLASIK_LISE/MAARIF_LISE),
        "available_for_graduate": bool,
        "topics": [(name, grade_level), ...]
    }

Sayılar:
- Mevcut DB: 6 LGS dersi + 53 LGS topic (zaten seed edilmiş, bu dosya idempotent)
- Hedef: yukarıdakiler + 15 Maarif Lise dersi × (9-10) + 11+ klasik dersler

Geriye uyumluluk: `CURRICULUM` ve `SUBJECT_ORDER` mevcut sistemin LGS verisini
sağlıyor (eski seed.py uyumu için); yeni seed yapısı `ALL_CURRICULA` üzerinden.
"""

from __future__ import annotations


# =============================================================================
# LGS — 5-8. sınıf (mevcut sistem, LGS sınavına yönelik)
# =============================================================================
# 8. sınıf konuları (mevcut DB'de seed edilmiş, koru). 5-7 daha sonra eklenecek.

LGS_CURRICULUM: dict[str, dict] = {
    "Türkçe": {
        "min_grade": 5, "max_grade": 8,
        "exam_section": "LGS",
        "curriculum_model": "LGS",
        "available_for_graduate": False,
        # 8. sınıf (LGS) DÜZ konu — yayınevi kitaplarıyla birebir.
        "topics": [
            ("Sözcükte Anlam", 8),
            ("Cümlede Anlam", 8),
            ("Paragrafta Anlam", 8),
            ("Metin Türleri", 8),
            ("Sözel Mantık", 8),
            ("Fiilimsiler", 8),
            ("Cümlenin Ögeleri", 8),
            ("Fiilde Çatı", 8),
            ("Cümle Türleri", 8),
            ("Anlatım Bozuklukları", 8),
            ("Yazım Kuralları", 8),
            ("Noktalama İşaretleri", 8),
        ],
        # 5-7: anlam + dil bilgisi + yazım (yayınevi test kitabı düzeni). Dil bilgisi
        # konuları MEB sıralaması: 5 isim/sıfat · 6 zamir/edat · 7 fiil/zarf/ek fiil.
        "unit_term": "Öğrenme Alanı",
        "units": [
            (1, "Anlam Bilgisi", 5, [
                "Sözcükte Anlam", "Söz Varlığı (Deyim ve Atasözleri)",
                "Cümlede Anlam", "Paragrafta Anlam"]),
            (2, "Dil Bilgisi", 5, ["İsimler (Adlar)", "Sıfatlar (Ön Adlar)"]),
            (3, "Yazım ve Noktalama", 5, ["Yazım Kuralları", "Noktalama İşaretleri"]),
            (1, "Anlam Bilgisi", 6, [
                "Sözcükte Anlam", "Cümlede Anlam", "Paragrafta Anlam"]),
            (2, "Dil Bilgisi", 6, ["Zamirler (Adıllar)", "Edat, Bağlaç ve Ünlem"]),
            (3, "Yazım ve Noktalama", 6, ["Yazım Kuralları", "Noktalama İşaretleri"]),
            (1, "Anlam Bilgisi", 7, [
                "Sözcükte Anlam", "Cümlede Anlam", "Paragrafta Anlam"]),
            (2, "Dil Bilgisi", 7, [
                "Fiiller (Anlam, Kip, Kişi)", "Ek Fiil", "Zarflar (Belirteçler)"]),
            (3, "Yazım ve Noktalama", 7, ["Yazım Kuralları", "Noktalama İşaretleri"]),
        ],
    },
    "Matematik": {
        "min_grade": 5, "max_grade": 8,
        "exam_section": "LGS",
        "curriculum_model": "LGS",
        "available_for_graduate": False,
        # 8. sınıf (LGS sınavı) DÜZ konu — yayınevi kitaplarıyla birebir (%100 eşleşir).
        "topics": [
            ("Çarpanlar ve Katlar", 8),
            ("Üslü İfadeler", 8),
            ("Kareköklü İfadeler", 8),
            ("Veri Analizi", 8),
            ("Basit Olayların Olasılığı", 8),
            ("Cebirsel İfadeler ve Özdeşlikler", 8),
            ("Doğrusal Denklemler", 8),
            ("Eşitsizlikler", 8),
            ("Üçgenler", 8),
            ("Eşlik ve Benzerlik", 8),
            ("Dönüşüm Geometrisi", 8),
            ("Geometrik Cisimler", 8),
        ],
        # 5-7. sınıf: öğrenme alanı (PARENT) + geleneksel konu (LEAF). Yayınevi
        # test kitapları bu konu adlarıyla düzenlenir → eşleşir. (MEB öğrenme alanları)
        "unit_term": "Öğrenme Alanı",
        "units": [
            (1, "Sayılar ve İşlemler", 5, [
                "Doğal Sayılar", "Doğal Sayılarla İşlemler", "Kesirler",
                "Kesirlerle İşlemler", "Ondalık Gösterim", "Yüzdeler"]),
            (2, "Geometri ve Ölçme", 5, [
                "Temel Geometrik Kavramlar ve Çizimler", "Üçgen ve Dörtgenler",
                "Uzunluk ve Zaman Ölçme", "Alan Ölçme", "Geometrik Cisimler"]),
            (3, "Veri İşleme", 5, ["Veri Toplama ve Değerlendirme"]),
            (1, "Sayılar ve İşlemler", 6, [
                "Doğal Sayılarla İşlemler", "Çarpanlar ve Katlar", "Kümeler",
                "Tam Sayılar", "Kesirlerle İşlemler", "Ondalık Gösterimlerle İşlemler",
                "Oran"]),
            (2, "Cebir", 6, ["Cebirsel İfadeler"]),
            (3, "Geometri ve Ölçme", 6, [
                "Açılar", "Alan Ölçme", "Çember", "Geometrik Cisimler (Yüzey Alanı ve Hacim)"]),
            (4, "Veri İşleme", 6, ["Veri Toplama ve Değerlendirme", "Veri Analizi"]),
            (1, "Sayılar ve İşlemler", 7, [
                "Tam Sayılarla İşlemler", "Rasyonel Sayılar",
                "Rasyonel Sayılarla İşlemler", "Oran ve Orantı", "Yüzde Problemleri"]),
            (2, "Cebir", 7, ["Cebirsel İfadeler", "Eşitlik ve Denklem"]),
            (3, "Geometri ve Ölçme", 7, [
                "Doğrular ve Açılar", "Çokgenler", "Çember ve Daire",
                "Dönüşüm Geometrisi", "Cisimlerin Farklı Yönlerden Görünümleri"]),
            (4, "Veri İşleme", 7, ["Veri Analizi"]),
        ],
    },
    "Fen Bilimleri": {
        "min_grade": 5, "max_grade": 8,
        "exam_section": "LGS",
        "curriculum_model": "LGS",
        "available_for_graduate": False,
        # 8. sınıf (LGS) DÜZ ünite — yayınevi kitaplarıyla birebir.
        "topics": [
            ("Mevsimler ve İklim", 8),
            ("DNA ve Genetik Kod", 8),
            ("Basınç", 8),
            ("Madde ve Endüstri", 8),
            ("Basit Makineler", 8),
            ("Enerji Dönüşümleri ve Çevre Bilimi", 8),
            ("Elektrik Yükleri ve Elektrik Enerjisi", 8),
        ],
        # 5-7: öğrenme alanı (PARENT) + ünite (LEAF). Yayınevi kitapları ünite adıyla
        # düzenlenir → leaf = ünite. (MEB Fen öğrenme alanları)
        "unit_term": "Öğrenme Alanı",
        "units": [
            (1, "Dünya ve Evren", 5, ["Güneş, Dünya ve Ay"]),
            (2, "Canlılar ve Yaşam", 5, ["Canlılar Dünyası", "İnsan ve Çevre"]),
            (3, "Madde ve Doğası", 5, ["Maddenin Değişimi"]),
            (4, "Fiziksel Olaylar", 5, [
                "Kuvvetin Ölçülmesi ve Sürtünme", "Işığın Yayılması",
                "Basit Elektrik Devreleri"]),
            (1, "Dünya ve Evren", 6, ["Güneş Sistemi ve Tutulmalar"]),
            (2, "Canlılar ve Yaşam", 6, ["Vücudumuzdaki Sistemler"]),
            (3, "Fiziksel Olaylar", 6, [
                "Kuvvet ve Hareket", "Ses ve Özellikleri", "Elektriğin İletimi"]),
            (4, "Madde ve Doğası", 6, ["Madde ve Isı"]),
            (1, "Dünya ve Evren", 7, ["Güneş Sistemi ve Ötesi"]),
            (2, "Canlılar ve Yaşam", 7, [
                "Hücre ve Bölünmeler", "Canlılarda Üreme, Büyüme ve Gelişme"]),
            (3, "Fiziksel Olaylar", 7, [
                "Kuvvet ve Enerji", "Işığın Madde ile Etkileşimi", "Elektrik Devreleri"]),
            (4, "Madde ve Doğası", 7, ["Saf Madde ve Karışımlar"]),
        ],
    },
    "Sosyal Bilgiler": {
        "min_grade": 4, "max_grade": 7,
        "exam_section": "LGS",
        "curriculum_model": "LGS",
        "available_for_graduate": False,
        # Not: 8. sınıfta "T.C. İnkılap Tarihi ve Atatürkçülük" ayrı ders olur,
        # 4-7'de Sosyal Bilgiler tek ders. min_grade=4 koçluk-zincirinin
        # genişlemesi için (5-7 ana kapsam).
        "topics": [
            # 5. sınıf — Maarif Modeli öğrenme alanları
            ("Birlikte Yaşamak", 5),
            ("Evimiz Dünya", 5),
            ("Ortak Mirasımız", 5),
            ("Yaşayan Demokrasimiz", 5),
            ("Hayatımızdaki Ekonomi", 5),
            ("Teknoloji ve Sosyal Bilimler", 5),
            # 6. sınıf — öğrenme alanları
            ("Birlikte Yaşamak — Gruplar, Roller, Kültürel Bağlar", 6),
            ("Evimiz Dünya — Konum ve Türk Dünyası", 6),
            ("Ortak Mirasımız — Türkistan'daki İlk Türk Devletleri", 6),
            ("İslam Medeniyeti ve Anadolu'nun Türkleşmesi", 6),
            ("Yaşayan Demokrasimiz — Yönetim ve Vatandaşlık", 6),
            ("Hayatımızdaki Ekonomi — Kaynaklar ve Meslekler", 6),
            ("Teknoloji ve Sosyal Bilimler", 6),
            # 7. sınıf
            ("Birlikte Yaşamak — Etkili İletişim ve Fırsat Eşitliği", 7),
            ("Evimiz Dünya — Küreselleşme", 7),
            ("Osmanlı Cihan Devleti ve Yenilikleri", 7),
            ("Osmanlı Kültür ve Medeniyeti", 7),
            ("Cumhuriyet, Demokrasi ve Yönetim", 7),
            ("Hayatımızdaki Ekonomi — Millî Kalkınma", 7),
            ("Teknoloji, Bilim ve Toplum", 7),
        ],
    },
    "T.C. İnkılap Tarihi ve Atatürkçülük": {
        "min_grade": 8, "max_grade": 8,
        "exam_section": "LGS",
        "curriculum_model": "LGS",
        "available_for_graduate": False,
        "topics": [
            ("Bir Kahraman Doğuyor", 8),
            ("Millî Uyanış: Bağımsızlık Yolunda Atılan Adımlar", 8),
            ("Millî Bir Destan: Ya İstiklal Ya Ölüm!", 8),
            ("Atatürkçülük ve Çağdaşlaşan Türkiye", 8),
            ("Demokratikleşme Çabaları", 8),
            ("Atatürk Dönemi Türk Dış Politikası", 8),
            ("Atatürk'ün Ölümü ve Sonrası", 8),
        ],
    },
    "Din Kültürü ve Ahlak Bilgisi": {
        "min_grade": 5, "max_grade": 8,
        "exam_section": "LGS",
        "curriculum_model": "LGS",
        "available_for_graduate": False,
        "topics": [
            # 5. sınıf
            ("Allah İnancı", 5),
            ("Namaz", 5),
            ("Kur'an-ı Kerim", 5),
            ("Peygamber Kıssaları", 5),
            ("Mimarimizde Dinî Motifler", 5),
            # 6. sınıf
            ("Peygamber ve İlahi Kitap İnancı", 6),
            ("Ramazan ve Oruç", 6),
            ("Ahlaki Davranışlar", 6),
            ("Peygamberliğinden Önce Hz. Muhammed", 6),
            ("Kültürümüzde Dinî Motifler", 6),
            # 7. sınıf
            ("Melek ve Ahiret İnancı", 7),
            ("Hac, Umre ve Kurban", 7),
            ("İslam Düşüncesinde Yorumlar (Tasavvuf, Alevilik-Bektaşilik)", 7),
            ("Peygamber Olarak Hz. Muhammed (Mekke-Medine)", 7),
            ("Yaşayan Dünya Dinleri", 7),
            # 8. sınıf
            ("Kader İnancı", 8),
            ("Zekât, Hac ve Kurban İbadeti", 8),
            ("Din ve Hayat", 8),
            ("Hz. Muhammed'in Örnekliği", 8),
            ("Kur'an-ı Kerim ve Özellikleri", 8),
        ],
    },
    "İngilizce": {
        "min_grade": 5, "max_grade": 8,
        "exam_section": "LGS",
        "curriculum_model": "LGS",
        "available_for_graduate": False,
        "topics": [
            ("Friendship", 8),
            ("Teen Life", 8),
            ("In the Kitchen", 8),
            ("On the Phone", 8),
            ("The Internet", 8),
            ("Adventures", 8),
            ("Tourism", 8),
            ("Chores, Please!", 8),
            ("Science", 8),
            ("Natural Forces", 8),
        ],
    },
}


# =============================================================================
# MAARIF LİSE — 9-12. sınıf (Türkiye Yüzyılı Maarif Modeli, 2024-25'ten beri)
# =============================================================================
# Kaynak: RESMİ MEB — Türkiye Yüzyılı Maarif Modeli (tymm.meb.gov.tr), onaylı
# öğretim programı PDF'leri (2024programbiy/fiz/kim/math/turh/tar/cog/fel/din...).
# 2026-06 web doğrulamasıyla 9-12 dört sınıf da yayımlanmış; her ders kendi
# resmi terimini kullanır ("Tema" veya "Ünite") — `unit_term` ile korunur.
#
# YAPI: her ders `units` listesi → (unit_no, unit_name, grade, [alt_başlıklar]).
# Seed'de her ünite/tema bir PARENT Topic, alt başlıklar parent_id ile CHILD
# Topic olur. Test kitapları bu alt başlıklarla düzenlendiği için alt başlık =
# kitap bölümü eşleştirme adayı. (Eski seed yanlış/eksikti → tamamen yenilendi.)

MAARIF_LISE_CURRICULUM: dict[str, dict] = {
    "Matematik": {
        "min_grade": 9, "max_grade": 12,
        "exam_section": "TYT",
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": True,
        "unit_term": "Tema",
        "units": [
            (1, "Sayılar", 9, [
                "Üslü ve Köklü İfadeler", "Gerçek Sayı Aralıkları",
                "Sayı Kümeleri ve İşlem Özellikleri",
                "İki Kare Farkı ve Tam Kare Özdeşlikleri"]),
            (2, "Nicelikler ve Değişimler", 9, [
                "Doğrusal Fonksiyonlar ve Mutlak Değer Fonksiyonu",
                "Doğrusal Denklem ve Eşitsizlikler"]),
            (3, "Algoritma ve Bilişim", 9, [
                "Algoritma Temelli Problemler", "Mantık Bağlaçları ve Niceleyiciler"]),
            (4, "Geometrik Şekiller", 9, [
                "Üçgende Açı Özellikleri", "Üçgende Kenar Özellikleri"]),
            (5, "Eşlik ve Benzerlik", 9, [
                "Geometrik Dönüşümler (Yansıma, Öteleme, Dönme)",
                "Üçgenlerde Eşlik ve Benzerlik (Tales, Öklid, Pisagor)"]),
            (6, "İstatistiksel Araştırma Süreci", 9, [
                "Tek Değişkenli Veri Analizi (Histogram, Kutu Grafiği, Standart Sapma)"]),
            (7, "Veriden Olasılığa", 9, [
                "Deneysel ve Teorik Olasılık"]),
            (1, "Sayılar", 10, [
                "Bölünebilme, Asal Çarpanlar, OBEB ve OKEK"]),
            (2, "Nicelikler ve Değişimler", 10, [
                "Karesel Fonksiyonlar", "Karekök ve Rasyonel Fonksiyonlar",
                "Fonksiyonların Tersi", "İlgili Denklem ve Eşitsizlikler"]),
            (3, "Sayma, Algoritma ve Bilişim", 10, [
                "Sayma Stratejileri", "Cebirsel İşlemlerin Algoritmik Yapısı"]),
            (4, "Geometrik Şekiller", 10, [
                "Dik Üçgende Trigonometrik Oranlar", "Trigonometrik Özdeşlikler",
                "Üçgende Yardımcı Elemanlar", "Üçgende Alan",
                "Sinüs ve Kosinüs Teoremleri"]),
            (5, "Analitik İnceleme", 10, [
                "Noktanın Analitiği", "Doğrunun Analitiği", "İki Nokta Arası Uzaklık"]),
            (6, "İstatistiksel Araştırma Süreci", 10, [
                "İki Kategorik Değişken (İki Yönlü Tablo, Koşullu Sıklık)"]),
            (7, "Veriden Olasılığa", 10, [
                "Koşullu Olasılık", "Bağımlı ve Bağımsız Olaylar", "Bayes Teoremi"]),
            (1, "Nicelikler ve Değişimler", 11, [
                "Trigonometrik Fonksiyonlar", "Üstel ve Logaritmik Fonksiyonlar",
                "Fonksiyonlarla İşlemler ve Bileşke Fonksiyon"]),
            (2, "Geometrik Şekiller", 11, [
                "Dörtgenler ve Özel Dörtgenler", "Çokgenler"]),
            (3, "İstatistiksel Araştırma Süreci", 11, [
                "İki Nicel Değişken (Serpme Diyagramı, Korelasyon)"]),
            (1, "Nicelikler ve Değişimler", 12, [
                "Diziler (Aritmetik ve Geometrik Dizi)",
                "Polinom Fonksiyonlar", "Polinom ve Rasyonel Denklem-Eşitsizlikler"]),
            (2, "Değişimin Matematiği", 12, [
                "Limit ve Süreklilik", "Türev ve Türev Alma Kuralları",
                "Türevin Uygulamaları"]),
            (3, "Geometrik Şekiller", 12, [
                "Çemberde Açı, Kiriş ve Teğet", "Dairenin Alanı"]),
            (4, "Geometrik Cisimler", 12, [
                "Prizma, Silindir, Piramit, Koni ve Küre (Alan ve Hacim)"]),
            (5, "Hazır Veriler Üzerinde Çalışma", 12, [
                "Betimleyen ve İlişkilendiren İstatistiksel Çalışmalar"]),
        ],
    },
    "Fizik": {
        "min_grade": 9, "max_grade": 12,
        "exam_section": "AYT_SAY",
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": True,
        "unit_term": "Ünite",
        "units": [
            (1, "Fizik Bilimi ve Kariyer Keşfi", 9, [
                "Fizik Bilimi ve Alt Dalları", "Fizikte Kariyer Keşfi"]),
            (2, "Kuvvet ve Hareket", 9, [
                "Temel ve Türetilmiş Büyüklükler (SI)", "Skaler ve Vektörel Büyüklükler",
                "Vektörler", "Doğadaki Temel Kuvvetler", "Hareket Çeşitleri"]),
            (3, "Akışkanlar", 9, [
                "Basınç", "Sıvılarda Basınç", "Açık Hava Basıncı",
                "Kaldırma Kuvveti", "Bernoulli İlkesi"]),
            (4, "Enerji", 9, [
                "İç Enerji, Isı ve Sıcaklık", "Öz Isı ve Isı Sığası",
                "Hâl Değişimleri", "Isıl Denge", "Isı Aktarma Yolları"]),
            (1, "Kuvvet ve Hareket", 10, [
                "Sabit Hızlı Hareket", "Sabit İvmeli Hareket",
                "Serbest Düşme", "İki Boyutta Hareket (Atışlar)"]),
            (2, "Enerji", 10, [
                "İş, Enerji ve Güç", "Enerji Biçimleri",
                "Mekanik Enerji", "Enerji Kaynakları"]),
            (3, "Elektrik", 10, [
                "Basit Elektrik Devreleri", "Elektrik Akımı", "Ohm Yasası",
                "Dirençlerin Bağlanması", "Üreteçlerin Bağlanması"]),
            (4, "Dalgalar", 10, [
                "Dalgaların Temel Kavramları", "Dalga Çeşitleri",
                "Periyodik Hareketler", "Su Dalgalarında Yansıma ve Kırılma",
                "Rezonans ve Deprem"]),
            (1, "Kuvvet ve Hareket", 11, [
                "Newton'un Hareket Yasaları", "Sürtünme Kuvveti",
                "Limit Hız", "Çembersel Hareket"]),
            (2, "Elektrik ve Manyetizma", 11, [
                "Elektriksel Kuvvet ve Elektriksel Alan",
                "Manyetik Alan ve Manyetik Kuvvet", "İndüksiyon Akımı", "Transformatörler"]),
            (3, "Madde ve Doğası", 11, ["Yarı İletkenler", "Süper İletkenler"]),
            (4, "Optik", 11, [
                "Aydınlanma", "Düzlem ve Küresel Aynalar", "Işığın Kırılması",
                "Mercekler", "Prizmalar ve Fiber Optik"]),
            (1, "Kuvvet ve Hareket", 12, [
                "Tork ve Denge", "İtme ve Momentum", "Momentumun Korunumu",
                "Açısal Momentum"]),
            (2, "Enerji", 12, [
                "Yay Sabiti ve Esneklik Potansiyel Enerjisi",
                "Sürtünmede Yapılan İş", "Enerjinin Korunumu ve Verim"]),
            (3, "Dalgalar", 12, [
                "Kırınım", "Girişim", "Elektromanyetik Dalgalar", "Işık Renkleri"]),
            (4, "Madde ve Doğası", 12, [
                "Siyah Cisim Işıması ve Fotoelektrik Etki", "Modern Atom Teorisi",
                "Standart Model", "Nükleer Enerji"]),
        ],
    },
    "Kimya": {
        "min_grade": 9, "max_grade": 12,
        "exam_section": "AYT_SAY",
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": True,
        "unit_term": "Tema",
        "units": [
            (1, "Etkileşim", 9, [
                "Günlük Hayatta Kimya ve Kariyer", "Atom Teorileri ve Atomun Yapısı",
                "Atom Orbitalleri ve Elektron Dizilimi",
                "Periyodik Tablo ve Periyodik Özellikler"]),
            (2, "Çeşitlilik", 9, [
                "Metalik, İyonik ve Kovalent Bağ", "Lewis Yapısı ve Molekül Polarlığı",
                "Bileşiklerin Adlandırılması", "Moleküller Arası Etkileşimler",
                "Katılar ve Sıvılar"]),
            (3, "Sürdürülebilirlik", 9, [
                "Nanoparçacıklar ve Ekolojik Sürdürülebilirlik", "Yeşil Kimya"]),
            (1, "Etkileşim", 10, [
                "Kimyasal Tepkimelerin Oluşumu", "Kimyasal Tepkime Türleri",
                "Mol Kavramı", "Denklem Denkleştirme ve Stokiyometri",
                "Gazlar ve Gaz Yasaları", "İdeal Gaz Yasası", "Difüzyon ve Efüzyon"]),
            (2, "Çeşitlilik", 10, [
                "Çözünme Süreci ve Çözünürlük", "Derişim Birimleri (Molarite, ppm)",
                "Çözünürlüğe Etki Eden Faktörler", "Çözeltilerin Sınıflandırılması",
                "Koligatif Özellikler"]),
            (3, "Sürdürülebilirlik", 10, [
                "Yeşil Kimya ve Atmosferdeki Tepkimeler"]),
            (1, "Etkileşim", 11, [
                "Tepkimelerde Enerji (Entalpi)", "Bağ Enerjileri ve Oluşum Entalpileri",
                "Kimyasal Tepkimelerde Hız", "Hıza Etki Eden Faktörler"]),
            (2, "Çeşitlilik", 11, [
                "Kimyasal Denge ve Dengeyi Etkileyen Faktörler",
                "Asit-Baz Dengesi ve pH", "Tampon Çözeltiler ve Titrasyon",
                "Çözünürlük Dengesi (Kçç)"]),
            (3, "Sürdürülebilirlik", 11, [
                "Nanoteknoloji, Yeşil Hidrojen ve Mikroplastikler"]),
            (1, "Etkileşim", 12, [
                "İndirgenme-Yükseltgenme (Redoks) Tepkimeleri",
                "Elektrokimyasal Hücreler", "Elektroliz ve Korozyon"]),
            (2, "Çeşitlilik", 12, [
                "Organik Kimyaya Giriş (Hibritleşme, VSEPR)",
                "Hidrokarbonlar (Alifatik ve Aromatik)",
                "Fonksiyonel Gruplar ve İzomerlik"]),
            (3, "Sürdürülebilirlik", 12, [
                "Nanobilim, Biyobozunur Polimerler ve Yeşil Kimya"]),
        ],
    },
    "Biyoloji": {
        "min_grade": 9, "max_grade": 12,
        "exam_section": "AYT_SAY",
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": True,
        "unit_term": "Tema",
        "units": [
            (1, "Yaşam", 9, [
                "Biyolojinin Doğası ve Bilim Etiği", "Canlıların Ortak Özellikleri",
                "Canlıların Sınıflandırılması", "Üç Âlem (Domain) Sistemi",
                "Biyoçeşitlilik"]),
            (2, "Organizasyon", 9, [
                "İnorganik Bileşikler (Su, Mineraller, Asit-Baz)",
                "Organik Bileşikler (Karbonhidrat, Lipit, Protein, Enzim, Nükleik Asit, ATP)",
                "Hücre ve Organeller", "Hücre Zarından Madde Geçişleri",
                "Hücre-Doku-Organ-Sistem Organizasyonu"]),
            (1, "Enerji", 10, [
                "Canlılıkta Enerji ve ATP", "Fotosentez", "Kemosentez",
                "Hücresel Solunum (Oksijenli Solunum)", "Fermantasyon",
                "Sindirim Sistemleri"]),
            (2, "Ekoloji", 10, [
                "Ekosistemin Bileşenleri", "Komünite ve Popülasyon Ekolojisi",
                "Madde Döngüleri ve Enerji Akışı",
                "Ekolojik Sürdürülebilirlik ve Çevre Sorunları",
                "Biyoçeşitliliğin Korunması"]),
            (1, "Tepki", 11, [
                "Bitkilerde Tepki (Hormonlar, Tropizma, Nasti)", "Duyu Organları",
                "Sinir Sistemi", "Refleks ve Hareketin Kontrolü (Kas-İskelet)",
                "Bağışıklık Sistemi"]),
            (2, "Homeostazi", 11, [
                "Homeostazi ve Geri Bildirim Mekanizmaları", "Endokrin Sistem",
                "Dolaşım Sistemi", "Solunum Sistemi", "Boşaltım Sistemi"]),
            (1, "Üreme", 12, [
                "Hücre Bölünmeleri (Mitoz ve Mayoz)", "Eşeysiz Üreme",
                "Eşeyli Üreme", "İnsanda Üreme ve Gelişme",
                "Bitkilerde Üreme ve Gelişme"]),
            (2, "Gen", 12, [
                "Nükleik Asitler ve DNA Replikasyonu", "Gen İfadesi (Protein Sentezi)",
                "Kalıtım (Mendel Genetiği)", "Eşeye Bağlı Kalıtım",
                "Biyoteknoloji ve Genetik Mühendisliği"]),
        ],
    },
    "Türk Dili ve Edebiyatı": {
        "min_grade": 9, "max_grade": 12,
        "exam_section": "AYT_SOZ",
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": True,
        "unit_term": "Tema",
        "units": [
            (1, "Sözün İnceliği", 9, ["Şiir", "Deneme", "Mülakat"]),
            (2, "Anlam Arayışı", 9, ["Hikâye", "Anı", "Şiir"]),
            (3, "Anlamın Yapı Taşları", 9, ["Hikâye", "Gezi Yazısı", "Belgesel"]),
            (4, "Dilin Zenginliği", 9, ["Roman", "Tiyatro", "Eleştiri", "Otobiyografi"]),
            (1, "Sözün Ezgisi", 10, ["Koşuk", "Koşma", "Türkü", "Ninni", "Masal"]),
            (2, "Kelimelerin Ritmi", 10, ["Gazel", "Kaside", "Saf Şiir", "Söyleşi"]),
            (3, "Dünden Bugüne", 10, ["Destan", "Halk Hikâyesi", "Mesnevi", "Fabl"]),
            (4, "Nesillerin Mirası", 10, [
                "Dede Korkut Hikâyeleri", "Tanzimat ve Servetifünun Edebiyatı",
                "Millî Edebiyat"]),
            (1, "Bir Diyeceğim Var", 11, ["Karagöz Oyunu", "Mektup", "Dilekçe ve E-Posta"]),
            (2, "Kültür Yolculuğu", 11, [
                "Hikâye (Türk Dünyası)", "Anı", "Orhun Abideleri ve Dîvânu Lugâti't-Türk"]),
            (3, "Yaşamın İzinde", 11, ["Roman", "Biyografi", "Tezkire", "Mülakat"]),
            (4, "Hayatın Aynası", 11, ["Tiyatro", "Küçürek Hikâye", "Belgesel"]),
            (1, "Benim Yolculuğum", 12, ["Günlük", "Blog", "Şiir", "Hikâye"]),
            (2, "Toplumun Ahengi", 12, ["Roman", "Makale", "Haber Metni", "Eleştiri"]),
            (3, "Hayatın Dengesi", 12, ["Gezi Yazısı", "Broşür", "Hikâye", "Anket"]),
            (4, "Hayalimdeki Yarın", 12, ["Hikâye", "Makale", "Öz Geçmiş", "Röportaj"]),
        ],
    },
    "Tarih": {
        "min_grade": 9, "max_grade": 11,
        "exam_section": "AYT_SOZ",
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": True,
        "unit_term": "Ünite",
        "units": [
            (1, "Geçmişin İnşa Sürecinde Tarih", 9, [
                "Tarihin Doğası ve Tarih Öğrenmenin Faydaları",
                "Tarihsel Bilginin Üretimi ve Dijitalleşme"]),
            (2, "Eski Çağ Medeniyetleri", 9, [
                "Tarım Devrimi, Yerleşme ve Ekonomi", "Yönetim, Ordu ve Hukuk",
                "İnanç, Bilim ve Sanat", "Türklerde Konargöçer Yaşam"]),
            (3, "Orta Çağ Medeniyetleri", 9, [
                "Kitlesel Göçler", "Devletlerin Yönetim ve Ordu Yapıları",
                "Ticaret Yolları", "Bilim, Kültür ve Sanat"]),
            (1, "Türkistan'dan Türkiye'ye (1040-1299)", 10, [
                "Askerî Mücadeleler", "Devlet ve Ordu Teşkilatı",
                "Sosyal ve Ekonomik Yaşam", "Türk-İslam Bilim ve Sanatı"]),
            (2, "Beylikten Devlete Osmanlı (1299-1453)", 10, [
                "Osmanlı'nın Kuruluşu", "Siyasi ve Askerî Mücadeleler",
                "Devletleşme: Ordu, Hukuk ve Toprak Sistemi",
                "İskân ve İlim-İrfan Geleneği"]),
            (3, "Cihan Devleti Osmanlı (1453-1683)", 10, [
                "Siyasi ve Askerî Mücadeleler", "Yönetim ve Ordu Yapısındaki Değişim",
                "Avrupa'nın Sömürgeciliği", "İsyanlar", "Bilim, Kültür ve Sanat"]),
            (1, "Değişen Dünyada Osmanlı (1683-1789)", 11, [
                "Siyasi ve Askerî Mücadeleler", "Lale Devri",
                "Sanayi Devrimi'nin Etkileri"]),
            (2, "Dönüşüm Sürecinde Osmanlı (1789-1908)", 11, [
                "Fransız İhtilali'nin Etkileri", "Siyasi, Askerî ve İdari Gelişmeler",
                "Bilim, Sanat, Teknoloji ve Sanayileşme Çabaları"]),
            (3, "Savaşlar Sarmalında Osmanlı (1908-1918)", 11, [
                "Siyasi ve Askerî Gelişmeler", "Kitlesel Göç ve Salgınlar",
                "Osmanlı'nın İnsanlık Tarihine Katkıları"]),
        ],
    },
    "Coğrafya": {
        "min_grade": 9, "max_grade": 12,
        "exam_section": "AYT_SOZ",
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": True,
        "unit_term": "Ünite",
        "units": [
            (1, "Coğrafyanın Doğası", 9, [
                "Coğrafyanın Konusu ve Bölümleri", "Coğrafya Biliminin Gelişimi"]),
            (2, "Mekânsal Bilgi Teknolojileri", 9, [
                "Haritalar", "Türkiye'nin Coğrafi Konumu",
                "Mekânsal Bilgi Teknolojilerinin Bileşenleri"]),
            (3, "Doğal Sistemler ve Süreçler", 9, [
                "Hava Olayları", "İklim Sistemi ve Bileşenleri", "İklim Türleri",
                "İklim Değişiklikleri"]),
            (4, "Beşerî Sistemler ve Süreçler", 9, [
                "Nüfusun Dağılışı ve Hareketleri", "Demografik Dönüşüm ve Nüfus Piramitleri",
                "Nüfus Politikaları"]),
            (5, "Ekonomik Faaliyetler ve Etkileri", 9, [
                "Ekonomik Faaliyetleri Etkileyen Coğrafi Faktörler"]),
            (6, "Afetler ve Sürdürülebilir Çevre", 9, [
                "Tehlike, Risk ve Afet", "Afet Türleri", "Bütüncül Afet Yönetimi"]),
            (7, "Bölgeler, Ülkeler ve Küresel Bağlantılar", 9, [
                "Bölge ve Bölge Türleri"]),
            (1, "Coğrafyanın Doğası", 10, ["Coğrafi Bakış (Konum, Mekân, Dağılış)"]),
            (2, "Mekânsal Bilgi Teknolojileri", 10, [
                "CBS ve Uzaktan Algılama", "Mekânsal Verilerin Haritalara Aktarılması"]),
            (3, "Doğal Sistemler ve Süreçler", 10, [
                "Tektonik Süreçler", "Aşınma ve Çözünme Süreçleri",
                "Aşınım-Birikim ve Yeryüzü Şekilleri", "Yeryüzü Şekilleri ve Beşerî Faaliyet"]),
            (4, "Beşerî Sistemler ve Süreçler", 10, [
                "Yerleşmelerin Kuruluşu ve Gelişimi", "Yerleşmelerin Fonksiyonları"]),
            (5, "Ekonomik Faaliyetler ve Etkileri", 10, [
                "Ekonomik Sektörler ve Gelişmişlik", "Türkiye Ekonomisinin Sektörel Dağılımı"]),
            (6, "Afetler ve Sürdürülebilir Çevre", 10, [
                "Afetlerle Mücadele ve Afet Bilinci", "Afetlere Dirençli Yaşam Alanları"]),
            (7, "Bölgeler, Ülkeler ve Küresel Bağlantılar", 10, [
                "Türk Kültürünün Mekânsal Özellikleri"]),
            (1, "Coğrafyanın Doğası", 11, ["Mekânsal Sorunlar ve Coğrafya Bilimi"]),
            (2, "Mekânsal Bilgi Teknolojileri", 11, ["Web Tabanlı CBS"]),
            (3, "Doğal Sistemler ve Süreçler", 11, [
                "Su Kaynakları", "Türkiye'nin Su Kaynakları"]),
            (4, "Beşerî Sistemler ve Süreçler", 11, [
                "Yerleşmelerin Mekânsal Organizasyonu", "Yerleşmelerin Etki Alanları"]),
            (5, "Ekonomik Faaliyetler ve Etkileri", 11, [
                "Tarımsal Faaliyetler ve Sürdürülebilirlik", "Madenler ve Enerji Kaynakları",
                "Sanayileşmenin Mekânsal Etkileri"]),
            (6, "Afetler ve Sürdürülebilir Çevre", 11, [
                "Gezegen Sınırı ve Küresel İklim Değişikliği",
                "Suyun Sürdürülebilir Kullanımı"]),
            (7, "Bölgeler, Ülkeler ve Küresel Bağlantılar", 11, [
                "Türkiye'nin Kültürel Hinterlandı", "Örnek Ülkeler (Tarım, Sanayi, Enerji)"]),
            (1, "Coğrafyanın Doğası", 12, ["Geleceğin Dünyasında Coğrafya"]),
            (2, "Mekânsal Bilgi Teknolojileri", 12, ["CBS ve Tematik Haritalar"]),
            (3, "Doğal Sistemler ve Süreçler", 12, [
                "Toprak Oluşumu ve Kullanımı", "Bitki Türlerinin Çeşitliliği ve Dağılışı"]),
            (4, "Beşerî Sistemler ve Süreçler", 12, [
                "Kültür-Mekân Etkileşimi", "Kültürel Peyzaj ve Sürdürülebilirlik"]),
            (5, "Ekonomik Faaliyetler ve Etkileri", 12, [
                "Ulaşım Sistemleri", "Küresel Ticaret", "Turizm Faaliyetleri"]),
            (6, "Afetler ve Sürdürülebilir Çevre", 12, [
                "Çevre Sorunları ve Çözümleri", "Ortak Doğal ve Kültürel Miras"]),
            (7, "Bölgeler, Ülkeler ve Küresel Bağlantılar", 12, [
                "Uluslararası Birliktelik ve Anlaşmazlıklar", "Örnek Ülkeler"]),
        ],
    },
    "Felsefe": {
        "min_grade": 10, "max_grade": 11,
        "exam_section": "AYT_SOZ",
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": True,
        "unit_term": "Ünite",
        "units": [
            (1, "Felsefenin Doğası", 10, [
                "Felsefenin Anlamı ve Felsefi Düşünce",
                "Felsefenin Diğer Alanlarla İlişkisi ve İşlevi"]),
            (2, "Felsefe, Mantık ve Argümantasyon", 10, [
                "Düşünme ve Dil İlişkisi", "Argümantasyonun Yapısı ve Temel Kavramları"]),
            (3, "Varlık Felsefesi", 10, [
                "Varlık Felsefesinin Konusu", "Varlık Felsefesinin Temel Problemleri"]),
            (4, "Bilgi Felsefesi", 10, [
                "Bilginin İmkânı ve Kaynağı", "Doğruluk Ölçütleri"]),
            (5, "Ahlak Felsefesi", 10, [
                "Evrensel Ahlak Yasasının İmkânı", "Özgürlük-Sorumluluk İlişkisi"]),
            (6, "Estetik ve Sanat Felsefesi", 10, [
                "Güzellik ve Ortak Estetik Yargıların İmkânı"]),
            (7, "Siyaset Felsefesi", 10, [
                "Devletin Kökeni ve İktidarın Meşruiyeti", "İdeal Düzen ve Ütopyalar"]),
            (8, "Din Felsefesi", 10, [
                "Tanrı'nın Varlığına İlişkin Görüşler ve Kanıtlamalar",
                "Ruhun Ölümsüzlüğü"]),
            (9, "Bilim Felsefesi", 10, [
                "Bilimin Ne Olduğu", "Bilimin Yöntemi"]),
            (1, "Çevre Sorunları ve Felsefe", 11, [
                "Çevre Problemleri ve Sürdürülebilirlik", "Çevre Etiği"]),
            (2, "Teknoloji ve Hayat", 11, [
                "Teknoloji ve İnsan Hayatı", "Ontolojik ve Aksiyolojik Problemler"]),
            (3, "Akıl ve İnanç", 11, ["Akıl-İnanç İlişkisine Yönelik Görüşler"]),
            (4, "Edebiyat ve Felsefe", 11, [
                "Dil, Edebiyat ve Felsefe İlişkisi", "Edebî Unsurlara Felsefi Bakış"]),
            (5, "Hayatın Anlamı", 11, [
                "Mutluluk ve Hayat İlişkisi", "Varoluş ve Kendi Olma"]),
            (6, "Hukuk ve Felsefe", 11, [
                "Hukukun Gereği ve Kaynağı (Doğal Hukuk, Pozitif Hukuk)",
                "Ahlak-Hukuk İlişkisi"]),
        ],
    },
    "İngilizce": {
        "min_grade": 9, "max_grade": 12,
        "exam_section": "AYT_DIL",
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": True,
        "unit_term": "Theme",
        "units": [
            (1, "School Life", 9, ["Countries, Nationalities and Languages", "National Days"]),
            (2, "Classroom Life", 9, ["Friendships", "Daily and Study Routines"]),
            (3, "Personal Life: Appearance & Personality", 9, [
                "Physical Appearance", "Personality and Character Traits"]),
            (4, "Family Life", 9, ["Family Members' Jobs and Routines"]),
            (5, "Life in the House & Neighbourhood", 9, ["Houses, Rooms and Furniture"]),
            (6, "Life in the City & Country", 9, ["Local and International Food Culture"]),
            (7, "Life in the World & Nature", 9, ["Endangered Animals and Habitats"]),
            (1, "School Life & Education", 10, ["Types of Schools", "School Anxiety and Stress"]),
            (2, "Classroom Life & Learning", 10, ["Learning Styles", "Learning with Technology"]),
            (3, "Personal Life & Well-being", 10, ["Illnesses", "Fashion Preferences"]),
            (4, "Family Life & Home", 10, ["Routines (Past and Present)", "Hobbies and Interests"]),
            (5, "Neighbourhood, City & Social Life", 10, ["Attractions", "Services", "Transportation"]),
            (6, "Life in the World & Culture", 10, ["Continents and Nationalities", "Food Culture"]),
            (7, "Life in Nature & Global Problems", 10, ["Natural Resources and Protection"]),
            (8, "Life in the Universe & the Future", 10, ["Space Exploration", "Futuristic Technology"]),
            (1, "School Life & Education", 11, ["Comparing Schools and Education Systems"]),
            (2, "Classroom Life & Learning", 11, ["Traditional vs Modern Education"]),
            (3, "Personal Life & Well-being", 11, ["Physical Health", "Mental and Emotional Health"]),
            (4, "Family Life & Home", 11, ["Family Traditions and Values", "Family Problems"]),
            (5, "Neighbourhood, City & Social Life", 11, ["Types of Cities", "Rural vs Urban Life"]),
            (6, "Life in the World & Culture", 11, ["Music and Art", "Sports Cultures"]),
            (7, "Life in Nature & Global Problems", 11, ["Globalisation", "Environmental Issues"]),
            (8, "Life in the Universe & Future", 11, ["Future Lifestyles and Inventions"]),
            (1, "School Life & Education", 12, ["Coping with Challenges", "Future Plans"]),
            (2, "Personal Life & Well-being", 12, ["Social Health", "Economic Stability"]),
            (3, "Family Life & Home", 12, ["Technology and Family", "Family and Community"]),
            (4, "City & Social Life", 12, ["Communities and Lifestyles", "Infrastructure and Planning"]),
            (5, "Life in the Cultural and Natural World", 12, ["Cultural Diversity", "Climate Change"]),
            (6, "Life in the Universe & Future", 12, ["Space Organisations", "Future Aspirations"]),
        ],
    },
    "Din Kültürü ve Ahlak Bilgisi": {
        "min_grade": 9, "max_grade": 12,
        "exam_section": None,  # YKS'de yok, sadece okul dersi
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": False,
        "unit_term": "Ünite",
        "units": [
            (1, "Allah-İnsan İlişkisi", 9, [
                "İnsanın Yaratılışı", "Doğruyu Arayan Varlık Olarak İnsan",
                "İbadet ve Dua"]),
            (2, "İslam'da İnanç Esasları", 9, [
                "İman ve Mahiyeti", "İslam'da İman Esasları", "İmanın Kazandırdıkları"]),
            (3, "İslam'da İbadetler", 9, [
                "İbadetin Kapsamı", "Temel İbadetler", "İnsan ve İbadet"]),
            (4, "İslam'da Ahlak İlkeleri", 9, [
                "Ahlakın Mahiyeti", "Ahlakın Temel Unsurları", "Ahlaki Tutum ve Davranışlar"]),
            (5, "Kur'an'a Göre Hz. Muhammed", 9, [
                "Hz. Muhammed'in Beşerî ve Peygamberlik Yönü", "Hz. Muhammed'in Örnekliği"]),
            (1, "İslam'da Varlık ve Bilgi", 10, [
                "Bilgi ve Kaynakları", "Allah-Âlem İlişkisi"]),
            (2, "Allah'ı Tanımak", 10, [
                "Allah'ın Varlığının Delilleri", "İsim ve Sıfatlarıyla Allah"]),
            (3, "İslam'ın Evrensel Mesajları", 10, [
                "Tevhit İlkesi", "Adalet ve Eşitlik", "İslam ve Barış"]),
            (4, "Din, Çevre ve Teknoloji", 10, [
                "İnsan, Çevre ve Ahlak", "Teknoloji ve Ahlak"]),
            (5, "İslam Düşüncesinde Yorumlar", 10, [
                "Dinî Yorum Farklılıklarının Sebepleri",
                "İtikadi-Siyasi ve Fıkhi Yorumlar"]),
            (1, "Kader, İrade ve Sorumluluk", 11, [
                "İnsan ve Kader", "Akıl, İrade ve Sorumluluk"]),
            (2, "Din, Felsefe, Bilim ve Sanat", 11, [
                "Din, Felsefe ve Bilim", "Din ve Sanat"]),
            (3, "İslam Medeniyeti ve Gönül Coğrafyamız", 11, [
                "Medeniyetin Oluşumu", "İslam Medeniyetinin İzleri"]),
            (4, "İnançla İlgili Meseleler", 11, [
                "İnançla İlgili Felsefi Yaklaşımlar", "Kötülük Problemi", "Din İstismarı"]),
            (5, "Yahudilik ve Hristiyanlık", 11, ["Yahudilik", "Hristiyanlık"]),
            (1, "Kur'an-ı Kerim", 12, [
                "Kur'an'ın Tarihi", "Ana Konuları ve Temel Özellikleri",
                "Anlaşılmasında Temel İlkeler"]),
            (2, "Din ve Aile", 12, [
                "İslam'da Aile", "Aile İçi İletişim", "Aile ve Ahlaki Değerler"]),
            (3, "Güncel Dinî Meseleler", 12, [
                "Gıda, Bağımlılık ve Günlük Hayatla İlgili Meseleler"]),
            (4, "İslam Düşüncesinde Tasavvufi Yorumlar", 12, [
                "Tasavvufi Düşünce", "Alevilik-Bektaşilik ve Cem Erkânı"]),
            (5, "Hint ve Çin Dinleri", 12, [
                "Hinduizm ve Budizm", "Konfüçyanizm ve Taoizm"]),
        ],
    },
}


# =============================================================================
# KLASİK LİSE — 11-12. sınıf (Maarif öncesi, son nesil)
# =============================================================================
# Faz 2.3'te doldurulacak. 2026-27'de son 12. sınıf nesli (9'a 2023'te girenler);
# 2027-28 itibariyle Klasik 11 ve 12 tamamen biter.

KLASIK_LISE_CURRICULUM: dict[str, dict] = {
    # 11-12. sınıf konuları MEB klasik (Maarif öncesi) lise müfredatından.
    # Şu an aktif olan Klasik kohort: 2025-26'da 11. sınıf (9'a 2023'te girdi)
    # ve 12. sınıf (9'a 2022'de girdi). Eylül 2026'dan sonra 11 Maarif olur,
    # Eylül 2027'de 12 de Maarif. Bu müfredat son nesil için kalıcı kalır.
    # Kaynak: ÜniRehberi 11/12 ders sayfaları + 2018 MEB öğretim programları.

    "Matematik": {
        "min_grade": 11, "max_grade": 12,
        "exam_section": "TYT",
        "curriculum_model": "KLASIK_LISE",
        "available_for_graduate": True,
        "topics": [
            # 11. sınıf
            ("Trigonometri — Yönlü Açılar ve Trigonometrik Fonksiyonlar", 11),
            ("Analitik Geometri — Doğrunun Analitik İncelenmesi", 11),
            ("Fonksiyonlarla İlgili Uygulamalar", 11),
            ("İkinci Dereceden Fonksiyonlar ve Grafikleri", 11),
            ("Fonksiyonların Dönüşümleri", 11),
            ("İkinci Dereceden Denklem Sistemleri", 11),
            ("İkinci Dereceden Bir Bilinmeyenli Eşitsizlikler", 11),
            ("Çemberin Temel Elemanları ve Açılar", 11),
            ("Çemberde Teğet", 11),
            ("Dairenin Çevresi ve Alanı", 11),
            ("Uzay Geometri — Katı Cisimler", 11),
            ("Olasılık — Koşullu / Deneysel / Teorik", 11),
            # 12. sınıf
            ("Üstel ve Logaritmik Fonksiyonlar", 12),
            ("Üstel ve Logaritmik Denklem/Eşitsizlikler", 12),
            ("Gerçek Sayı Dizileri", 12),
            ("Trigonometri — Toplam-Fark ve İki Kat Açı Formülleri", 12),
            ("Trigonometrik Denklemler", 12),
            ("Analitik Düzlemde Temel Dönüşümler", 12),
            ("Limit ve Süreklilik", 12),
            ("Anlık Değişim Oranı ve Türev", 12),
            ("Türevin Uygulamaları", 12),
            ("Belirsiz İntegral", 12),
            ("Belirli İntegral ve Uygulamaları", 12),
            ("Çemberin Analitik İncelenmesi", 12),
        ],
    },
    "Fizik": {
        "min_grade": 11, "max_grade": 12,
        "exam_section": "AYT_SAY",
        "curriculum_model": "KLASIK_LISE",
        "available_for_graduate": True,
        "topics": [
            # 11. sınıf
            ("Vektörler ve Bağıl Hareket", 11),
            ("Newton'ın Hareket Yasaları", 11),
            ("Bir Boyutta Sabit İvmeli Hareket", 11),
            ("Serbest Düşme ve Düşey Atış", 11),
            ("İki Boyutta Hareket — Yatay/Düşey Atış", 11),
            ("Enerji ve Hareket", 11),
            ("İtme ve Çizgisel Momentum", 11),
            ("Tork, Denge ve Denge Şartları", 11),
            ("Basit Makineler", 11),
            ("Elektriksel Kuvvet ve Elektrik Alan", 11),
            ("Elektriksel Potansiyel ve Sığa", 11),
            ("Manyetizma ve Elektromanyetik İndüklenme", 11),
            ("Alternatif Akım ve Transformatörler", 11),
            # 12. sınıf
            ("Düzgün Çembersel Hareket", 12),
            ("Dönerek Öteleme ve Açısal Momentum", 12),
            ("Kütle Çekim Kuvveti ve Kepler Kanunları", 12),
            ("Basit Harmonik Hareket", 12),
            ("Dalgalarda Kırınım, Girişim ve Doppler", 12),
            ("Elektromanyetik Dalgalar", 12),
            ("Atom Kavramının Tarihsel Gelişimi", 12),
            ("Büyük Patlama ve Evrenin Oluşumu", 12),
            ("Radyoaktivite", 12),
            ("Özel Görelilik", 12),
            ("Kuantum Fiziğine Giriş, Fotoelektrik, Compton, De Broglie", 12),
            ("Modern Fiziğin Teknolojideki Uygulamaları", 12),
        ],
    },
    "Kimya": {
        "min_grade": 11, "max_grade": 12,
        "exam_section": "AYT_SAY",
        "curriculum_model": "KLASIK_LISE",
        "available_for_graduate": True,
        "topics": [
            # 11. sınıf
            ("Modern Atom Teorisi — Atomun Kuantum Modeli", 11),
            ("Periyodik Sistem ve Elektron Dizilimleri", 11),
            ("Periyodik Özellikler ve Yükseltgenme Basamakları", 11),
            ("Gazlar — Özellikleri ve Yasaları", 11),
            ("İdeal Gaz Yasası ve Kinetik Teori", 11),
            ("Gaz Karışımları ve Gerçek Gazlar", 11),
            ("Sıvı Çözeltiler — Çözücü-Çözünen Etkileşimleri", 11),
            ("Derişim Birimleri ve Koligatif Özellikler", 11),
            ("Çözünürlük ve Etkileyen Faktörler", 11),
            ("Kimyasal Tepkimelerde Enerji (Entalpi, Bağ Enerjisi)", 11),
            ("Kimyasal Tepkimelerde Hız", 11),
            ("Kimyasal Tepkimelerde Denge ve Sulu Çözelti Dengeleri", 11),
            # 12. sınıf
            ("Kimya ve Elektrik — Elektrokimyasal Hücreler", 12),
            ("Elektrot Potansiyelleri ve Elektroliz", 12),
            ("Korozyon", 12),
            ("Karbon Kimyasına Giriş — Anorganik/Organik Bileşikler", 12),
            ("Lewis Formülleri, Hibritleşme, Molekül Geometrileri", 12),
            ("Hidrokarbonlar ve Fonksiyonel Gruplar", 12),
            ("Alkoller, Eterler, Karbonil Bileşikleri", 12),
            ("Karboksilik Asitler ve Esterler", 12),
            ("Enerji Kaynakları ve Sürdürülebilirlik", 12),
        ],
    },
    "Biyoloji": {
        "min_grade": 11, "max_grade": 12,
        "exam_section": "AYT_SAY",
        "curriculum_model": "KLASIK_LISE",
        "available_for_graduate": True,
        "topics": [
            # 11. sınıf
            ("Sinir Sisteminin Yapısı ve İşleyişi", 11),
            ("Endokrin Sistem ve Hormonlar", 11),
            ("Duyu Organları", 11),
            ("Destek ve Hareket Sistemi", 11),
            ("Sindirim Sistemi", 11),
            ("Dolaşım Sistemi — Kalp, Damar, Kan", 11),
            ("Lenf Dolaşımı ve Bağışıklık", 11),
            ("Solunum Sistemi", 11),
            ("Boşaltım Sistemi ve Homeostasis", 11),
            ("Üreme Sistemi ve Embriyonik Gelişim", 11),
            ("Komünite Ekolojisi", 11),
            ("Popülasyon Ekolojisi", 11),
            # 12. sınıf
            ("Genden Proteine — Nükleik Asitler", 12),
            ("Genetik Şifre ve Protein Sentezi", 12),
            ("Canlılık ve Enerji", 12),
            ("Fotosentez", 12),
            ("Kemosentez", 12),
            ("Hücresel Solunum", 12),
            ("Bitki Biyolojisi — Yapı ve Madde Taşınması", 12),
            ("Bitkilerde Eşeyli Üreme", 12),
            ("Canlılar ve Çevre", 12),
        ],
    },
    "Türk Dili ve Edebiyatı": {
        "min_grade": 11, "max_grade": 12,
        "exam_section": "AYT_SOZ",
        "curriculum_model": "KLASIK_LISE",
        "available_for_graduate": True,
        "topics": [
            # 11. sınıf
            ("Giriş — Edebiyat-Toplum İlişkisi ve Sanat Akımları", 11),
            ("Cumhuriyet Dönemi Hikâye (1923-1940)", 11),
            ("Cumhuriyet Dönemi Hikâye (1940-1960)", 11),
            ("Tanzimat Dönemi Şiir", 11),
            ("Servetifünun Dönemi Şiir", 11),
            ("Saf Şiir ve Milli Edebiyat Şiiri", 11),
            ("Cumhuriyet İlk Yılları Şiiri", 11),
            ("Makale", 11),
            ("Sohbet ve Fıkra", 11),
            ("Roman 1923-1950", 11),
            ("Roman 1950-1980 (Modernizm)", 11),
            ("Dünya Edebiyatında Roman", 11),
            ("Tiyatro 1923-1950 / 1950-1980", 11),
            ("Eleştiri", 11),
            ("Mülakat / Röportaj", 11),
            # 12. sınıf
            ("Giriş — Edebiyat-Felsefe-Psikoloji İlişkisi", 12),
            ("Cumhuriyet Sonrası Hikâye", 12),
            ("Milli Edebiyat ve Garip Akımı Şiiri", 12),
            ("İkinci Yeni Şiiri", 12),
            ("Dini-Geleneksel ve Metafizik Şiir", 12),
            ("1960 Sonrası Toplumcu Şiir", 12),
            ("1980 Sonrası Türk Şiiri", 12),
            ("Cumhuriyet Sonrası Halk Şiiri", 12),
            ("Cumhuriyet Dönemi Türk Romanı (1923-1950 / 1950-1980 / 1980 Sonrası)", 12),
            ("Tiyatro (Cumhuriyet Sonrası)", 12),
            ("Deneme", 12),
            ("Söylev (Nutuk)", 12),
        ],
    },
    "Tarih": {
        "min_grade": 11, "max_grade": 11,
        "exam_section": "AYT_SOZ",
        "curriculum_model": "KLASIK_LISE",
        "available_for_graduate": False,  # 12'de "T.C. İnkılap Tarihi" ayrı ders
        "topics": [
            # 11. sınıf — Genel Tarih (Osmanlı modernleşmesi)
            ("Değişen Dünya Dengeleri ve Osmanlı Siyaseti (1595-1700)", 11),
            ("XVII. Yüzyıl Osmanlı Politikaları ve Avrupa Denizcilik Stratejileri", 11),
            ("1700-1774 Yılları Osmanlı Devleti'nin Rekabeti", 11),
            ("Değişim Çağında Avrupa ve Osmanlı", 11),
            ("Osmanlı'da İsyanlar ve Düzeni Koruma Çabaları", 11),
            ("Devrimler Çağı — İhtilaller", 11),
            ("Sanayi İnkılabı ve Sömürgecilik", 11),
            ("Osmanlı'da Modern Orduya Geçiş", 11),
            ("Uluslararası İlişkilerde Denge (1774-1914)", 11),
            ("Tanzimat, Islahat Fermanları ve Kanun-ı Esasi", 11),
            ("XIX-XX. Yüzyıl Değişen Gündelik Hayat", 11),
        ],
    },
    "T.C. İnkılap Tarihi ve Atatürkçülük": {
        "min_grade": 12, "max_grade": 12,
        "exam_section": "AYT_SOZ",
        "curriculum_model": "KLASIK_LISE",
        "available_for_graduate": True,
        "topics": [
            # 12. sınıf
            ("20. Yüzyıl Başlarında Osmanlı Devleti ve Dünya", 12),
            ("Millî Mücadele", 12),
            ("Atatürkçülük ve Türk İnkılabı", 12),
            ("İki Savaş Arasındaki Dönemde Türkiye ve Dünya", 12),
            ("II. Dünya Savaşı Sürecinde Türkiye ve Dünya", 12),
            ("II. Dünya Savaşı Sonrasında Türkiye ve Dünya", 12),
            ("Toplumsal Devrim Çağında Dünya ve Türkiye", 12),
            ("21. Yüzyılın Eşiğinde Türkiye ve Dünya", 12),
        ],
    },
    "Coğrafya": {
        "min_grade": 11, "max_grade": 12,
        "exam_section": "AYT_SOZ",
        "curriculum_model": "KLASIK_LISE",
        "available_for_graduate": True,
        "topics": [
            # 11. sınıf
            ("Doğal Sistemler — Ekosistemler ve Biyoçeşitlilik", 11),
            ("Beşeri Sistemler — Nüfus Politikaları", 11),
            ("Yerleşmelerin Özellikleri ve Şehirler", 11),
            ("Ekonomik Faaliyetler ve Doğal Kaynaklar", 11),
            ("Türkiye'de Tarım, Maden, Sanayi", 11),
            ("Küresel Ortam — Kültür Bölgeleri", 11),
            ("Küreselleşen Dünya — Ticaret, Turizm, Sanayi", 11),
            ("Çevre ve Toplum — Çevre Sorunları", 11),
            ("Sürdürülebilir Doğal Kaynak Kullanımı", 11),
            # 12. sınıf
            ("Ekstrem Doğa Olayları ve Küresel İklim Değişimi", 12),
            ("Ekonomik Faaliyetlerin Sosyal-Kültürel Etkileri", 12),
            ("Şehirleşme, Sanayi ve Göç", 12),
            ("Türkiye'nin İşlevsel Bölgeleri ve Kalkınma Projeleri", 12),
            ("Hizmet Sektörü ve Ulaşım", 12),
            ("Türkiye'nin Dış Ticareti", 12),
            ("Türkiye'nin Kültürel Mirası ve Turizm", 12),
            ("Türkiye'nin Jeopolitik Konumu", 12),
            ("Gelişmişlik ve Kalkınma", 12),
            ("Doğal Kaynak Potansiyeli ve Enerji Güzergahları", 12),
            ("Çevre Politikaları ve Anlaşmaları", 12),
        ],
    },
    "Felsefe": {
        "min_grade": 11, "max_grade": 11,
        "exam_section": "AYT_SOZ",
        "curriculum_model": "KLASIK_LISE",
        "available_for_graduate": True,  # 11'de tamamlandığı için 12+mezunda da ref
        "topics": [
            # Klasik müfredatta Felsefe sadece 11'de — dönem-bazlı 5 ünite
            ("MÖ 6. Yüzyıl – MS 2. Yüzyıl Felsefesi", 11),
            ("MS 2. Yüzyıl – MS 15. Yüzyıl Felsefesi", 11),
            ("15. Yüzyıl – 17. Yüzyıl Felsefesi", 11),
            ("18. Yüzyıl – 19. Yüzyıl Felsefesi", 11),
            ("20. Yüzyıl Felsefesi", 11),
        ],
    },
    "İngilizce": {
        "min_grade": 11, "max_grade": 12,
        "exam_section": "AYT_DIL",
        "curriculum_model": "KLASIK_LISE",
        "available_for_graduate": True,
        "topics": [
            # Klasik 11-12 İngilizce tema-bazlı; öğretmen kullandığı temayı ekler.
        ],
    },
}


# =============================================================================
# SINAV-BAZLI KANONİK TAKSONOMİ (model-bağımsız) — TYT / AYT
# =============================================================================
# Okul müfredatı (LGS/Maarif/Klasik) model+sınıf bazlıdır; YKS sınavı (TYT/AYT)
# ise model-üstü ve sınıf-üstüdür. Test kitapları + koçluk bu listeyle düzenlenir.
# Bu dersler `curriculum_model=None` (model-bağımsız) + `exam_section` ile seed
# edilir → YKS öğrencisi için ilerleme panelinde ve eşleştirmede omurga olur.
# Okul müfredatı (Maarif tema/ünite) SİLİNMEZ — referans olarak kalır.
#
# Kaynak: ÖSYM/MEB TYT-AYT konu çerçevesi (yaygın yayınevi taksonomisi). Konu
# adları en yaygın yayınevi formuyla yazıldı (auto-map uyumu yüksek olsun diye).
# Kapsam: Matematik (TYT + AYT). Diğer dersler sonraki aşamalarda eklenecek.

EXAM_CURRICULUM: dict[str, dict] = {
    "TYT Matematik": {
        "min_grade": 9, "max_grade": 12,
        "exam_section": "TYT",
        "curriculum_model": None,
        "available_for_graduate": True,
        "topics": [
            ("Temel Kavramlar", 9),
            ("Sayı Basamakları", 9),
            ("Tek ve Çift Sayılar", 9),
            ("Ardışık Sayılar", 9),
            ("Bölme ve Bölünebilme", 9),
            ("EBOB - EKOK", 9),
            ("Asal Sayılar", 9),
            ("Faktöriyel", 9),
            ("Rasyonel Sayılar", 9),
            ("Basit Eşitsizlikler", 9),
            ("Mutlak Değer", 9),
            ("Üslü Sayılar", 9),
            ("Köklü Sayılar", 9),
            ("Çarpanlara Ayırma", 9),
            ("Oran ve Orantı", 9),
            ("Birinci Dereceden Denklemler", 9),
            ("Sayı - Kesir Problemleri", 9),
            ("Yaş Problemleri", 9),
            ("Yüzde Problemleri", 9),
            ("Kar - Zarar Problemleri", 9),
            ("Karışım Problemleri", 9),
            ("İşçi Problemleri", 9),
            ("Hareket Problemleri", 9),
            ("Grafik Problemleri", 9),
            ("Sayısal Yetenek Problemleri", 9),
            ("Kümeler", 9),
            ("Mantık", 9),
            ("Fonksiyonlar", 10),
            ("Polinomlar", 10),
            ("Permütasyon", 10),
            ("Kombinasyon", 10),
            ("Binom", 10),
            ("Olasılık", 10),
            ("Veri ve İstatistik", 10),
        ],
    },
    "AYT Matematik": {
        "min_grade": 11, "max_grade": 12,
        "exam_section": "AYT_SAY",
        "curriculum_model": None,
        "available_for_graduate": True,
        "topics": [
            ("Polinomlar", 11),
            ("İkinci Dereceden Denklemler", 11),
            ("Parabol", 11),
            ("Eşitsizlikler", 11),
            ("Trigonometri", 11),
            ("Karmaşık Sayılar", 11),
            ("Logaritma ve Üstel Fonksiyonlar", 12),
            ("Diziler", 12),
            ("Limit ve Süreklilik", 12),
            ("Türev", 12),
            ("İntegral", 12),
            ("Fonksiyon Grafikleri ve Uygulamaları", 12),
        ],
    },
    # ------------------------------- TYT -------------------------------
    "TYT Türkçe": {
        "min_grade": 9, "max_grade": 12, "exam_section": "TYT",
        "curriculum_model": None, "available_for_graduate": True,
        "topics": [
            ("Sözcükte Anlam", 9), ("Cümlede Anlam", 9), ("Paragraf", 9),
            ("Anlatım Biçimleri ve Düşünceyi Geliştirme Yolları", 9),
            ("Ses Bilgisi", 9), ("Yazım Kuralları", 9), ("Noktalama İşaretleri", 9),
            ("Sözcükte Yapı (Ekler)", 9), ("Sözcük Türleri", 10),
            ("Fiiller (Anlam, Çatı, Kip, Yapı)", 10), ("Fiilimsiler", 10),
            ("Cümlenin Ögeleri", 10), ("Cümle Türleri", 10),
            ("Anlatım Bozuklukları", 10),
        ],
    },
    "TYT Geometri": {
        "min_grade": 9, "max_grade": 12, "exam_section": "TYT",
        "curriculum_model": None, "available_for_graduate": True,
        "topics": [
            ("Temel Geometrik Kavramlar ve Doğruda Açılar", 9),
            ("Üçgenler", 9), ("Üçgende Açı-Kenar Bağıntıları", 9),
            ("Üçgende Eşlik ve Benzerlik", 9), ("Üçgende Alan", 9),
            ("Çokgenler ve Dörtgenler", 10), ("Çember ve Daire", 11),
            ("Analitik Geometri", 11),
            ("Katı Cisimler (Prizma, Piramit, Koni, Küre, Silindir)", 10),
            ("Dönüşüm Geometrisi", 10),
        ],
    },
    "TYT Fizik": {
        "min_grade": 9, "max_grade": 12, "exam_section": "TYT",
        "curriculum_model": None, "available_for_graduate": True,
        "topics": [
            ("Fizik Bilimine Giriş", 9), ("Madde ve Özellikleri", 9),
            ("Hareket ve Kuvvet", 9), ("İş, Güç ve Enerji", 9),
            ("Isı ve Sıcaklık", 9), ("Elektrostatik", 10), ("Elektrik", 10),
            ("Manyetizma", 10), ("Basınç ve Kaldırma Kuvveti", 10),
            ("Dalgalar", 10), ("Optik", 10),
        ],
    },
    "TYT Kimya": {
        "min_grade": 9, "max_grade": 12, "exam_section": "TYT",
        "curriculum_model": None, "available_for_graduate": True,
        "topics": [
            ("Kimya Bilimi", 9), ("Atom ve Periyodik Sistem", 9),
            ("Kimyasal Türler Arası Etkileşimler", 9), ("Maddenin Halleri", 9),
            ("Kimyanın Temel Kanunları ve Kimyasal Hesaplamalar", 10),
            ("Karışımlar", 10), ("Asitler, Bazlar ve Tuzlar", 10),
            ("Kimya Her Yerde", 10),
        ],
    },
    "TYT Biyoloji": {
        "min_grade": 9, "max_grade": 12, "exam_section": "TYT",
        "curriculum_model": None, "available_for_graduate": True,
        "topics": [
            ("Canlıların Ortak Özellikleri", 9),
            ("Canlıların Temel Bileşenleri", 9), ("Hücre ve Organelleri", 9),
            ("Canlıların Sınıflandırılması", 9),
            ("Hücre Bölünmeleri (Mitoz-Mayoz)", 10),
            ("Kalıtımın Genel İlkeleri", 10), ("Ekosistem Ekolojisi", 10),
            ("Güncel Çevre Sorunları", 10),
        ],
    },
    "TYT Tarih": {
        "min_grade": 9, "max_grade": 12, "exam_section": "TYT",
        "curriculum_model": None, "available_for_graduate": True,
        "topics": [
            ("Tarih ve Zaman", 9), ("İnsanlığın İlk Dönemleri", 9),
            ("Orta Çağ'da Dünya", 9), ("İlk ve Orta Çağlarda Türk Dünyası", 9),
            ("İslam Medeniyetinin Doğuşu", 9),
            ("İlk Türk-İslam Devletleri", 9),
            ("Selçuklu Türkiyesi", 10), ("Beylikten Devlete Osmanlı", 10),
            ("Dünya Gücü Osmanlı Devleti", 10),
            ("Osmanlı Kültür ve Medeniyeti", 10),
            ("Değişen Dünya Dengeleri Karşısında Osmanlı", 11),
            ("XX. Yüzyıl Başlarında Osmanlı Devleti", 12),
            ("Milli Mücadele", 12), ("Atatürkçülük ve Türk İnkılabı", 12),
        ],
    },
    "TYT Coğrafya": {
        "min_grade": 9, "max_grade": 12, "exam_section": "TYT",
        "curriculum_model": None, "available_for_graduate": True,
        "topics": [
            ("Doğa ve İnsan", 9), ("Dünya'nın Şekli ve Hareketleri", 9),
            ("Harita Bilgisi", 9), ("Coğrafi Konum", 9), ("İklim Bilgisi", 9),
            ("Yerin Şekillenmesi (İç-Dış Kuvvetler)", 10),
            ("Su, Toprak ve Bitkiler", 10), ("Nüfus", 10), ("Göç", 10),
            ("Yerleşme", 10), ("Ekonomik Faaliyetler", 11),
            ("Bölgeler", 11), ("Doğal Afetler ve Çevre", 10),
        ],
    },
    "TYT Felsefe": {
        "min_grade": 9, "max_grade": 12, "exam_section": "TYT",
        "curriculum_model": None, "available_for_graduate": True,
        "topics": [
            ("Felsefenin Konusu", 10), ("Bilgi Felsefesi", 10),
            ("Varlık Felsefesi", 10), ("Ahlak Felsefesi", 10),
            ("Sanat Felsefesi", 10), ("Din Felsefesi", 10),
            ("Siyaset Felsefesi", 10), ("Bilim Felsefesi", 10),
            ("MÖ 6 - MS 2. Yüzyıl Felsefesi", 11),
            ("MS 2 - MS 15. Yüzyıl Felsefesi", 11),
            ("15-17. Yüzyıl Felsefesi", 11), ("18-19. Yüzyıl Felsefesi", 11),
            ("20. Yüzyıl Felsefesi", 11),
        ],
    },
    "TYT Din Kültürü ve Ahlak Bilgisi": {
        "min_grade": 9, "max_grade": 12, "exam_section": "TYT",
        "curriculum_model": None, "available_for_graduate": True,
        "topics": [
            ("Bilgi ve İnanç", 9), ("İslam ve İbadet", 9),
            ("Gençlik ve Değerler", 9), ("Allah-İnsan İlişkisi", 10),
            ("Hz. Muhammed ve Gençlik", 10), ("Din ve Hayat", 10),
            ("İslam Düşüncesinde Yorumlar", 11),
            ("Kur'an'a Göre Hz. Muhammed", 11), ("İnançla İlgili Meseleler", 11),
            ("Dünya ve Ahiret", 12), ("Yaşayan Dinler", 12),
        ],
    },
    # ------------------------------- AYT -------------------------------
    "AYT Geometri": {
        "min_grade": 11, "max_grade": 12, "exam_section": "AYT_SAY",
        "curriculum_model": None, "available_for_graduate": True,
        "topics": [
            ("Üçgenlerde Açı ve Kenar Bağıntıları", 11), ("Üçgende Alan", 11),
            ("Açıortay ve Kenarortay", 11), ("Üçgende Benzerlik", 11),
            ("Çokgenler ve Dörtgenler", 11), ("Dörtgenlerde Alan", 11),
            ("Çemberde Açı, Kiriş ve Teğet", 11),
            ("Çemberin Analitik İncelenmesi", 12), ("Analitik Geometri (Doğru)", 11),
            ("Katı Cisimler", 11), ("Dönüşüm Geometrisi", 12),
        ],
    },
    "AYT Fizik": {
        "min_grade": 11, "max_grade": 12, "exam_section": "AYT_SAY",
        "curriculum_model": None, "available_for_graduate": True,
        "topics": [
            ("Vektörler", 11), ("Kuvvet, Tork ve Denge", 11),
            ("Kütle Merkezi ve Basit Makineler", 11),
            ("Hareket (Doğrusal, Bağıl, Atışlar)", 11),
            ("Newton'un Hareket Yasaları", 11), ("İş, Güç ve Enerji", 11),
            ("İtme ve Momentum", 11), ("Elektrik Alan ve Potansiyel", 11),
            ("Paralel Levhalar ve Sığa", 11),
            ("Manyetizma ve Elektromanyetik İndüksiyon", 11),
            ("Çembersel Hareket", 12), ("Basit Harmonik Hareket", 12),
            ("Dalga Mekaniği", 12), ("Atom Fiziği ve Radyoaktivite", 12),
            ("Modern Fizik", 12),
        ],
    },
    "AYT Kimya": {
        "min_grade": 11, "max_grade": 12, "exam_section": "AYT_SAY",
        "curriculum_model": None, "available_for_graduate": True,
        "topics": [
            ("Modern Atom Teorisi", 11), ("Gazlar", 11),
            ("Sıvı Çözeltiler ve Çözünürlük", 11),
            ("Kimyasal Tepkimelerde Enerji", 11),
            ("Kimyasal Tepkimelerde Hız", 11),
            ("Kimyasal Tepkimelerde Denge", 11), ("Asit-Baz Dengesi", 11),
            ("Çözünürlük Dengesi", 11), ("Kimya ve Elektrik", 12),
            ("Karbon Kimyasına Giriş", 12), ("Organik Bileşikler", 12),
            ("Enerji Kaynakları ve Bilimsel Gelişmeler", 12),
        ],
    },
    "AYT Biyoloji": {
        "min_grade": 11, "max_grade": 12, "exam_section": "AYT_SAY",
        "curriculum_model": None, "available_for_graduate": True,
        "topics": [
            ("Sinir Sistemi", 11), ("Endokrin Sistem ve Hormonlar", 11),
            ("Duyu Organları", 11), ("Destek ve Hareket Sistemi", 11),
            ("Sindirim Sistemi", 11), ("Dolaşım ve Bağışıklık Sistemi", 11),
            ("Solunum Sistemi", 11), ("Boşaltım Sistemi", 11),
            ("Üreme Sistemi ve Embriyonik Gelişim", 11),
            ("Komünite ve Popülasyon Ekolojisi", 11),
            ("Genden Proteine (Nükleik Asitler, Protein Sentezi)", 12),
            ("Canlılarda Enerji Dönüşümleri (Fotosentez, Solunum)", 12),
            ("Bitki Biyolojisi", 12), ("Canlılık ve Çevre", 12),
        ],
    },
    "AYT Edebiyat": {
        "min_grade": 11, "max_grade": 12, "exam_section": "AYT_SOZ",
        "curriculum_model": None, "available_for_graduate": True,
        "topics": [
            ("Güzel Sanatlar ve Edebiyat", 9), ("Edebi Türler", 10),
            ("Edebi Sanatlar (Söz Sanatları)", 10),
            ("Şiir Bilgisi (Nazım Biçim ve Türleri)", 10),
            ("İslamiyet Öncesi ve Geçiş Dönemi Türk Edebiyatı", 10),
            ("Halk Edebiyatı", 10), ("Divan Edebiyatı", 11),
            ("Tanzimat Dönemi Edebiyatı", 11),
            ("Servet-i Fünun ve Fecr-i Ati Edebiyatı", 11),
            ("Milli Edebiyat Dönemi", 11),
            ("Cumhuriyet Dönemi Edebiyatı", 12), ("Edebiyat Akımları", 12),
        ],
    },
    "AYT Tarih": {
        "min_grade": 11, "max_grade": 12, "exam_section": "AYT_SOZ",
        "curriculum_model": None, "available_for_graduate": True,
        "topics": [
            ("Değişen Dünya Dengeleri Karşısında Osmanlı (1595-1774)", 11),
            ("Değişim Çağında Avrupa ve Osmanlı", 11),
            ("Uluslararası İlişkilerde Denge Stratejisi (1774-1914)", 11),
            ("Devrimler Çağında Değişen Devlet-Toplum İlişkileri", 11),
            ("Sermaye ve Emek", 11),
            ("XIX. ve XX. Yüzyılda Değişen Gündelik Hayat", 11),
            ("XX. Yüzyıl Başlarında Osmanlı ve Dünya", 12),
            ("Milli Mücadele", 12), ("Atatürkçülük ve Türk İnkılabı", 12),
            ("İki Savaş Arası Dönemde Türkiye ve Dünya", 12),
            ("II. Dünya Savaşı ve Sonrası", 12), ("Soğuk Savaş Dönemi", 12),
            ("Yumuşama Dönemi ve Sonrası", 12), ("Küreselleşen Dünya", 12),
        ],
    },
    "AYT Coğrafya": {
        "min_grade": 11, "max_grade": 12, "exam_section": "AYT_SOZ",
        "curriculum_model": None, "available_for_graduate": True,
        "topics": [
            ("Ekosistem ve Madde Döngüleri", 11), ("Nüfus Politikaları", 11),
            ("Türkiye'de Nüfus ve Yerleşme", 11),
            ("Ekonomik Faaliyetler ve Doğal Kaynaklar", 11),
            ("Türkiye Ekonomisi (Tarım, Sanayi, Madencilik)", 11),
            ("Bölgeler ve Ülkeler", 11),
            ("Uluslararası Ulaşım ve Ticaret", 11), ("Doğal Afetler", 11),
            ("Çevre ve Toplum", 12),
            ("Küresel Ortam: Bölgeler ve Ülkeler", 12),
            ("Çevre Sorunları ve Yönetimi", 12),
        ],
    },
    "AYT Felsefe Grubu": {
        "min_grade": 11, "max_grade": 12, "exam_section": "AYT_SOZ",
        "curriculum_model": None, "available_for_graduate": True,
        "topics": [
            ("Felsefe: MÖ 6 - MS 2. Yüzyıl", 11),
            ("Felsefe: MS 2 - MS 15. Yüzyıl", 11),
            ("Felsefe: 15-17. Yüzyıl", 11), ("Felsefe: 18-19. Yüzyıl", 11),
            ("Felsefe: 20. Yüzyıl", 11), ("Psikoloji: Psikoloji Bilimi", 11),
            ("Psikoloji: Öğrenme, Bellek, Düşünme", 11),
            ("Psikoloji: Ruh Sağlığının Temelleri", 11),
            ("Sosyoloji: Birey ve Toplum", 12),
            ("Sosyoloji: Toplumsal Yapı ve Kurumlar", 12),
            ("Sosyoloji: Toplumsal Değişme ve Gelişme", 12),
            ("Mantık: Mantığa Giriş", 12), ("Mantık: Klasik Mantık", 12),
            ("Mantık: Sembolik Mantık", 12),
        ],
    },
    "AYT Din Kültürü ve Ahlak Bilgisi": {
        "min_grade": 11, "max_grade": 12, "exam_section": "AYT_SOZ",
        "curriculum_model": None, "available_for_graduate": True,
        "topics": [
            ("Dünya ve Ahiret", 11), ("Kur'an'a Göre Hz. Muhammed", 11),
            ("Kur'an'da Bazı Kavramlar", 11), ("İnançla İlgili Meseleler", 11),
            ("Yahudilik ve Hıristiyanlık", 12), ("İslam ve Bilim", 12),
            ("Anadolu'da İslam", 12),
            ("İslam Düşüncesinde Tasavvufi Yorumlar", 12),
            ("Güncel Dini Meseleler", 12), ("Hint ve Çin Dinleri", 12),
        ],
    },
}


# =============================================================================
# Tüm müfredat sözlüklerinin birleşik view'i (seed.py kullanır)
# =============================================================================

ALL_CURRICULA: dict[str, dict[str, dict]] = {
    "LGS": LGS_CURRICULUM,
    "MAARIF_LISE": MAARIF_LISE_CURRICULUM,
    "KLASIK_LISE": KLASIK_LISE_CURRICULUM,
}


# =============================================================================
# Geriye uyumluluk — eski seed.py / curriculum_data.py API'si
# =============================================================================
# Mevcut testler veya import'lar için CURRICULUM ve SUBJECT_ORDER eski şekliyle
# LGS verisinden türetilir.

CURRICULUM: dict[str, list[str]] = {
    name: [t[0] for t in spec["topics"]]
    for name, spec in LGS_CURRICULUM.items()
}

SUBJECT_ORDER: list[str] = list(LGS_CURRICULUM.keys())
