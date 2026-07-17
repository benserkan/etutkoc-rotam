"""AI deneme içe aktarma — deneme sonuç PDF'ini Gemini ile okuma.

FORMAT-BAĞIMSIZ okuma sözleşmesi: hangi yayınevi/okul yazılımı olursa olsun,
belgeden çıkarılacak ZORUNLU çekirdek "ders → konu → sonuç (doğru/yanlış/boş)"
üçlüsüdür; DC/ÖC, soru no, ders özet tablosu, puan/sıralama OPSİYONEL
zenginliktir (belge veriyorsa alınır). Belirli bir sayfa düzeni varsayılmaz.

Uydurma önleme (exam_import_service ile birlikte 3 katman):
  1. ÇİFT OKUMA — bu modül iki bağımsız Gemini çağrısı yapar; servis katmanı
     hücre-hücre karşılaştırıp uyuşmayanları "şüpheli" işaretler.
  2. Deterministik iç tutarlılık (servis katmanında).
  3. Kapalı-küme konu normalizasyonu (servis katmanında).

KVKK: belge öğrenci adı/okul/sıralama içerir → personal_data=True (ÜCRETLİ
anahtar, no-training). PDF bellekte işlenir; saklama kararı servis katmanında
(kanıt olarak ExamResult'a bağlanır).
"""
from __future__ import annotations

import logging
from typing import Any

from app.services import gemini
from app.services.ai_book_template import AIInvalidResponse  # reuse (hata eşlemesi korunur)

logger = logging.getLogger(__name__)

PDF_MIME = "application/pdf"

# 100-160 soru satırı + özet ~6-8K token; 2.5'in düşünme tokenı da bütçeden
# yediği için yüksek tutulur (yarım JSON = parse hatası).
_MAX_OUTPUT_TOKENS = 32768
_TIMEOUT = 150.0

_READ_PROMPT = """Sana bir DENEME SINAVI SONUÇ BELGESİ (PDF) veriyorum. Görevin belgedeki veriyi eksiksiz ve UYDURMADAN çıkarmak.

KURALLAR (çok önemli):
- Belge düzeni her yayınevinde farklıdır; düzeni değil İÇERİĞİ oku.
- ASLA satır uydurma: yalnız belgede gerçekten görünen soruları yaz. Okuyamadığın alanı null bırak.
- Konu adını belgede YAZILDIĞI GİBİ aynen kopyala (kısaltılmışsa kısaltılmış haliyle, örn. "Paragrafta Yardımcı Düşü…"). Düzeltme/uzatma yapma.
- Soru satırlarında ders, o sorunun ait olduğu ders başlığıdır (örn. Türkçe, Matematik, Fizik). Üst bölüm başlığı ile ders karışırsa en yakın ders başlığını kullan.
- Ders adını SADE yaz — bölüm kodu/eki EKLEME: "Edebiyat (EDE-SOS)" değil "Edebiyat"; "Tarih-1"/"Tarih SOS-2" değil "Tarih"; "Matematik AYT-MAT" değil "Matematik". Aynı ders belgede iki testte geçiyorsa da aynı sade adı kullan.
- Cevap sütunları: doğru cevap (DC/CA/anahtar) ve öğrenci cevabı (ÖC/verilen). Öğrenci cevabı hücresi BOŞSA student_answer=null yaz (bu "boş bırakmış" demektir).
- Sonuç: belge +/- benzeri işaret veriyorsa onu kullan ("dogru"/"yanlis"); öğrenci cevabı boşsa "bos". İşaret yoksa doğru cevap ile öğrenci cevabını karşılaştır. Hiçbiri çıkarılamıyorsa null.
- Belgede ders bazlı ÖZET tablosu (soru/doğru/yanlış/boş/net) varsa "subjects" içine aynen yaz; yoksa boş liste.
- Puan/sıralama/katılımcı bilgisi varsa "score_info" içine yaz; yoksa null.
- Sınav adı, tarihi, öğrencinin sınıfı (örn. "12-D" → 12) belgede varsa yaz.
- ÇOK ÖNEMLİ — BİRLEŞİK BELGELER: Bazı belgeler AYNI dosyada İKİ AYRI sınav
  oturumu içerir (örn. hem TYT hem AYT bölümleri; "TG" kitapçıkları). Belge
  bölüm başlıklarından hangi sorunun hangi oturuma ait olduğu anlaşılıyorsa her
  soruda "exam_part" alanına "tyt" veya "ayt" yaz (ders özetlerinde de "part").
  Belge TEK sınavsa exam_part=null bırak. Oturumu ASLA tahmin etme — yalnız
  belgede açıkça yazıyorsa etiketle.

YALNIZ şu JSON nesnesini döndür:
{
  "exam_title": "sınav adı" | null,
  "exam_date": "YYYY-MM-DD" | null,
  "grade_hint": 5-12 arası tam sayı | null,
  "type_hints": ["TYT","AYT","LGS","MSÜ","BRANŞ","OKUL", sınıf ibaresi vb. belgede geçen tür ipuçları],
  "subjects": [
    {"name": "ders adı", "part": "tyt"|"ayt"|null, "questions": int|null, "correct": int|null, "wrong": int|null, "blank": int|null, "net": float|null}
  ],
  "questions": [
    {"subject": "ders adı", "part": "tyt"|"ayt"|null, "no": int|null, "topic": "konu adı (aynen)", "correct_answer": "A-E"|null, "student_answer": "A-E"|null, "result": "dogru"|"yanlis"|"bos"|null}
  ],
  "score_info": {"score": float|null, "rank_overall": int|null, "participants": int|null, "extra": "diğer puan/sıralama notları"|null} | null
}"""


