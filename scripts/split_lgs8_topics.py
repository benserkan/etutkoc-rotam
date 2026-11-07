"""LGS 8 Mat + Fen + Türkçe + İnkılap + Din — ünite "(Karma)" bağlarını alt konulara taşı (2026-11-07).

Bağlam (Neslihan Hoca saha bulgusu): 8. sınıf LGS müfredatı yalnız ünite adlarından
oluşuyordu ("Çarpanlar ve Katlar"); yayınevleri alt konu basıyor ("EBOB-EKOK",
"Bilimsel Gösterim", "Pisagor Bağıntısı"...). Seed artık üniteyi üst başlık, alt
konuları seçilebilir konu yapıyor; eski düz konu aynı id ile "<ad> (Karma)" oldu.

Bu betik mevcut veriyi taşır:
  - kitap bölümleri + katalog şablon bölümleri: "(Karma)" konuya bağlı olup adı
    TEK bir alt konuyu açıkça söyleyen bölüm o alt konuya,
  - deneme soruları (elle düzeltilmemiş, LGS): aynı kural, karne etiketinden.

Belirsizde DOKUNMAZ: ünitenin tam adını taşıyan, birden çok alt konu anan ya da
hiçbirini anmayan etiket "(Karma)"da kalır. Dry-run varsayılan; --apply yazar.
İdempotent: ikinci koşu 0 değişiklik.

    python -m scripts.split_lgs8_topics            # rapor
    python -m scripts.split_lgs8_topics --apply    # uygula
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

from app.database import SessionLocal
from app.models import BookSection, BookTemplateSection, CurriculumModel, Subject, Topic, User
from app.models.exam_result import ExamResult, ExamResultQuestion
from app.services.curriculum_mapping import _label_key, _topic_key, normalize
from app.services.exam_import_service import rebuild_subject_nets

# karma adı → [(alt konu, anahtar sözcükler, dışlayan sözcükler)]. Sözcükler
# eşleştirme anahtarında (Türkçe sadeleştirilmiş, bağlaçsız) sözcük BAŞI olarak aranır.
RULES: dict[str, list[tuple[str, tuple[str, ...], tuple[str, ...]]]] = {
    # ---------------- Matematik ----------------
    "Çarpanlar ve Katlar (Karma)": [
        ("Çarpanlar ve Asal Çarpanlara Ayırma", ("carpan",), ("aralarinda", "ebob", "ekok")),
        ("EBOB ve EKOK", ("ebob", "ekok", "en buyuk ortak", "en kucuk ortak"),
         ("problem", "aralarinda")),
        ("EBOB ve EKOK Problemleri", ("ebob ekok problem", "ekok problem", "ebob problem"), ()),
        ("Aralarında Asal Sayılar", ("aralarinda",), ("ebob", "ekok")),
    ],
    "Üslü İfadeler (Karma)": [
        ("Tam Sayıların Tam Sayı Kuvvetleri", ("kuvvet", "negatif"), ("10",)),
        ("Üslü İfadelerle İşlemler", ("carpma", "bolme", "islem", "ussun", "kural"), ()),
        ("Ondalık Gösterimlerin Çözümlenmesi", ("cozumle", "10 un", "10un"),
         ("bilimsel", "cok buyuk")),
        ("Bilimsel Gösterim (Çok Büyük ve Çok Küçük Sayılar)",
         ("bilimsel", "cok buyuk", "cok kucuk"), ("10 un", "10un")),
    ],
    "Kareköklü İfadeler (Karma)": [
        ("Tam Kare Sayılar ve Karekök", ("tam kare", "tamkare"), ("olmayan",)),
        ("Karekök Tahmini (Yaklaşık Değer)", ("tahmin", "yaklasik", "olmayan"),
         ("tam kare pozitif", "tam kare dogal")),
        ("Kareköklü İfadelerle İşlemler",
         ("toplama", "cikarma", "carpma", "bolme", "islem", "disina", "icine",
          "dogal sayi yap", "siralama"), ()),
        ("Ondalık Gösterimlerin Karekökü ve Gerçek Sayılar",
         ("ondalik", "gercek"), ()),
    ],
    "Veri Analizi (Karma)": [
        ("Grafik Okuma ve Yorumlama (Çizgi, Sütun, Daire)",
         ("cizgi", "sutun", "daire", "yorumla", "grafik okuma"), ("donusum",)),
        ("Grafikler Arası Dönüşüm", ("donusum",), ()),
    ],
    "Basit Olayların Olasılığı (Karma)": [
        ("Olası Durumlar", ("olasi durum", "temel kavram"), ("olma olasil",)),
        ("Basit Olayların Olma Olasılığı",
         ("olma olasil", "olasilik hesab", "olasilik deger"), ()),
    ],
    "Cebirsel İfadeler ve Özdeşlikler (Karma)": [
        ("Cebirsel İfadelerle Çarpma", ("carpim", "carpma"), ("carpanlar",)),
        ("Özdeşlikler", ("ozdeslik", "tam kare", "iki kare"), ("carpanlar",)),
        ("Cebirsel İfadeleri Çarpanlarına Ayırma", ("carpanlar",), ()),
    ],
    "Doğrusal Denklemler (Karma)": [
        ("Birinci Dereceden Bir Bilinmeyenli Denklemler",
         ("bilinmeyenli denklem", "bir bilinmeyen"), ("koordinat", "esitsizlik")),
        ("Koordinat Sistemi", ("koordinat", "sirali ikili"), ("dogrusal", "bilinmeyen")),
        ("Doğrusal İlişkiler ve Grafikleri",
         ("dogrusal iliski", "grafi", "eksenlere", "orijin", "kesen dogru",
          "gercek hayat", "iki degiskenin"), ("egim", "koordinat")),
        ("Eğim", ("egim",), ()),
    ],
    "Eşitsizlikler (Karma)": [
        ("Eşitsizliklerin Sayı Doğrusunda Gösterimi",
         ("sayi dogrusu", "esitsizlik kavram", "esitsizlik cumle"), ()),
        ("Eşitsizlik Çözme", ("cozme", "cozum"), ()),
    ],
    "Üçgenler (Karma)": [
        ("Kenarortay, Açıortay ve Yükseklik",
         ("kenarortay", "aciortay", "yukseklik", "yardimci eleman"), ()),
        ("Üçgen Eşitsizliği ve Açı-Kenar Bağıntısı",
         ("ucgen esitsizl", "aci kenar", "kenar aci", "kenarlari arasi"), ("cizim",)),
        ("Üçgen Çizimi", ("cizim", "cizme"), ("bagint", "iliski")),
        ("Pisagor Bağıntısı", ("pisagor",), ()),
    ],
    "Eşlik ve Benzerlik (Karma)": [
        ("Eşlik", ("eslik",), ("benzer",)),
        ("Benzerlik", ("benzer",), ("eslik", "es benzer")),
    ],
    "Dönüşüm Geometrisi (Karma)": [
        ("Öteleme", ("oteleme",), ("yansima",)),
        ("Yansıma", ("yansima",), ("oteleme",)),
        ("Ötelemeli Yansıma", ("otelemeli", "ardisik"), ()),
    ],
    "Geometrik Cisimler (Karma)": [
        ("Dik Prizmalar", ("prizma",), ("silindir",)),
        ("Dik Dairesel Silindir (Alan ve Hacim)", ("silindir",), ("prizma",)),
        ("Dik Piramit", ("piramit",), ("koni",)),
        ("Dik Dairesel Koni", ("koni",), ("piramit",)),
    ],
    # ---------------- Fen Bilimleri ----------------
    "Mevsimler ve İklim (Karma)": [
        ("Mevsimlerin Oluşumu", ("mevsim", "aydinlanan", "gunes isin"), ("iklim",)),
        ("İklim ve Hava Hareketleri", ("iklim", "hava hareket", "hava olay"), ("mevsim",)),
    ],
    "DNA ve Genetik Kod (Karma)": [
        ("DNA'nın Yapısı ve Eşlenmesi",
         ("nukleotid", "eslen", "kendini esle", "kromozom"), ("kalitim",)),
        ("Kalıtım (Çaprazlamalar)", ("kalitim", "caprazlama", "karakter"), ()),
        ("Mutasyon ve Modifikasyon", ("mutasyon", "modifikasyon"), ("adaptasyon",)),
        ("Adaptasyon (Çevreye Uyum)", ("adaptasyon", "cevreye uyum"), ("mutasyon",)),
        ("Biyoteknoloji", ("biyoteknoloji", "genetik muhendis"), ()),
    ],
    "Basınç (Karma)": [
        ("Katı Basıncı", ("kati basinc",), ()),
        ("Sıvı Basıncı", ("sivi",), ("gaz",)),
        ("Gaz Basıncı ve Basıncın Uygulamaları",
         ("gaz", "pascal", "acik hava", "gunluk hayat", "gunluk yasam"), ("sivi",)),
    ],
    "Madde ve Endüstri (Karma)": [
        ("Periyodik Sistem", ("periyodik", "element"), ()),
        ("Fiziksel ve Kimyasal Değişimler", ("fiziksel",), ("tepkime",)),
        ("Kimyasal Tepkimeler", ("tepkime",), ("fiziksel",)),
        ("Asitler ve Bazlar", ("asit", "baz"), ()),
        ("Maddenin Isı ile Etkileşimi (Hâl Değişimi)",
         ("isi", "hal degisim", "isinma", "sogum"), ("endustri",)),
        ("Türkiye'de Kimya Endüstrisi", ("endustri",), ("isi",)),
    ],
    "Basit Makineler (Karma)": [
        ("Kaldıraçlar", ("kaldirac",), ()),
        ("Makaralar", ("makara",), ()),
        ("Eğik Düzlem ve Çıkrık", ("egik", "cikrik"), ("disli", "kasnak")),
        ("Dişli Çark, Kasnak, Vida ve Bileşik Makineler",
         ("disli", "kasnak", "vida", "bilesik"), ()),
    ],
    "Enerji Dönüşümleri ve Çevre Bilimi (Karma)": [
        ("Besin Zinciri ve Enerji Akışı", ("besin zinciri", "enerji akis", "besin ag"), ()),
        ("Fotosentez", ("fotosentez",), ("solunum",)),
        ("Solunum", ("solunum",), ("fotosentez",)),
        ("Madde Döngüleri ve Çevre Sorunları", ("dongu", "cevre sorun"), ()),
        ("Sürdürülebilir Kalkınma", ("surdurulebilir",), ()),
    ],
    "Elektrik Yükleri ve Elektrik Enerjisi (Karma)": [
        ("Elektrik Yükleri ve Elektriklenme", ("elektriklenme",),
         ("topraklam", "yuklu cisim", "donusum")),
        ("Elektrik Yüklü Cisimler ve Topraklama",
         ("yuklu cisim", "topraklam", "elektroskop"), ("donusum", "elektriklenme")),
        ("Elektrik Enerjisinin Dönüşümü", ("donusum",), ()),
    ],
    # ---------------- Türkçe (düz kardeş konular; kaynak konu Karma değil) ----------------
    "Fiilimsiler": [
        ("İsim-Fiil", ("isim fiil", "ad eylem"), ("sifat fiil", "zarf fiil", "ortac", "ulac")),
        ("Sıfat-Fiil", ("sifat fiil", "ortac"), ("isim fiil", "zarf fiil", "ulac")),
        ("Zarf-Fiil", ("zarf fiil", "ulac", "bag fiil"), ("isim fiil", "sifat fiil", "ortac")),
    ],
    "Sözcükte Anlam": [
        ("Sözcükler Arası Anlam İlişkileri",
         ("anlam iliski", "es anlam", "zit anlam", "es zit", "yakin anlam", "es sesli"), ()),
    ],
    "Metin Türleri": [
        ("Hikâye Unsurları ve Anlatıcı", ("hikaye unsur", "anlatici", "olay orgu"), ("siir",)),
        ("Şiirde Tema ve Duygu", ("siir",), ("hikaye",)),
    ],
    "Paragrafta Anlam": [
        ("Hikâye Unsurları ve Anlatıcı", ("hikaye unsur", "anlatici"), ("siir",)),
        ("Şiirde Tema ve Duygu", ("siir",), ("hikaye",)),
    ],
    # ---------------- T.C. İnkılap Tarihi ----------------
    "Bir Kahraman Doğuyor (Karma)": [
        ("Avrupa'daki Gelişmeler ve Osmanlı Devleti", ("avrupa", "uyanan"), ()),
        ("Mustafa Kemal'in Çocukluğu ve Öğrenim Hayatı", ("cocukluk", "ogrenim", "ailesi"),
         ("askerlik", "fikir")),
        ("Mustafa Kemal'in Askerlik Hayatı", ("askerlik",), ("ogrenim", "fikir")),
        ("Mustafa Kemal'in Fikir Hayatı", ("fikir",), ("askerlik", "ogrenim")),
    ],
    "Millî Uyanış: Bağımsızlık Yolunda Atılan Adımlar (Karma)": [
        ("Birinci Dünya Savaşı ve Osmanlı Devleti", ("dunya savas", "son savasi"), ()),
        ("Mondros Ateşkes Antlaşması ve İşgaller", ("mondros", "isgal"), ("cemiyet", "kuva")),
        ("Cemiyetler ve Kuvâ-yı Millîye", ("cemiyet", "kuva"), ("mondros",)),
        ("Millî Mücadele Hazırlık Dönemi (Kongreler)",
         ("hazirlik", "kongre", "genelge", "samsun"), ("misak",)),
        ("Misak-ı Millî ve TBMM'nin Açılması", ("misak", "mebusan", "acilis"), ("ayaklanma",)),
        ("TBMM'ye Karşı Ayaklanmalar", ("ayaklanma", "isyan"), ()),
        ("Sevr Antlaşması", ("sevr",), ()),
    ],
    "Millî Bir Destan: Ya İstiklal Ya Ölüm! (Karma)": [
        ("Doğu ve Güney Cepheleri", ("dogu", "guney"), ("bati",)),
        ("Batı Cephesi (İnönü Savaşları)", ("bati cephe", "inonu"), ("sakarya", "dogu")),
        ("Maarif Kongresi ve Tekâlif-i Millîye", ("maarif", "tekalif"), ()),
        ("Sakarya'dan Büyük Taarruz'a ve Mudanya", ("sakarya", "buyuk taarruz", "mudanya"), ()),
        ("Lozan Barış Antlaşması", ("lozan",), ()),
        ("Millî Mücadele'nin Sanat ve Edebiyata Yansımaları", ("sanat", "edebiyat"), ()),
    ],
    "Atatürkçülük ve Çağdaşlaşan Türkiye (Karma)": [
        ("Atatürk İlkeleri ve Temel Esaslar", ("ilke", "temel esas"), ("alan",)),
        ("Siyasi Alanda İnkılaplar", ("siyasi", "siyasal"), ("hukuk",)),
        ("Hukuk Alanında İnkılaplar", ("hukuk",), ("siyasi",)),
        ("Eğitim ve Kültür Alanında İnkılaplar", ("egitim", "kultur"), ()),
        ("Toplumsal Alanda İnkılaplar", ("toplumsal",), ()),
        ("Ekonomik Alanda İnkılaplar", ("ekonomi",), ()),
        ("Sağlık Alanındaki Gelişmeler", ("saglik",), ()),
    ],
    "Demokratikleşme Çabaları (Karma)": [
        ("Demokratikleşme Yolunda Atılan Adımlar (Çok Partili Hayat Denemeleri)",
         ("demokratiklesme yolunda", "demokrasi yolunda", "cok partili", "firka"),
         ("tehdit", "suikast")),
        ("Cumhuriyete Yönelik Tehditler (Suikast ve İsyanlar)",
         ("tehdit", "suikast", "seyh sait", "menemen"), ()),
    ],
    "Atatürk Dönemi Türk Dış Politikası (Karma)": [
        ("Dış Politikanın Temel İlkeleri ve Amaçları", ("temel ilke", "amac"), ("gelisme",)),
        ("Dış Politikada Gelişmeler",
         ("gelisme", "bogaz", "musul", "mubadele", "balkan antant", "sadabat"),
         ("temel ilke", "hatay")),
        ("Hatay'ın Anavatana Katılması", ("hatay",), ()),
    ],
    "Atatürk'ün Ölümü ve Sonrası (Karma)": [
        ("Atatürk'ün Ölümü ve Eserleri", ("olum", "eser"), ("dunya", "partili")),
        ("II. Dünya Savaşı ve Türkiye", ("dunya savas", "sarsilan dunya"), ()),
        ("Çok Partili Hayata Geçiş", ("cok partili",), ()),
    ],
    # ---------------- Din Kültürü ----------------
    "Kader İnancı (Karma)": [
        ("Kader ve Kaza İnancı", ("kaza",), ("irade", "kavram")),
        ("İnsan İradesi ve Kader", ("irade",), ()),
        ("Kaderle İlgili Kavramlar", ("kavram",), ()),
    ],
    "Zekât, Hac ve Kurban İbadeti (Karma)": [
        ("İslam'ın Paylaşma ve Yardımlaşmaya Verdiği Önem", ("paylasma", "yardimlasma"), ()),
        ("Zekât ve Sadaka", ("zekat", "sadaka"), ("paylasma", "hac", "kurban")),
        ("Hac ve Kurban", ("hac", "kurban", "umre"), ("zekat",)),
    ],
    "Din ve Hayat (Karma)": [
        ("Din, Birey ve Toplum", ("birey", "toplum"), ()),
        ("Dinin Temel Gayesi", ("gaye", "amac"), ()),
    ],
    "Hz. Muhammed'in Örnekliği (Karma)": [
        ("Hz. Muhammed'in Doğruluğu, Merhameti ve Affediciliği",
         ("dogrulu", "guvenilir", "merhamet", "affedici"), ()),
        ("Hz. Muhammed'in İstişareye ve İnsana Değer Vermesi",
         ("istisare", "deger verme"), ()),
        ("Hz. Muhammed'in Hakkı Gözetmesi, Cesareti ve Kararlılığı",
         ("hakki", "cesaret", "kararlilig"), ()),
    ],
    "Kur'an-ı Kerim ve Özellikleri (Karma)": [
        ("İslam Dininin Temel Kaynakları", ("kaynak",), ()),
        ("Kur'an-ı Kerim'in Ana Konuları", ("ana konu",), ()),
        ("Kur'an-ı Kerim'in Temel Özellikleri", ("temel ozellik",), ()),
    ],
}


_SEPS = (" — ", " – ", " / ", ": ")
_GENERAL = ("tarama", "tekrar", "deneme", "degerlendirme", "unite sonu", "genel")


def _rule_hit(key: str, rules) -> str | None:
    hits = [
        name for name, words, excl in rules
        if any(f" {w}" in key for w in words) and not any(f" {x}" in key for x in excl)
    ]
    return hits[0] if len(hits) == 1 else None


def split_target(label: str | None, karma_name: str) -> str | None:
    """(Karma) bağlı etiketin taşınacağı alt konu adı; belirsizde None."""
    rules = RULES.get(karma_name)
    if not rules or not label:
        return None
    key = f" {_label_key(label)} "
    if any(f" {w}" in f" {normalize(label)} " for w in _GENERAL):
        return None  # tarama / tekrar / deneme → ünite geneli
    exact = [n for n, _, _ in rules if _topic_key(n) == key.strip()]
    if exact:
        return exact[0]
    base_key = _topic_key(karma_name.replace("(Karma)", "").strip())
    base = base_key.split()
    toks = set(key.split())
    if base and all(b in toks for b in base):
        # "DNA ve Genetik Kod — Kalıtım": ünite adı + ayraç + alt konu → kuyruğa bak
        for sep in _SEPS:
            if sep in label:
                tail = label.rsplit(sep, 1)[1]
                tkey = _label_key(tail)
                if tkey and tkey != base_key:
                    return _rule_hit(f" {tkey} ", rules)
        return None  # ünitenin tam adı → ünite geneli
    return _rule_hit(key, rules)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    db = SessionLocal()

    subjects = (
        db.query(Subject)
        .filter(Subject.is_builtin.is_(True), Subject.teacher_id.is_(None),
                Subject.curriculum_model == CurriculumModel.LGS,
                Subject.name.in_(["Matematik", "Fen Bilimleri", "Türkçe",
                                  "T.C. İnkılap Tarihi ve Atatürkçülük",
                                  "Din Kültürü ve Ahlak Bilgisi"]))
        .all()
    )
    topics = (
        db.query(Topic)
        .filter(Topic.subject_id.in_([s.id for s in subjects]),
                Topic.is_builtin.is_(True), Topic.grade_level == 8)
        .all()
    )
    karma = {t.id: t for t in topics if t.name in RULES}
    if not karma:
        print("(Karma) konular yok — önce seed çalışmalı (scripts.seed).")
        return 1
    # hedef: kaynakla AYNI üst başlık altındaki konu (Türkçe'de düz kardeş: parent None)
    child_by = {(t.subject_id, t.parent_id, t.name): t for t in topics}

    def target(label: str | None, cur: Topic) -> Topic | None:
        name = split_target(label, cur.name)
        return child_by.get((cur.subject_id, cur.parent_id, name)) if name else None

    changes: Counter[str] = Counter()
    report: Counter[tuple[str, str, str, str]] = Counter()

    for model, kind in ((BookSection, "bolum"), (BookTemplateSection, "sablon")):
        for sec in db.query(model).filter(model.topic_id.in_(list(karma))).all():
            cur = karma[sec.topic_id]
            tgt = target(sec.label, cur)
            if tgt is not None:
                report[(kind, sec.label or "", cur.name, tgt.name)] += 1
                changes[kind] += 1
                if args.apply:
                    sec.topic_id = tgt.id

    touched: set[int] = set()
    qs = (
        db.query(ExamResultQuestion)
        .filter(ExamResultQuestion.topic_id.in_(list(karma)),
                ExamResultQuestion.manually_edited.is_(False))
        .all()
    )
    for q in qs:
        cur = karma[q.topic_id]
        tgt = target(q.topic_label_raw, cur)
        if tgt is not None:
            report[("soru", q.topic_label_raw or "", cur.name, tgt.name)] += 1
            changes["soru"] += 1
            touched.add(q.exam_result_id)
            if args.apply:
                q.topic_id = tgt.id

    for (kind, label, old, new), n in sorted(report.items()):
        print(f"[{kind}] {label[:80]}  |  {old}  ->  {new}  (x{n})")
    print("\nÖZET:", dict(changes), "| etkilenen deneme:", len(touched))
    if args.apply:
        db.flush()
        for ex in db.query(ExamResult).filter(ExamResult.id.in_(touched)).all():
            st = db.get(User, ex.student_id)
            if st is not None:
                rebuild_subject_nets(db, ex, st)
        db.commit()
        print("UYGULANDI.")
    else:
        db.rollback()
        print("(dry-run — yazmak için --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
