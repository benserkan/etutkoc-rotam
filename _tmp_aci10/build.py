import json, sys
src, dst = sys.argv[1], sys.argv[2]
d = json.load(open(src, encoding="utf-8"))
G = "Dik Üçgende Trigonometrik Oranlar"
rows = [
 # Tema 1 Geometrik Şekiller (22 = 20 + 2 BT)
 ("Dik Üçgende Trigonometrik Oranlar", 5, G, "Tema 1 T1-T5 (trig oranlar, özel açılar, birim çember)"),
 ("Trigonometrik Özdeşlikler", 1, "Trigonometrik Özdeşlikler", "Tema 1 T6"),
 ("Üçgende Yardımcı Elemanlar (Açıortay, Kenarortay, Özel Noktalar)", 5, "Üçgende Yardımcı Elemanlar", "Tema 1 T8-T12 (T8-T9 açıortay, T10-T11 kenarortay/ağırlık merkezi, T12 çevrel çember/diklik merkezi)"),
 ("Üçgende Alan", 4, "Üçgende Alan", "Tema 1 T13-T16 (T15 sinüslü alan, T16 alan oranları)"),
 ("Sinüs ve Kosinüs Teoremleri", 2, "Sinüs ve Kosinüs Teoremleri", "Tema 1 T17 kosinüs, T18 sinüs teoremi"),
 ("Trigonometri ve Yardımcı Elemanlar (Karma)", 1, "", "Tema 1 T19 ÖTT (trig alan + ağırlık merkezi karışık)"),
 ("Üçgende Yardımcı Elemanlar (ÖSYM Tadında)", 1, "Üçgende Yardımcı Elemanlar", "Tema 1 T20 ÖTT açıortay/ağırlık merkezi"),
 ("Üçgende Alan (ÖSYM Tadında)", 1, "Üçgende Alan", "Tema 1 T21 ÖTT"),
 ("Bağlam Temelli Test (Karma) (Tema 1: Geometrik Şekiller)", 2, "", "Tema 1 T7 + T22 BT"),
 # Tema 2 (7 = 5 + 2 BT)
 ("İstatistiksel Araştırma Süreci (İki Kategorik Değişken, İki Yönlü Tablo)", 5, "İki Kategorik Değişken (İki Yönlü Tablo, Koşullu Sıklık)", "Tema 2 T1-T5 (araştırma sorusu, iki yönlü/göreli/koşullu sıklık tablosu, yanlılık)"),
 ("Bağlam Temelli Test (Karma) (Tema 2: İstatistiksel Araştırma Süreci)", 2, "", "Tema 2 T6-T7 BT"),
 # Tema 3 (20 = 18 + 2 BT)
 ("Asal Sayılar, Asal Çarpanlar ve Bölenler", 6, "Bölünebilme, Asal Çarpanlar, OBEB ve OKEK", "Tema 3 T1-T6 (asal/aralarında asal, asal çarpanlar, pozitif bölen sayısı; T5 ÖTT)"),
 ("OBEB ve OKEK", 4, "Bölünebilme, Asal Çarpanlar, OBEB ve OKEK", "Tema 3 T7-T10 (T9-T10 ÖTT problemleri)"),
 ("Bölme ve Bölünebilme Kuralları", 5, "Bölünebilme, Asal Çarpanlar, OBEB ve OKEK", "Tema 3 T11-T15 (T11 bölme, T12 2-5, T13 3-9, T14 4-8, T15 karma kurallar)"),
 ("Sayılar Karma Tekrar (Asal Çarpanlar, OBEB-OKEK, Bölünebilme)", 2, "Bölünebilme, Asal Çarpanlar, OBEB ve OKEK", "Tema 3 T16-T17 (türsüz karma tekrar, tek müfredat başlığı içinde)"),
 ("Bölünebilme (ÖSYM Tadında)", 1, "Bölünebilme, Asal Çarpanlar, OBEB ve OKEK", "Tema 3 T18 ÖTT"),
 ("Bağlam Temelli Test (Karma) (Tema 3: Sayılar)", 2, "", "Tema 3 T19-T20 BT"),
 # Tema 4 (32 = 30 + 2 BT)
 ("Fonksiyon Kavramı ve Özellikleri", 6, "", "Tema 4 T1-T6 (fonksiyon tanımı/grafiği, tanım-görüntü kümesi, sıfır, işaret, artan-azalan, maks-min, bire bir/örten, tek-çift)"),
 ("Doğrusal Fonksiyonlar", 2, "Doğrusal Fonksiyonlar ve Mutlak Değer Fonksiyonu", "Tema 4 T7-T8 (doğrusal referans fonksiyon, dönüşümler, modelleme)"),
 ("Karesel Fonksiyonlar", 5, "Karesel Fonksiyonlar", "Tema 4 T9-T13 (karesel referans + dönüşümler; T11-T13 ÖTT)"),
 ("Karekök Fonksiyonlar", 3, "Karekök ve Rasyonel Fonksiyonlar", "Tema 4 T14-T16 (T16 ÖTT)"),
 ("Rasyonel Fonksiyonlar", 4, "Karekök ve Rasyonel Fonksiyonlar", "Tema 4 T17-T20 (T18-T20 ÖTT)"),
 ("Fonksiyonların Tersi", 4, "Fonksiyonların Tersi", "Tema 4 T21-T24 (doğrusal, rasyonel, karesel, karekök fonksiyonların tersi)"),
 ("Fonksiyonlar (Karma)", 3, "", "Tema 4 T25-T27 (türsüz karma: grafik modelleme, karesel/karekök/rasyonel/doğrusal karışık)"),
 ("Karesel Fonksiyonlar (ÖSYM Tadında)", 1, "Karesel Fonksiyonlar", "Tema 4 T28 ÖTT (maks-min, gelir modelleme)"),
 ("İlgili Denklem ve Eşitsizlikler", 2, "İlgili Denklem ve Eşitsizlikler", "Tema 4 T29-T30 ÖTT (iki fonksiyonun eşitliği/karşılaştırılması, modelleme)"),
 ("Bağlam Temelli Test (Karma) (Tema 4: Nicelikler ve Değişimler)", 2, "", "Tema 4 T31-T32 BT"),
 # Tema 5 (21 = 19 + 2 BT)
 ("Toplama ve Çarpma Yoluyla Sayma", 4, "Sayma Stratejileri", "Tema 5 T1-T4 (T4 ÖTT)"),
 ("Sıralama (Permütasyon)", 4, "Sayma Stratejileri", "Tema 5 T5-T8 (dizilimler, tekrarlı permütasyon, en kısa yol; T8 karma sayma)"),
 ("Seçme (Kombinasyon)", 4, "Sayma Stratejileri", "Tema 5 T9-T12 (T10 ÖTT, T11-T12 geometrik kombinasyon)"),
 ("Pascal Üçgeni", 1, "Sayma Stratejileri", "Tema 5 T13"),
 ("Algoritma ve Akış Şemaları", 3, "Cebirsel İşlemlerin Algoritmik Yapısı", "Tema 5 T14-T16 (doğal dil algoritma, akış şeması, döngü)"),
 ("Sayma Stratejileri (Karma Tekrar)", 1, "Sayma Stratejileri", "Tema 5 T17 (türsüz; 7 sayma + 1 algoritma sorusu)"),
 ("Sayma Stratejileri (ÖSYM Tadında)", 2, "Sayma Stratejileri", "Tema 5 T18-T19 ÖTT"),
 ("Bağlam Temelli Test (Karma) (Tema 5: Sayma, Algoritma ve Bilişim)", 2, "", "Tema 5 T20-T21 BT"),
 # Tema 6 (12 = 10 + 2 BT)
 ("Noktanın Analitiği", 1, "Noktanın Analitiği", "Tema 6 T1 (sayı doğrusu, bölgeler, eksenlere uzaklık)"),
 ("İki Nokta Arası Uzaklık", 2, "İki Nokta Arası Uzaklık", "Tema 6 T2-T3"),
 ("Orta Nokta, Ağırlık Merkezi ve Bölen Nokta", 2, "Noktanın Analitiği", "Tema 6 T4-T5"),
 ("Doğrunun Analitiği (Eğim ve Doğru Denklemi)", 3, "Doğrunun Analitiği", "Tema 6 T6-T8"),
 ("Doğrunun Analitiği (ÖSYM Tadında)", 2, "Doğrunun Analitiği", "Tema 6 T9-T10 ÖTT (paralel/dik doğrular, kesişim, uzaklık)"),
 ("Bağlam Temelli Test (Karma) (Tema 6: Analitik İnceleme)", 2, "", "Tema 6 T11-T12 BT"),
 # Tema 7 (10 = 9 + 1 BT)
 ("Örnek Uzay ve Olasılık", 1, "Deneysel ve Teorik Olasılık", "Tema 7 T1 (örnek uzay, temel olasılık)"),
 ("Koşullu Olasılık", 1, "Koşullu Olasılık", "Tema 7 T2"),
 ("Bağımsız Olaylar", 1, "Bağımlı ve Bağımsız Olaylar", "Tema 7 T3 (iki kutu/atıcılık; birkaç tablo-koşullu soru)"),
 ("Koşullu Olasılık (ÖSYM Tadında)", 1, "Koşullu Olasılık", "Tema 7 T4 ÖTT"),
 ("Bağımlı ve Bağımsız Olaylar", 1, "Bağımlı ve Bağımsız Olaylar", "Tema 7 T5 (iadeli/iadesiz çekiliş)"),
 ("Bayes Teoremi", 1, "Bayes Teoremi", "Tema 7 T6"),
 ("Olasılık (Karma)", 1, "", "Tema 7 T7 (türsüz; koşullu + bağımsız + Bayes karışık)"),
 ("Koşullu Olasılık ve Bayes (ÖSYM Tadında)", 1, "Koşullu Olasılık", "Tema 7 T8 ÖTT (baskın koşullu, 2 Bayes sorusu)"),
 ("Bayes Teoremi (ÖSYM Tadında)", 1, "Bayes Teoremi", "Tema 7 T9 ÖTT"),
 ("Bağlam Temelli Test (Karma) (Tema 7: Veriden Olasılığa)", 1, "", "Tema 7 T10 BT"),
]
old_total = sum(s["test_count"] for s in d["sections"])
new_total = sum(r[1] for r in rows)
assert old_total == new_total == 124, (old_total, new_total)
assert len({r[0] for r in rows}) == len(rows)
d["sections"] = [{"label": r[0], "test_count": r[1], "topic": r[2]} for r in rows]
d["curriculum_model"] = "maarif_lise"
d["warnings"] = [
 "Alt konu bölümü SORU İÇERİĞİNDEN yapıldı (kitap bantlarında yalnız tema adı var). Her testin iki sayfasının soru metni (PyMuPDF metin katmanı) okunup baskın konuya atandı; tema toplamları ve test sayıları değişmedi (22/7/20/32/21/12/10 = 124).",
 "Tema 1'de Bağlam Temelli T7 tema ortasında; BT satırı orijinaldeki gibi tek satır (2 test: T7 + T22) olarak tema sonunda korundu.",
 "10. sınıf listesinde karşılığı olmayan 2 blok için 9. sınıf Maarif adı kullanıldı (aynı Matematik dersinde var): Tema 4 T7-T8 → 'Doğrusal Fonksiyonlar ve Mutlak Değer Fonksiyonu', Tema 7 T1 → 'Deneysel ve Teorik Olasılık'. İstenmezse topic boş bırakılmalı.",
 "Tema 4 T1-T6 genel fonksiyon kavramı/özellikleri (10. sınıf listesinde ayrı başlık yok) → topic boş.",
 "Karma satırlar (topic boş): Tema 1 T19 ÖTT, Tema 4 T25-T27, Tema 7 T7. Tema 3 T16-T17 ve Tema 5 T17 karma ama tek müfredat başlığı içinde kaldığı için o başlığa bağlandı.",
 "ÖTT (ÖSYM Tadında) testleri komşu konu satırına katılmadı, kitap sırasını korumak için ayrı '(ÖSYM Tadında)' satırı yapıldı (yalnız aynı konunun kesintisiz devamı olduğunda birleştirildi: Karesel T11-T13, Karekök T16, Rasyonel T18-T20, OBEB-OKEK T9-T10, Kombinasyon T10, Sayma T4, Asal çarpanlar T5)."
]
d["evidence"] = (d.get("evidence", "") + " | ALT KONU SATIRLARI: " + " ; ".join(f"{r[0]} = {r[3]}" for r in rows))
json.dump(d, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ok", len(rows), new_total)
