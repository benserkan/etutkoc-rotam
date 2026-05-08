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
        "topics": [
            # 5. sınıf — Maarif Modeli temaları (2025-26'dan)
            ("Tema: Oyun Dünyası", 5),
            ("Tema: Milli Mücadele ve Atatürk", 5),
            ("Tema: Duygularımı Tanıyorum", 5),
            ("Tema: Geleneklerimiz", 5),
            ("Tema: İletişim ve Sosyal İlişkiler", 5),
            ("Tema: Sağlıklı Yaşıyorum", 5),
            # 6. sınıf — temalar
            ("Tema: Dilimizin Zenginliği", 6),
            ("Tema: Bağımsızlık Yolu", 6),
            ("Tema: Farklı Dünyalar", 6),
            ("Tema: İletişim ve Sosyal İlişkiler", 6),
            ("Tema: Bilim ve Teknoloji", 6),
            ("Tema: Lider Ruhlar", 6),
            # 7. sınıf — temalar
            ("Tema: Hayat Boyu Gelişim", 7),
            ("Tema: Bir Hilal Uğruna", 7),
            ("Tema: İletişim ve Sosyal İlişkiler", 7),
            ("Tema: Türk Sanatı", 7),
            ("Tema: Okuma Kültürü", 7),
            ("Tema: Hak ve Sorumluluklar", 7),
            # 8. sınıf konuları (mevcut, MEB 2023 baskısı LGS müfredatı)
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
    },
    "Matematik": {
        "min_grade": 5, "max_grade": 8,
        "exam_section": "LGS",
        "curriculum_model": "LGS",
        "available_for_graduate": False,
        "topics": [
            # 5. sınıf — Maarif Modeli temaları
            ("Geometrik Şekiller", 5),
            ("Sayılar ve Nicelikler I", 5),
            ("Geometrik Nicelikler", 5),
            ("Sayılar ve Nicelikler II", 5),
            ("İstatistiksel Araştırma Süreci", 5),
            ("İşlemlerle Cebirsel Düşünme", 5),
            ("Veriden Olasılığa", 5),
            # 6. sınıf
            ("Çarpan ve Katlar, Bölünebilme Kriterleri", 6),
            ("Asal Sayılar, OBEB ve OKEK", 6),
            ("Ondalık Gösterimler ve Kesir-Bölme İlişkisi", 6),
            ("Ölçme Birimleri ve Yüzde Problemleri", 6),
            ("Bilinmeyen Nicelikler ve Cebirsel İfadeler", 6),
            ("Sayı ve Şekil Örüntüleri", 6),
            ("Paralel Doğrular, Açılar ve Dörtgenler", 6),
            ("Üçgen, Yamuk, Paralelkenar Açıları", 6),
            ("Alan Ölçme — Dikdörtgen, Paralelkenar, Üçgen", 6),
            ("Çemberin Uzunluğu ve Çap İlişkisi", 6),
            ("Veriye Dayalı Karar ve Olasılık Tahmini", 6),
            # 7. sınıf
            ("Doğal, Tam ve Rasyonel Sayılar", 7),
            ("Rasyonel Sayılarla İşlemler ve Problemler", 7),
            ("Oran ve Orantı, Doğru Orantılı Problemler", 7),
            ("Cebirsel İfadeler ve Birinci Dereceden Denklem/Eşitsizlikler", 7),
            ("Yansıma Dönüşümü, Orta Dikme ve Açıortay", 7),
            ("Eş Küplerle Hacim ve Yüzey Alan", 7),
            ("Daire ve Daire Dilimi Alanları", 7),
            ("Eşkenar Dörtgen ve Yamuk Alanı", 7),
            ("Üçgende Kenarortay, Açıortay, Yükseklik", 7),
            ("Veri Analizi ve Olasılık (Tümleyen, Ayrık Olaylar)", 7),
            # 8. sınıf
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
    },
    "Fen Bilimleri": {
        "min_grade": 5, "max_grade": 8,
        "exam_section": "LGS",
        "curriculum_model": "LGS",
        "available_for_graduate": False,
        "topics": [
            # 5. sınıf — Maarif Modeli temaları
            ("Olasılık Spektrumu — Kesin ve İmkansız Olay", 5),
            ("Kuvveti Tanıyalım", 5),
            ("Canlıların Yapısına Yolculuk", 5),
            ("Işığın Dünyası", 5),
            ("Maddenin Doğası", 5),
            ("Yaşamımızdaki Elektrik", 5),
            ("Sürdürülebilir Yaşam ve Geri Dönüşüm", 5),
            # 6. sınıf
            ("Güneş Sistemi ve Tutulmalar", 6),
            ("Kuvvetin Etkisinde Hareket — Bileşke, Sürat, Hız", 6),
            ("Canlılarda Sistemler — Üreme ve Sinir Sistemi", 6),
            ("Işığın Yansıması ve Renkler", 6),
            ("Maddenin Ayırt Edici Özellikleri", 6),
            ("Elektriğin İletimi ve Direnç", 6),
            ("Sürdürülebilir Yaşam ve Etkileşim", 6),
            # 7. sınıf
            ("Uzay Çağı — Türkiye ve Uzay Araştırmaları", 7),
            ("Yıldızlar, Galaksiler ve Evren", 7),
            ("Kuvvet, İş ve Enerji İlişkisi", 7),
            ("Enerji Dönüşümleri ve Korunumu", 7),
            ("Sindirim, Dolaşım, Solunum, Boşaltım Sistemleri", 7),
            ("Işığın Kırılması ve Mercekler", 7),
            ("Atomun Yapısı ve Element-Bileşik", 7),
            ("Periyodik Tablo ve İlk 18 Element", 7),
            ("Karışımlar ve Ayrılması", 7),
            ("Elektriklenme ve Elektrik Yükleri", 7),
            ("Besin Zinciri, Enerji Akışı ve Sürdürülebilir Yaşam", 7),
            # 8. sınıf
            ("Mevsimler ve İklim", 8),
            ("DNA ve Genetik Kod", 8),
            ("Basınç", 8),
            ("Madde ve Endüstri", 8),
            ("Basit Makineler", 8),
            ("Enerji Dönüşümleri ve Çevre Bilimi", 8),
            ("Elektrik Yükleri ve Elektrik Enerjisi", 8),
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
# Faz 2.2'de doldurulacak (15 ders × 9-10. sınıf). 11-12 MEB tarafından
# henüz yayınlanmadığı için placeholder kalıyor; Eylül 2026'dan önce eklenir.

MAARIF_LISE_CURRICULUM: dict[str, dict] = {
    # 9-10. sınıf konuları MEB Türkiye Yüzyılı Maarif Modeli (2024-25 onaylı)
    # öğretim programlarından alınmıştır. Ünite başlıkları kesin; alt-konuların
    # bir kısmı 3. parti rehberlerden derlendiği için dikkat:
    #   - 10. sınıf: detaylı (Atlas Rehberlik dökümünden)
    #   - 9. sınıf: ünite bazlı + Mat/Fiz/Kim/Bio için kısmi alt-konu
    #   - 11-12: MEB henüz yayınlamadı (Eylül 2026 / 2027 sonrası eklenir)
    # Eksik alt-konuları öğretmen UI üzerinden ekleyebilir.

    "Matematik": {
        "min_grade": 9, "max_grade": 12,
        "exam_section": "TYT",
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": True,
        "topics": [
            # 9. sınıf
            ("Sayılar — Üslü ve Köklü Gösterimler", 9),
            ("Sayılar — Aralıklar ve İşlemler", 9),
            ("Sayı Kümeleri ve İşlem Özellikleri", 9),
            ("İki Kare Farkı ve Tamkare Özdeşlikleri", 9),
            ("Doğrusal Fonksiyonlar ve Mutlak Değer", 9),
            ("Doğrusal Denklem ve Eşitsizlikler", 9),
            ("Algoritma Temelli Problemler", 9),
            ("Mantık Bağlaçları ve Niceleyiciler", 9),
            ("Üçgende Açı ve Kenar Özellikleri", 9),
            ("Geometrik Şekillerde Eşlik ve Benzerlik", 9),
            ("Geometrik Dönüşümler (Yansıma, Öteleme, Dönme)", 9),
            ("İstatistiksel Araştırma Süreci", 9),
            ("Veriden Olasılığa", 9),
            # 10. sınıf
            ("Üçgenler ve Trigonometri", 10),
            ("İki Kategorik Değişkenli Dağılımlar", 10),
            ("Asal Çarpanlar, OBEB ve OKEK", 10),
            ("Bölme Algoritması", 10),
            ("Fonksiyon Tanımı ve Özellikleri", 10),
            ("Ters Fonksiyonlar", 10),
            ("Doğrusal, Karesel, Karekök ve Rasyonel Fonksiyonlar", 10),
            ("Doğrusal/Karesel/Karekök/Rasyonel Denklem ve Eşitsizlikler", 10),
            ("Sayma Stratejileri ve Algoritmik Dil", 10),
            ("Koşullu Olasılık", 10),
            ("Nokta ve Doğrunun Analitiği", 10),
        ],
    },
    "Fizik": {
        "min_grade": 9, "max_grade": 12,
        "exam_section": "AYT_SAY",
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": True,
        "topics": [
            # 9. sınıf
            ("Fizik Bilimi ve Kariyer Keşfi", 9),
            ("Temel ve Türetilmiş Nicelikler, Vektörler", 9),
            ("Doğadaki Temel Kuvvetler", 9),
            ("Hareket ve Hareket Türleri", 9),
            ("Akışkanlar — Basınç ve Sıvılarda Basınç", 9),
            ("Kaldırma Kuvveti ve Bernoulli İlkesi", 9),
            ("Enerji, Isı ve Sıcaklık", 9),
            ("Hâl Değişimi, Isıl Denge ve Isı Aktarımı", 9),
            # 10. sınıf
            ("Sabit Hızlı Hareket", 10),
            ("Sabit İvmeli Hareket", 10),
            ("Serbest Düşme (Bir Boyut)", 10),
            ("Serbest Düşme (İki Boyut)", 10),
            ("İş, Enerji ve Güç", 10),
            ("Enerji Çeşitleri ve Mekanik Enerji", 10),
            ("Temel Elektrik Kavramları", 10),
            ("Elektrik Akımı", 10),
            ("Dalga Türleri", 10),
            ("Dalgaların Temel Özellikleri", 10),
        ],
    },
    "Kimya": {
        "min_grade": 9, "max_grade": 12,
        "exam_section": "AYT_SAY",
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": True,
        "topics": [
            # 9. sınıf
            ("Etkileşim — Atom Teorileri ve Periyodik Tablo", 9),
            ("Çeşitlilik — Kimyasal Bağlar", 9),
            ("Lewis Yapıları, Polar/Apolar Adlandırma", 9),
            ("Katılar ve Sıvılar", 9),
            ("Sürdürülebilirlik — Nanoparçacıklar ve Yeşil Kimya", 9),
            # 10. sınıf
            ("Kimyasal Tepkimelerin Oluşumu", 10),
            ("Kimyasal Tepkime Türleri", 10),
            ("Mol Kavramı ve Stokiyometrik Hesaplamalar", 10),
            ("Gazlar — Özellikleri ve Yasaları", 10),
            ("İdeal Gaz Yasası", 10),
            ("Graham Difüzyon ve Efüzyon", 10),
            ("Çözünme Süreci ve Derişim Birimleri", 10),
            ("Çözünürlük ve Etkileyen Faktörler", 10),
            ("Çözeltilerin Sınıflandırılması ve Koligatif Özellikler", 10),
            ("Yeşil Kimya — Çevresel ve Ekonomik Sürdürülebilirlik", 10),
        ],
    },
    "Biyoloji": {
        "min_grade": 9, "max_grade": 12,
        "exam_section": "AYT_SAY",
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": True,
        "topics": [
            # 9. sınıf
            ("Yaşam — Biyoloji Bilimi ve Sınıflandırma", 9),
            ("Üç Âlem Sistemi ve Biyoçeşitlilik", 9),
            ("Organizasyon — İnorganik ve Organik Moleküller", 9),
            ("Hücre Yapısı ve Madde Geçişleri", 9),
            # 10. sınıf
            ("Canlılık için Enerjinin Önemi", 10),
            ("ATP", 10),
            ("Fotosentez Süreci", 10),
            ("Fotosentez Hızını Etkileyen Faktörler", 10),
            ("Kemosentez", 10),
        ],
    },
    "Türk Dili ve Edebiyatı": {
        "min_grade": 9, "max_grade": 12,
        "exam_section": "AYT_SOZ",
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": True,
        "topics": [
            # 9. sınıf
            ("Giriş — Edebiyat, Gösterge, Düşünce, Dil, İletişim", 9),
            ("Hikâye (Öykü)", 9),
            ("Şiir", 9),
            ("Masal / Fabl", 9),
            ("Roman", 9),
            ("Tiyatro", 9),
            ("Biyografi / Otobiyografi / CV / Dilekçe / Tutanak", 9),
            ("Mektup / E-Posta", 9),
            ("Günlük / Blog", 9),
            # 10. sınıf
            ("Sözün Ezgisi — Kelimelerin Ritmi", 10),
            ("Dünden Bugüne", 10),
            ("Nesillerin Mirası", 10),
        ],
    },
    "Tarih": {
        "min_grade": 9, "max_grade": 11,
        "exam_section": "AYT_SOZ",
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": True,
        "topics": [
            # 9. sınıf
            ("Geçmişin İnşa Süreci, Tarihin Doğası, Dijitalleşme", 9),
            ("Eski Çağ Medeniyetleri, Tarım Devrimi, Yönetim, Hukuk", 9),
            ("Orta Çağ Göçleri, Devletler, Ticaret Yolları, Bilim/Kültür", 9),
            # 10. sınıf
            ("Türkistan'dan Türkiye'ye (1040–1299)", 10),
            ("Beylikten Devlete Osmanlı (1299–1453)", 10),
            ("Cihan Devleti Osmanlı (1453–1683)", 10),
        ],
    },
    "Coğrafya": {
        "min_grade": 9, "max_grade": 12,
        "exam_section": "AYT_SOZ",
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": True,
        "topics": [
            # 9. sınıf
            ("Coğrafya Biliminin Konusu ve Bölümleri", 9),
            ("Haritalar", 9),
            ("Doğal Sistemler — Hava ve İklim", 9),
            ("Beşeri Sistemler — Nüfus", 9),
            ("Ekonomik Faaliyetler", 9),
            ("Afetler", 9),
            ("Bölgeler", 9),
            # 10. sınıf
            ("Coğrafya Bilimi", 10),
            ("Mekânsal Bilgi Teknolojileri", 10),
            ("Tektonik Süreçler ve Yeryüzü Şekilleri", 10),
            ("Yerleşmeler", 10),
            ("Ekonomik Faaliyetler", 10),
            ("Afetler", 10),
            ("Türk Kültürü", 10),
        ],
    },
    "Felsefe": {
        "min_grade": 10, "max_grade": 11,
        "exam_section": "AYT_SOZ",
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": True,
        "topics": [
            # 10. sınıf — 9'da Felsefe yok, 10'da başlar
            ("Felsefenin Doğası", 10),
            ("Felsefe, Mantık ve Argümantasyon", 10),
            ("Varlık Felsefesi", 10),
            ("Bilgi Felsefesi", 10),
            ("Ahlak Felsefesi", 10),
            ("Estetik ve Sanat Felsefesi", 10),
            ("Siyaset Felsefesi", 10),
            ("Din Felsefesi", 10),
            ("Bilim Felsefesi", 10),
        ],
    },
    "İngilizce": {
        "min_grade": 9, "max_grade": 12,
        "exam_section": "AYT_DIL",
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": True,
        "topics": [
            # MEB resmî 9-12 İngilizce öğretim programı tema-bazlı; alt-konular
            # zaman içinde tema değişimleriyle güncellenir. Öğretmen UI üzerinden
            # kullandığı temayı ekleyebilir. Boş bırakıyoruz — kullanıcı eklesin.
        ],
    },
    "Din Kültürü ve Ahlak Bilgisi": {
        "min_grade": 9, "max_grade": 12,
        "exam_section": None,  # YKS'de yok, sadece okul dersi
        "curriculum_model": "MAARIF_LISE",
        "available_for_graduate": False,
        "topics": [
            # 9. sınıf
            ("Allah-İnsan İlişkisi", 9),
            ("İnanç Esasları", 9),
            ("İbadetler", 9),
            ("Ahlak İlkeleri", 9),
            ("Hz. Muhammed", 9),
            # 10. sınıf
            ("İslamda Varlık ve Birlik", 10),
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