def read_exam_pdf(pdf_base64: str) -> dict[str, Any]:
    """Tek Gemini okuması → yapılandırılmış dict. AIInvalidResponse/AIServiceUnavailable fırlatır."""
    raw = gemini.generate(
        [
            gemini.inline_part(pdf_base64, PDF_MIME),
            gemini.text_part(_READ_PROMPT),
        ],
        personal_data=True,
        json_mode=True,
        timeout=_TIMEOUT,
        max_output_tokens=_MAX_OUTPUT_TOKENS,
    )
    data = gemini.extract_json(raw)
    return _normalize_read(data)


def read_exam_pdf_double(pdf_base64: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """ÇİFT bağımsız okuma (uydurma önleme katmanı 1) — PARALEL çalışır.

    Sıralı iki okuma büyük belgede 2×60-120 sn sürüp kullanıcıyı bekletiyordu;
    paralelde duvar süresi tek okumaya iner. Karşılaştırma servis katmanında.
    """
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(read_exam_pdf, pdf_base64)
        f2 = pool.submit(read_exam_pdf, pdf_base64)
        return f1.result(), f2.result()


def _clean_answer(v: Any) -> str | None:
    """Cevap hücresi: tek harf beklenir; gürültü (boş/'-'/None) → None."""
    if v is None:
        return None
    s = str(v).strip().upper()
    if not s or s in {"-", "—", "*", "BOŞ", "BOS", "NULL"}:
        return None
    return s[:8]


def _normalize_read(data: dict[str, Any]) -> dict[str, Any]:
    """Gemini çıktısını savunmacı normalize et (tip/alan varyasyonlarına dayanıklı)."""
    if not isinstance(data, dict):
        raise AIInvalidResponse("Belge okuması JSON nesnesi değil")

    out: dict[str, Any] = {
        "exam_title": (str(data.get("exam_title")).strip()[:200]
                       if data.get("exam_title") else None),
        "exam_date": (str(data.get("exam_date")).strip()[:10]
                      if data.get("exam_date") else None),
        "grade_hint": None,
        "type_hints": [],
        "subjects": [],
        "questions": [],
        "score_info": data.get("score_info") if isinstance(data.get("score_info"), dict) else None,
    }
    gh = data.get("grade_hint")
    if isinstance(gh, (int, float)) and 1 <= int(gh) <= 12:
        out["grade_hint"] = int(gh)
    th = data.get("type_hints")
    if isinstance(th, list):
        out["type_hints"] = [str(x).strip() for x in th if str(x).strip()][:10]

    def _part(v: Any) -> str | None:
        p = str(v).strip().lower() if v else None
        return p if p in ("tyt", "ayt") else None

    subs = data.get("subjects")
    if isinstance(subs, list):
        for s in subs:
            if not isinstance(s, dict) or not str(s.get("name") or "").strip():
                continue
            def _i(k: str) -> int | None:
                v = s.get(k)
                try:
                    return int(v) if v is not None else None
                except (TypeError, ValueError):
                    return None
            net = s.get("net")
            try:
                # TR belgeleri ondalıkta virgül kullanır ("14,67")
                if isinstance(net, str):
                    net = net.replace(",", ".")
                net = round(float(net), 2) if net is not None else None
            except (TypeError, ValueError):
                net = None
            out["subjects"].append({
                "name": str(s["name"]).strip()[:120],
                "part": _part(s.get("part")),
                "questions": _i("questions"),
                "correct": _i("correct"),
                "wrong": _i("wrong"),
                "blank": _i("blank"),
                "net": net,
            })

    qs = data.get("questions")
    if isinstance(qs, list):
        for q in qs:
            if not isinstance(q, dict):
                continue
            subject = str(q.get("subject") or "").strip()[:120]
            topic = str(q.get("topic") or "").strip()[:200]
            if not subject and not topic:
                continue  # tamamen boş satır — uydurma/gürültü
            no = q.get("no")
            try:
                no = int(no) if no is not None else None
            except (TypeError, ValueError):
                no = None
            res = q.get("result")
            res = str(res).strip().lower() if res else None
            if res not in ("dogru", "yanlis", "bos"):
                res = None
            out["questions"].append({
                "subject": subject,
                "part": _part(q.get("part")),
                "no": no,
                "topic": topic,
                "correct_answer": _clean_answer(q.get("correct_answer")),
                "student_answer": _clean_answer(q.get("student_answer")),
                "result": res,
            })

    if not out["questions"]:
        raise AIInvalidResponse(
            "Belgede soru-konu satırı bulunamadı. Bu bir deneme sonuç/analiz "
            "belgesi mi? (Konu analizi sayfası olmayan belgeler içe aktarılamaz.)"
        )
    return out
