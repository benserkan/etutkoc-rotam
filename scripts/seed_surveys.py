# -*- coding: utf-8 -*-
"""Anket kataloğu — 11 anketi DB'ye **idempotent** yükle (Faz 1, 2026-06-11).

Kullanım:
    python scripts/seed_surveys.py
    python scripts/seed_surveys.py --reset   # seed'leri siler+yeniden yazar
                                             # (DİKKAT: süper admin edit'lerini siler;
                                             #  atamalar CASCADE ile silinir!)

Idempotent: mevcut `code` varsa ATLAR — süper adminin sonradan yaptığı
düzenlemeler korunur (whatsapp_templates seed deseni).

TELİF NOTU (kullanıcı kararı 2026-06-11): Tüm madde metinleri ETÜTKOÇ'a
özgüdür. Teorik çerçeveler (çoklu zeka alanları, RIASEC tipleri, VAK stilleri,
yaşam çarkı, SWOT) telifsizdir. Mesleki İlgi anketi O*NET Interest Profiler'dan
(ABD Çalışma Bakanlığı, CC BY 4.0) esinlenen özgün uyarlamadır — atıf
source_attribution alanında taşınır. MBTI/Kolb/VARK gibi lisanslı araçlar
KULLANILMAZ.
"""
from __future__ import annotations

import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal
from app.models.survey import (
    QTYPE_LIKERT5,
    QTYPE_OPEN,
    QTYPE_SLIDER10,
    SCORING_DIMENSIONS,
    SCORING_QUALITATIVE,
    SCORING_WHEEL,
    SURVEY_CATEGORY_KARIYER,
    SURVEY_CATEGORY_MOTIVASYON,
    SURVEY_CATEGORY_SINAV,
    SURVEY_CATEGORY_TANIMA,
    SurveyQuestion,
    SurveyTemplate,
)


def D(key, label, desc, high="", low="", high_is_good=True):
    return {
        "key": key, "label": label, "description": desc,
        "high_text": high, "low_text": low, "high_is_good": high_is_good,
    }


def L(dim, text):
    """likert5 madde."""
    return {"qtype": QTYPE_LIKERT5, "dimension_key": dim, "text": text}


def S(dim, text):
    """slider10 madde (yaşam çarkı dilimi)."""
    return {"qtype": QTYPE_SLIDER10, "dimension_key": dim, "text": text}


def O(text, dim=None):
    """açık uç madde."""
    return {"qtype": QTYPE_OPEN, "dimension_key": dim, "text": text}


GENEL_NOT = (
    "Sonuçlar öğrencinin kendi değerlendirmesine dayanır; kesin yargı değil, "
    "koçluk görüşmesinde konuşulacak ipuçlarıdır. Yüksek/düşük çıkan boyutları "
    "öğrenciyle birlikte yorumlayın."
)


SEED_SURVEYS: list[dict] = [
    # =========================================================================
    # 1. ÇOKLU ZEKA — Tanıma
    # =========================================================================
    {
        "code": "coklu-zeka",
        "title": "Çoklu Zeka Envanteri",
        "category": SURVEY_CATEGORY_TANIMA,
        "scoring_type": SCORING_DIMENSIONS,
        "estimated_minutes": 10,
        "sort_order": 10,
        "description": (
            "Öğrencinin 8 zeka alanındaki baskın yönlerini gösterir; çalışma "
            "yöntemi ve kaynak seçimini kişiselleştirmek için kullanılır."
        ),
        "report_note": GENEL_NOT,
        "dimensions": [
            D("sozel", "Sözel-Dilsel",
              "Dil, okuma, yazma ve sözle ifade gücü.",
              high="Okuyarak/anlatarak öğrenme, özet çıkarma ve sözel dersler güçlü alan."),
            D("mantik", "Mantıksal-Matematiksel",
              "Sayılar, mantık yürütme ve problem çözme.",
              high="Sayısal dersler ve adım adım çözüm stratejileri verimli olur."),
            D("gorsel", "Görsel-Uzamsal",
              "Şekil, şema ve görsellerle düşünme.",
              high="Zihin haritası, şema ve video anlatım en verimli araçlar."),
            D("bedensel", "Bedensel-Kinestetik",
              "Yaparak-dokunarak öğrenme ve beden kontrolü.",
              high="Deney, uygulama ve hareketli mola düzeni öğrenmeyi güçlendirir."),
            D("muzik", "Müziksel-Ritmik",
              "Ses, ritim ve melodi duyarlılığı.",
              high="Ritim/tekerleme ile ezber ve düzenli ses ortamı işe yarar."),
            D("sosyal", "Sosyal (Kişilerarası)",
              "İnsanları anlama ve iletişim.",
              high="Grup çalışması ve birine anlatarak öğrenme çok verimli olur."),
            D("icsel", "İçsel (Kişiye Dönük)",
              "Kendini tanıma ve bağımsız çalışma.",
              high="Bireysel hedef takibi ve sessiz bireysel çalışma uygun."),
            D("doga", "Doğa",
              "Doğayı gözlemleme ve sınıflandırma.",
              high="Sınıflandırma/karşılaştırma ve gerçek yaşam örnekleri etkili."),
        ],
        "questions": [
            L("sozel", "Okuduğum bir hikâyeyi ya da konuyu kendi cümlelerimle kolayca anlatırım."),
            L("sozel", "Yeni kelimeler öğrenmek ve onları kullanmak hoşuma gider."),
            L("sozel", "Yazı yazarken (kompozisyon, günlük, mesaj) kendimi rahat ifade ederim."),
            L("sozel", "Kelime oyunları, bilmece ve bulmacalar ilgimi çeker."),
            L("mantik", "Sayılarla uğraşmak, işlem yapmak bana zor gelmez."),
            L("mantik", "Bir sorunun çözümüne adım adım, mantık yürüterek ulaşmayı severim."),
            L("mantik", "Olaylar arasında neden-sonuç ilişkisi kurmak bana doğal gelir."),
            L("mantik", "Strateji ve zekâ oyunlarında (satranç, sudoku vb.) iyiyimdir."),
            L("gorsel", "Bir konu şekil, şema veya çizimle anlatıldığında daha iyi anlarım."),
            L("gorsel", "Harita, kroki okuma ve yön bulma konusunda iyiyimdir."),
            L("gorsel", "Hayal gücümde resimler ve sahneler canlandırmak benim için kolaydır."),
            L("gorsel", "Çizim yapmayı, tasarlamayı veya görsel düzenlemeyi severim."),
            L("bedensel", "Bir şeyi yaparak ve dokunarak öğrendiğimde daha iyi kavrarım."),
            L("bedensel", "Spor, dans veya el işi gibi beden kullanılan etkinliklerde başarılıyımdır."),
            L("bedensel", "Uzun süre hareketsiz oturmak bana zor gelir."),
            L("bedensel", "El becerisi gerektiren işlerde (tamir, maket, el sanatı) iyiyimdir."),
            L("muzik", "Bir şarkıyı birkaç kez dinleyince melodisini kolayca hatırlarım."),
            L("muzik", "Ritim tutmak ya da müzik dinlemek bana iyi gelir."),
            L("muzik", "Seslerin tonundaki ve ritmindeki değişiklikleri kolay fark ederim."),
            L("muzik", "Şarkı söylemek ya da bir enstrüman çalmak ilgimi çeker."),
            L("sosyal", "Arkadaşlarımın ne hissettiğini yüzlerinden kolayca anlarım."),
            L("sosyal", "Grup çalışmalarında insanları bir araya getirmekte iyiyimdir."),
            L("sosyal", "Arkadaşlarım dertlerini anlatmak için genellikle beni seçer."),
            L("sosyal", "Yeni insanlarla tanışmak ve iletişim kurmak bana kolay gelir."),
            L("icsel", "Güçlü ve zayıf yönlerimin farkındayımdır."),
            L("icsel", "Karar vermeden önce kendi başıma düşünmeye ihtiyaç duyarım."),
            L("icsel", "Duygularımın nedenini anlamaya çalışırım."),
            L("icsel", "Tek başıma çalışmak çoğu zaman bana daha verimli gelir."),
            L("doga", "Hayvanlar, bitkiler ve doğa olayları ilgimi çeker."),
            L("doga", "Doğada vakit geçirmek bana iyi gelir."),
            L("doga", "Nesneleri özelliklerine göre sınıflandırmayı, koleksiyon yapmayı severim."),
            L("doga", "Çevre sorunlarına ve doğanın korunmasına duyarlıyımdır."),
        ],
    },
    # =========================================================================
    # 2. ÖĞRENME STİLLERİ — Tanıma
    # =========================================================================
    {
        "code": "ogrenme-stilleri",
        "title": "Öğrenme Stilleri Anketi",
        "category": SURVEY_CATEGORY_TANIMA,
        "scoring_type": SCORING_DIMENSIONS,
        "estimated_minutes": 6,
        "sort_order": 20,
        "description": (
            "Görsel / işitsel / uygulamalı öğrenme tercihini gösterir; kaynak "
            "tipi (video, anlatım, soru çözümü) ve çalışma yöntemi seçiminde kullanılır."
        ),
        "report_note": GENEL_NOT,
        "dimensions": [
            D("gorsel", "Görsel",
              "Görerek, okuyarak, şema ve renkle öğrenme.",
              high="Şema/zihin haritası, renkli işaretleme ve video anlatım önerin."),
            D("isitsel", "İşitsel",
              "Dinleyerek ve sesli anlatarak öğrenme.",
              high="Sesli tekrar, anlatarak çalışma ve sessiz ortam önerin."),
            D("kinestetik", "Uygulamalı (Kinestetik)",
              "Yaparak, yazarak, deneyerek öğrenme.",
              high="Bol soru çözümü, not tutma ve kısa hareketli molalar önerin."),
        ],
        "questions": [
            L("gorsel", "Öğretmenin tahtaya yazdıklarını ve çizdiklerini görmeden konuyu tam anlayamam."),
            L("gorsel", "Renkli kalemle işaretlediğim notları daha iyi hatırlarım."),
            L("gorsel", "Konu anlatımlı video ve şemalar benim için en verimli kaynaklardır."),
            L("gorsel", "Bir kelimenin nasıl yazıldığını gözümde canlandırarak hatırlarım."),
            L("gorsel", "Bilginin kitapta sayfanın neresinde olduğunu hatırlayarak bulurum."),
            L("gorsel", "Ders çalışırken şema, tablo veya zihin haritası çıkarmak işimi kolaylaştırır."),
            L("isitsel", "Öğretmenin anlattığını dinlediğimde, kendim okuduğumdan daha iyi anlarım."),
            L("isitsel", "Konuyu birine sesli anlattığımda daha kalıcı öğrenirim."),
            L("isitsel", "Sesli okumak, içimden okumaktan daha verimli olur."),
            L("isitsel", "Duyduğum bir açıklamayı uzun süre hatırlarım."),
            L("isitsel", "Gürültülü ortamda dikkatim çok çabuk dağılır."),
            L("isitsel", "Tekerleme veya şarkı gibi ezgili yollarla ezberlemek bana kolay gelir."),
            L("kinestetik", "Deney, uygulama ve proje yaparak öğrendiğim konular aklımda kalır."),
            L("kinestetik", "Çalışırken ara ara hareket etmek (yürümek, ayakta tekrar) bana iyi gelir."),
            L("kinestetik", "Not tutmak ve yazmak öğrenmemi güçlendirir."),
            L("kinestetik", "Uzun süre oturup yalnızca dinlemek beni sıkar."),
            L("kinestetik", "Bir şeyi anlamak için onu elimle yapmayı ya da denemeyi tercih ederim."),
            L("kinestetik", "Örnek soru çözmeden bir konuyu öğrendiğimden emin olamam."),
        ],
    },
    # =========================================================================
    # 3. YAŞAM ÇARKI — Tanıma
    # =========================================================================
    {
        "code": "yasam-carki",
        "title": "Yaşam Çarkı",
        "category": SURVEY_CATEGORY_TANIMA,
        "scoring_type": SCORING_WHEEL,
        "estimated_minutes": 5,
        "sort_order": 30,
        "description": (
            "Öğrencinin 8 yaşam alanındaki memnuniyet dengesini tek bakışta "
            "gösterir; ilk görüşmede öncelikli konuşma alanını belirler."
        ),
        "report_note": (
            "Düşük puanlı dilimler koçluk görüşmesinin doğal gündemidir. "
            "Açık uç cevapları öğrencinin kendi değişim isteğini gösterir — "
            "hedefi oradan kurun."
        ),
        "dimensions": [
            D("dersler", "Dersler & Okul", "Okul ve ders başarısından memnuniyet."),
            D("aile", "Aile İlişkileri", "Aileyle iletişim ve destek hissi."),
            D("arkadas", "Arkadaşlık & Sosyal Hayat", "Arkadaş ilişkileri ve sosyal doyum."),
            D("saglik", "Sağlık, Uyku & Enerji", "Fiziksel enerji, uyku ve beslenme."),
            D("duzen", "Çalışma Ortamı & Düzen", "Çalışma alanı, düzen ve zaman yönetimi."),
            D("eglence", "Eğlence & Hobiler", "Dinlenme, hobi ve keyif alanı."),
            D("gelisim", "Kişisel Gelişim", "Kendini geliştirme ve öğrenme isteği."),
            D("gelecek", "Gelecek & Umut", "Geleceğe dair umut ve güven."),
        ],
        "questions": [
            S("dersler", "Derslerim ve okul başarımdan şu an ne kadar memnunum? (1 = hiç, 10 = çok)"),
            S("aile", "Ailemle ilişkilerimden ne kadar memnunum?"),
            S("arkadas", "Arkadaşlıklarımdan ve sosyal hayatımdan ne kadar memnunum?"),
            S("saglik", "Uykumdan, enerjimden ve genel sağlığımdan ne kadar memnunum?"),
            S("duzen", "Çalışma ortamımdan ve günlük düzenimden ne kadar memnunum?"),
            S("eglence", "Eğlenceye ve hobilerime ayırdığım zamandan ne kadar memnunum?"),
            S("gelisim", "Kendimi geliştirmek için yaptıklarımdan ne kadar memnunum?"),
            S("gelecek", "Geleceğime dair umudum ve güvenim ne durumda?"),
            O("En düşük puan verdiğin alanı düşün: bu alanda neyin değişmesini isterdin?"),
            O("Önümüzdeki bir ay içinde hangi alanda küçük bir adım atmak istersin? Bu adım ne olabilir?"),
        ],
    },
    # =========================================================================
    # 4. SWOT — Tanıma
    # =========================================================================
    {
        "code": "swot",
        "title": "Kişisel SWOT Analizi",
        "category": SURVEY_CATEGORY_TANIMA,
        "scoring_type": SCORING_QUALITATIVE,
        "estimated_minutes": 8,
        "sort_order": 40,
        "description": (
            "Öğrencinin kendi gözünden güçlü/zayıf yönleri ile fırsat ve "
            "engelleri; koçluk planının ham maddesi."
        ),
        "report_note": (
            "Güçlü yönleri hedefe bağlayın; zayıf yön ve engelleri program "
            "tasarımında (telefon kuralı, ortam, destek) somut önleme çevirin."
        ),
        "dimensions": [
            D("guclu", "Güçlü Yönlerim", "Öğrencinin iyi olduğu alanlar."),
            D("zayif", "Geliştirmem Gereken Yönler", "Zorlandığı, geliştirmek istediği alanlar."),
            D("firsat", "Fırsatlarım", "Destek ve imkânlar."),
            D("tehdit", "Engeller & Riskler", "Hedefe giden yoldaki engeller."),
        ],
        "questions": [
            O("Derslerde ve günlük hayatta en iyi olduğun 3 şeyi yaz.", "guclu"),
            O("Arkadaşların ya da öğretmenlerin seni en çok hangi özelliklerinle över?", "guclu"),
            O("Sana en zor gelen, geliştirmek istediğin 3 yönünü yaz.", "zayif"),
            O("Ders çalışırken seni en çok ne zorluyor?", "zayif"),
            O("Sana destek olabilecek imkânlar neler? (koç, kurs, kaynak, aile desteği...)", "firsat"),
            O("Önümüzdeki dönemde işine yarayabilecek bir fırsat görüyor musun? Nedir?", "firsat"),
            O("Hedefine giden yolda seni engelleyebilecek şeyler neler? (telefon, oyun, kaygı...)", "tehdit"),
            O("Hangi alışkanlığın böyle devam ederse sınavda sana zarar verebilir?", "tehdit"),
        ],
    },
    # =========================================================================
    # 5. SINAV KAYGISI — Sınav & Çalışma
    # =========================================================================
    {
        "code": "sinav-kaygisi",
        "title": "Sınav Kaygısı Anketi",
        "category": SURVEY_CATEGORY_SINAV,
        "scoring_type": SCORING_DIMENSIONS,
        "estimated_minutes": 7,
        "sort_order": 10,
        "description": (
            "Kaygının düzeyini ve EN ÖNEMLİSİ kaynağını (beden, düşünce, odak, "
            "çevre baskısı) ayrıştırır; müdahaleyi doğru yere yönlendirir."
        ),
        "report_note": (
            "Yüksek boyut = müdahale noktası: beden → nefes/uyku düzeni; "
            "düşünce → olumsuz senaryolarla çalışma; odak → deneme stratejisi; "
            "baskı → aile ile beklenti konuşması. Çok yüksek genel skor varsa "
            "okul rehberlik servisine yönlendirmeyi düşünün."
        ),
        "dimensions": [
            D("bedensel", "Bedensel Belirtiler",
              "Kaygının bedendeki yansıması (uyku, çarpıntı, mide).",
              high="Belirgin bedensel tepki var — uyku/nefes/mola düzeni konuşulmalı.",
              high_is_good=False),
            D("dusunce", "Olumsuz Düşünceler",
              "Felaket senaryoları ve kendini yetersiz görme.",
              high="Olumsuz iç konuşma güçlü — düşünce kalıpları üzerinde çalışın.",
              high_is_good=False),
            D("odak", "Sınav Anı Odağı",
              "Sınav sırasında dikkat ve performans kaybı.",
              high="Sınav anı stratejisi (tur sistemi, soru atlama, süre planı) çalışılmalı.",
              high_is_good=False),
            D("baski", "Çevre Baskısı & Beklenti",
              "Aile/çevre beklentisinin yarattığı yük.",
              high="Beklenti yükü yüksek — veli görüşmesi ve gerçekçi hedef konuşması önerilir.",
              high_is_good=False),
        ],
        "questions": [
            L("bedensel", "Sınavdan önceki gece uykum kaçar."),
            L("bedensel", "Sınav anında kalbim hızla çarpar, ellerim terler."),
            L("bedensel", "Sınav günü yaklaştıkça midem bulanır ya da karnım ağrır."),
            L("bedensel", "Sınav sırasında nefesim daralıyormuş gibi hissederim."),
            L("bedensel", "Sınav öncesi iştahım belirgin şekilde değişir."),
            L("dusunce", "\"Ya yapamazsam\" düşüncesi sık sık aklıma gelir."),
            L("dusunce", "Sınavda başarısız olursam her şeyin mahvolacağını düşünürüm."),
            L("dusunce", "Diğerlerinin benden daha iyi olduğunu düşünürüm."),
            L("dusunce", "Sınav öncesinde aklımdan kötü senaryolar geçer."),
            L("dusunce", "Bir soruyu yapamayınca \"bu sınav bitti\" diye düşünürüm."),
            L("odak", "Sınavda bildiğim soruları bile heyecandan yanlış yaparım."),
            L("odak", "Sınav sırasında dikkatim sorudan kayar, aklım başka yerlere gider."),
            L("odak", "Süre azaldıkça paniğe kapılır, soruları sağlıklı okuyamam."),
            L("odak", "Sınavda donup kaldığım anlar olur."),
            L("odak", "Sınav bitince aslında bildiğim soruları yanlış yaptığımı fark ederim."),
            L("baski", "Ailemin benden beklentisini düşünmek beni gerer."),
            L("baski", "Sonuçlar açıklanınca başkalarının ne diyeceğinden endişelenirim."),
            L("baski", "Sınavlar kendimi kanıtlamam gereken bir yer gibi gelir."),
            L("baski", "Arkadaşlarımın netlerini duymak kaygımı artırır."),
            L("baski", "Başarısız olursam sevdiklerimi hayal kırıklığına uğratacağımı düşünürüm."),
        ],
    },
    # =========================================================================
    # 6. ÇALIŞMA ALIŞKANLIKLARI — Sınav & Çalışma
    # =========================================================================
    {
        "code": "calisma-aliskanliklari",
        "title": "Çalışma Alışkanlıkları Anketi",
        "category": SURVEY_CATEGORY_SINAV,
        "scoring_type": SCORING_DIMENSIONS,
        "estimated_minutes": 8,
        "sort_order": 20,
        "description": (
            "Planlama, ortam, derste verimlilik, tekrar, soru çözme ve erteleme "
            "alışkanlıklarını tarar; program tasarımının temel girdisi."
        ),
        "report_note": (
            "Düşük boyutlar programda doğrudan karşılık bulmalı: planlama "
            "düşükse haftalık plan birlikte yapılır; tekrar düşükse aralıklı "
            "tekrar devreye girer; erteleme yüksekse küçük-adım görevler verilir."
        ),
        "dimensions": [
            D("planlama", "Planlama",
              "Çalışmayı önceden planlama ve takip.",
              low="Plan alışkanlığı zayıf — haftalık planı birlikte kurun, küçük başlayın."),
            D("ortam", "Çalışma Ortamı",
              "Düzenli, dikkat dağıtıcısız çalışma alanı.",
              low="Ortam düzenlenmeli: sabit masa, telefon uzakta, sade alan."),
            D("derste", "Derste Verimlilik",
              "Derste dinleme, sorma ve not tutma.",
              low="Ders içi verim düşük — not tutma tekniği ve oturma düzeni konuşulmalı."),
            D("tekrar", "Tekrar & Analiz",
              "Konu tekrarı ve yanlış analizi alışkanlığı.",
              low="Tekrar zinciri yok — aynı gün 10 dk tekrar kuralıyla başlayın."),
            D("soru", "Soru Çözme",
              "Düzenli ve bilinçli soru çözme pratiği.",
              low="Soru pratiği az — konu sonrası mini test rutini ekleyin."),
            D("erteleme", "Erteleme Eğilimi",
              "Başlamayı erteleme ve planı uygulamama.",
              high="Erteleme belirgin — 5 dakika kuralı, küçük görevler, başlangıç saati netleştirme.",
              high_is_good=False),
        ],
        "questions": [
            L("planlama", "Haftalık ya da günlük çalışma planı yapar ve takip ederim."),
            L("planlama", "Çalışmaya başlamadan önce neyi, ne kadar çalışacağımı bilirim."),
            L("planlama", "Sınav tarihlerine göre önceden hazırlık yaparım."),
            L("planlama", "Gün içinde çalışma saatlerim aşağı yukarı bellidir."),
            L("ortam", "Çalışırken telefonumu uzakta ya da erişemeyeceğim bir yerde tutarım."),
            L("ortam", "Sabit ve düzenli bir çalışma alanım vardır."),
            L("ortam", "Çalışma masamda yalnızca o an gereken malzemeler bulunur."),
            L("ortam", "Kaynaklarım ve defterlerim düzenlidir; aradığımı kolay bulurum."),
            L("derste", "Derste anlatılanları dikkatle takip ederim."),
            L("derste", "Derste anlamadığım yeri sorarım ya da not alıp sonra araştırırım."),
            L("derste", "Düzenli ve sonradan anlaşılır notlar tutarım."),
            L("derste", "Ders sırasında aklım genellikle derste olur."),
            L("tekrar", "O gün işlenen konuyu aynı gün ya da ertesi gün tekrar ederim."),
            L("tekrar", "Yanlış yaptığım soruların doğru çözümünü mutlaka öğrenirim."),
            L("tekrar", "Konu eksiklerimi belirler ve onlara geri dönerim."),
            L("tekrar", "Denemelerden sonra hangi konudan kaçırdığımı analiz ederim."),
            L("soru", "Konu çalıştıktan sonra mutlaka soru çözerim."),
            L("soru", "Zor sorularla karşılaşınca hemen pes etmem, uğraşırım."),
            L("soru", "Süre tutarak soru çözme alışkanlığım vardır."),
            L("soru", "Farklı zorluk seviyelerinde kaynaklardan soru çözerim."),
            L("erteleme", "Çalışmaya başlamayı son ana kadar ertelerim."),
            L("erteleme", "\"Birazdan başlarım\" der, uzun süre başka şeylerle uğraşırım."),
            L("erteleme", "Zor dersleri sürekli sona bırakırım."),
            L("erteleme", "Plan yapsam bile çoğu zaman uygulamam."),
        ],
    },
    # =========================================================================
    # 7. MESLEKİ İLGİ (RIASEC) — Kariyer Keşif
    # =========================================================================
    {
        "code": "mesleki-ilgi",
        "title": "Mesleki İlgi Envanteri (RIASEC)",
        "category": SURVEY_CATEGORY_KARIYER,
        "scoring_type": SCORING_DIMENSIONS,
        "estimated_minutes": 8,
        "sort_order": 10,
        "description": (
            "Holland'ın 6 ilgi tipine göre öğrencinin meslek yöneliminin "
            "haritasını çıkarır; alan/bölüm hedefi konuşmasının başlangıç noktası."
        ),
        "report_note": (
            "En yüksek 2-3 tip öğrencinin 'Holland kodu'dur. Bu kodu Beceri "
            "Seti sonucu ve gerçek ders performansıyla birlikte yorumlayın — "
            "ilgi + beceri + akademik gerçeklik kesişimi hedef bölgesidir."
        ),
        "source_attribution": (
            "Holland'ın RIASEC modeli temel alınmıştır; maddeler O*NET Interest "
            "Profiler'dan (ABD Çalışma Bakanlığı, CC BY 4.0) esinlenen özgün "
            "ETÜTKOÇ uyarlamasıdır."
        ),
        "dimensions": [
            D("gercekci", "Gerçekçi (Uygulayıcı)",
              "Elle/araçla çalışma, üretme, teknik işler.",
              high="Mühendislik, teknik bölümler, uygulamalı alanlar yakın durur."),
            D("arastirmaci", "Araştırmacı",
              "Merak, inceleme, bilimsel düşünme.",
              high="Tıp, temel bilimler, araştırma ağırlıklı bölümler yakın durur."),
            D("sanatci", "Sanatçı (Yaratıcı)",
              "Yaratma, tasarım, özgün ifade.",
              high="Tasarım, iletişim, sanat ve yaratıcı endüstriler yakın durur."),
            D("sosyal", "Sosyal (Yardım Eden)",
              "İnsanlara yardım, öğretme, destek.",
              high="Öğretmenlik, psikoloji, sağlık ve sosyal hizmet yakın durur."),
            D("girisimci", "Girişimci (Yönetici)",
              "Liderlik, ikna, organizasyon.",
              high="İşletme, hukuk, yöneticilik ve girişimcilik yakın durur."),
            D("duzenli", "Düzenli (Sistemli)",
              "Düzen, ayrıntı, sistemli çalışma.",
              high="Finans, muhasebe, veri ve planlama gerektiren alanlar yakın durur."),
        ],
        "questions": [
            L("gercekci", "Bozulan bir aleti söküp tamir etmek hoşuma giderdi."),
            L("gercekci", "Bir makinenin ya da aracın nasıl çalıştığını yerinde incelemek hoşuma giderdi."),
            L("gercekci", "Elektronik bir devre ya da mekanik bir düzenek kurmak hoşuma giderdi."),
            L("gercekci", "Açık havada fiziksel çaba gerektiren bir işte çalışmak hoşuma giderdi."),
            L("gercekci", "Ahşap, metal ya da 3D yazıcıyla bir ürün üretmek hoşuma giderdi."),
            L("arastirmaci", "Bir deneyin sonucunu merak edip laboratuvarda çalışmak hoşuma giderdi."),
            L("arastirmaci", "Bir hastalığın nedenini araştırmak hoşuma giderdi."),
            L("arastirmaci", "Karmaşık bir problemi çözmek için saatlerce veri incelemek hoşuma giderdi."),
            L("arastirmaci", "Bilimsel bir araştırmayı okuyup tartışmak hoşuma giderdi."),
            L("arastirmaci", "Yıldızları, evreni ya da doğa olaylarını incelemek hoşuma giderdi."),
            L("sanatci", "Bir şarkı, şiir ya da hikâye yazmak hoşuma giderdi."),
            L("sanatci", "Resim, illüstrasyon ya da dijital tasarım yapmak hoşuma giderdi."),
            L("sanatci", "Bir tiyatro oyununda ya da videoda rol almak hoşuma giderdi."),
            L("sanatci", "Bir mekânın dekorasyonunu ya da tasarımını yapmak hoşuma giderdi."),
            L("sanatci", "Özgün bir fikirden yeni bir şey (oyun, içerik, ürün) yaratmak hoşuma giderdi."),
            L("sosyal", "Birine ders anlatmak, bir konuyu öğretmek hoşuma giderdi."),
            L("sosyal", "Zor durumda olan birine destek olmak, yol göstermek hoşuma giderdi."),
            L("sosyal", "Hasta ya da yaşlı birinin bakımına yardım etmek hoşuma giderdi."),
            L("sosyal", "Bir yardım kampanyası düzenlemek hoşuma giderdi."),
            L("sosyal", "İnsanların sorunlarını dinleyip çözüm bulmalarına yardım etmek hoşuma giderdi."),
            L("girisimci", "Kendi işimi ya da projemi kurup yönetmek hoşuma giderdi."),
            L("girisimci", "Bir ekibi hedefe ulaştırmak için yönlendirmek hoşuma giderdi."),
            L("girisimci", "Bir ürünü tanıtıp insanları ikna etmek hoşuma giderdi."),
            L("girisimci", "Okulda ya da bir toplulukta etkinlik sorumluluğu üstlenmek hoşuma giderdi."),
            L("girisimci", "Bir tartışmada fikrimi savunup insanları ikna etmek hoşuma giderdi."),
            L("duzenli", "Bir listedeki bilgileri sınıflandırıp düzenlemek hoşuma giderdi."),
            L("duzenli", "Bir bütçe ya da hesap tablosu tutmak hoşuma giderdi."),
            L("duzenli", "Belgeleri ve dosyaları sistemli şekilde arşivlemek hoşuma giderdi."),
            L("duzenli", "Kurallara göre titizlikle ilerleyen bir işte çalışmak hoşuma giderdi."),
            L("duzenli", "Bir etkinliğin ayrıntılarını planlayıp adım adım takip etmek hoşuma giderdi."),
        ],
    },
    # =========================================================================
    # 8. AKADEMİK BENLİK — Kariyer Keşif
    # =========================================================================
    {
        "code": "akademik-benlik",
        "title": "Akademik Benlik Anketi",
        "category": SURVEY_CATEGORY_KARIYER,
        "scoring_type": SCORING_DIMENSIONS,
        "estimated_minutes": 6,
        "sort_order": 20,
        "description": (
            "Öğrencinin alanlara göre 'kendine güven haritası'; alan seçimi ve "
            "gerçek performansla (deneme netleri) kıyas için kullanılır."
        ),
        "report_note": (
            "Benlik algısı ile GERÇEK performansı (deneme/konu verisi) "
            "karşılaştırın: algı düşük + performans iyi → güven çalışması; "
            "algı yüksek + performans düşük → yöntem çalışması gerekir."
        ),
        "dimensions": [
            D("sozelb", "Sözel Alan Güveni", "Dil/edebiyat alanında yetkinlik algısı.",
              high="Sözel ağırlıklı alan ve bölümler güven bölgesi."),
            D("sayisalb", "Sayısal Alan Güveni", "Matematik alanında yetkinlik algısı.",
              high="Sayısal ağırlıklı alan ve bölümler güven bölgesi."),
            D("fenb", "Fen Alanı Güveni", "Fen bilimlerinde yetkinlik algısı.",
              high="Fen ağırlıklı bölümler (sağlık, mühendislik) güven bölgesi."),
            D("sosyalb", "Sosyal Bilimler Güveni", "Sosyal bilimlerde yetkinlik algısı.",
              high="Sosyal bilimler ve insan odaklı bölümler güven bölgesi."),
            D("guven", "Genel Akademik Güven", "Öğrenebilirim inancı (öz-yeterlik).",
              low="Genel güven düşük — küçük başarı deneyimleri planlayın, hedefi kademelendirin."),
        ],
        "questions": [
            L("sozelb", "Türkçe/edebiyat derslerinde kendime güvenirim."),
            L("sozelb", "Okuduğumu anlama konusunda iyi olduğumu düşünürüm."),
            L("sozelb", "Yazılı anlatımım (kompozisyon) güçlüdür."),
            L("sozelb", "Sözel ağırlıklı konuları kolay öğrenirim."),
            L("sayisalb", "Matematik derslerinde kendime güvenirim."),
            L("sayisalb", "Sayısal problemleri çözebileceğime inanırım."),
            L("sayisalb", "Matematikte yeni bir konuyu kavramakta genellikle zorlanmam."),
            L("sayisalb", "Sayısal ağırlıklı bir bölümde başarılı olabilirim."),
            L("fenb", "Fen derslerinde (fizik, kimya, biyoloji) kendime güvenirim."),
            L("fenb", "Deneyler ve bilimsel konular bana anlaşılır gelir."),
            L("fenb", "Fen sorularını çözebileceğime inanırım."),
            L("fenb", "Fen ağırlıklı bir meslekte başarılı olabilirim."),
            L("sosyalb", "Tarih ve coğrafya gibi derslerde kendime güvenirim."),
            L("sosyalb", "Toplumsal konuları yorumlamakta iyiyimdir."),
            L("sosyalb", "Sosyal bilgiler konularını kolay öğrenirim."),
            L("sosyalb", "İnsan ve toplumla ilgili bir alanda başarılı olabilirim."),
            L("guven", "Çabalarsam zor konuları da öğrenebileceğime inanırım."),
            L("guven", "Sınavlarda gerçek seviyemi gösterebildiğimi düşünürüm."),
            L("guven", "Hedeflediğim okula ya da bölüme girebilecek kapasitem var."),
            L("guven", "Yeni bir konuya başlarken \"öğrenirim\" diye düşünürüm."),
        ],
    },
    # =========================================================================
    # 9. BAŞARISIZLIK NEDENLERİ — Hedef & Motivasyon
    # =========================================================================
    {
        "code": "basarisizlik-nedenleri",
        "title": "Başarıyı Engelleyen Nedenler Anketi",
        "category": SURVEY_CATEGORY_MOTIVASYON,
        "scoring_type": SCORING_DIMENSIONS,
        "estimated_minutes": 7,
        "sort_order": 10,
        "description": (
            "Düşük performansın KÖK NEDENİNİ (yöntem, motivasyon, dikkat, "
            "temel eksiği, çevre) ayrıştırır; doğru müdahaleyi seçtirir."
        ),
        "report_note": (
            "Bu ankette yüksek skor = sorun alanı. En yüksek boyut, koçluk "
            "müdahalesinin başlama noktasıdır; iki boyut yakınsa ikisini de "
            "görüşmede doğrulayın."
        ),
        "dimensions": [
            D("yontem", "Yöntem Bilgisi Eksikliği",
              "Verimli çalışmayı bilmeme.",
              high="Sorun çaba değil yöntem — çalışma tekniği eğitimi ve planlı program kurun.",
              high_is_good=False),
            D("motivasyon", "Motivasyon Eksikliği",
              "İsteksizlik ve anlam kaybı.",
              high="Önce hedef netliği çalışın (Kariyer Keşif anketleri) — 'neden'i olmayan çalışamaz.",
              high_is_good=False),
            D("dikkat", "Dikkat & Teknoloji",
              "Telefon/oyun ve odak dağınıklığı.",
              high="Telefon kuralı + odak tekniği (pomodoro) + ortam düzenlemesi gerekli.",
              high_is_good=False),
            D("temel", "Temel / Altyapı Eksikleri",
              "Önceki yıllardan birikmiş konu eksikleri.",
              high="Eksik kapatma programı şart — seviyeden başlayan kaynak planlayın.",
              high_is_good=False),
            D("cevre", "Çevre & Duygusal Etkenler",
              "Ortam, ilişkiler ve duygusal yük.",
              high="Çevresel/duygusal yük belirgin — veli görüşmesi ve gerekirse rehberlik desteği.",
              high_is_good=False),
        ],
        "questions": [
            L("yontem", "Nasıl verimli çalışacağımı tam olarak bilmiyorum."),
            L("yontem", "Çok çalıştığım hâlde karşılığını alamıyorum."),
            L("yontem", "Hangi kaynaktan, nasıl çalışacağıma karar veremiyorum."),
            L("yontem", "Ezberliyorum ama kısa sürede unutuyorum."),
            L("motivasyon", "Çalışmak için kendimde istek bulamıyorum."),
            L("motivasyon", "\"Neden çalışıyorum ki\" düşüncesine sık kapılıyorum."),
            L("motivasyon", "Hedefim net olmadığı için çalışmak anlamsız geliyor."),
            L("motivasyon", "Başladığım çalışmayı sürdürmekte zorlanıyorum."),
            L("dikkat", "Telefon ve sosyal medya çalışma süremi ciddi şekilde azaltıyor."),
            L("dikkat", "Çalışırken aklım sık sık başka yerlere gidiyor."),
            L("dikkat", "Oyun ya da dizi yüzünden planlarım aksıyor."),
            L("dikkat", "Kısa süre sonra çalışmayı bırakıp başka şeylere yöneliyorum."),
            L("temel", "Önceki yıllardan eksik konularım yeni konuları anlamamı zorlaştırıyor."),
            L("temel", "Bazı derslerde temelim zayıf olduğu için derse yetişemiyorum."),
            L("temel", "Soru çözerken eski konulardaki eksiklerim ortaya çıkıyor."),
            L("temel", "Eksiklerimin tam olarak nereden başladığını bilmiyorum."),
            L("cevre", "Evdeki ortam (gürültü, kalabalık, sorumluluklar) çalışmamı zorlaştırıyor."),
            L("cevre", "Ailevi ya da arkadaşlıkla ilgili konular aklımı meşgul ediyor."),
            L("cevre", "Kendimi sık sık yorgun ve isteksiz hissediyorum."),
            L("cevre", "Kaygı ve stres performansımı düşürüyor."),
        ],
    },
    # =========================================================================
    # 10. HEDEF & MOTİVASYON — Hedef & Motivasyon
    # =========================================================================
    {
        "code": "hedef-motivasyon",
        "title": "Hedef & Motivasyon Anketi",
        "category": SURVEY_CATEGORY_MOTIVASYON,
        "scoring_type": SCORING_DIMENSIONS,
        "estimated_minutes": 7,
        "sort_order": 20,
        "description": (
            "Hedef netliği, motivasyon kaynağı (içsel/dışsal), öz-yeterlik ve "
            "kararlılığı ölçer; hedef belirleme seansının ön hazırlığı."
        ),
        "report_note": (
            "Hedef netliği düşükse önce Kariyer Keşif anketlerini uygulayın — "
            "somut bölüm/meslek hedefi motivasyonun en güçlü kaynağıdır. "
            "Dışsal motivasyon baskınsa hedefi öğrencinin 'kendi nedeni'ne bağlayın."
        ),
        "dimensions": [
            D("netlik", "Hedef Netliği",
              "Somut, görünür bir hedefin varlığı.",
              low="Hedef bulanık — kariyer keşif çalışması ve somut okul/bölüm hedefi önceliklidir."),
            D("icsel", "İçsel Motivasyon",
              "Öğrenmenin kendisinden keyif alma.",
              high="İçsel motivasyon güçlü — merak uyandıran içerik ve zorlayıcı hedefler işe yarar."),
            D("dissal", "Dışsal Motivasyon",
              "Onay, ödül ve çevre kaynaklı itki.",
              high="Dışsal kaynak baskın — sürdürülebilirlik için hedefi içsel nedene bağlayın."),
            D("ozyeterlik", "Öz-Yeterlik",
              "Başarabilirim inancı.",
              low="Başarabilirim inancı zayıf — küçük kazanımlarla güven inşa edin."),
            D("azim", "Kararlılık & Süreklilik",
              "Zorlukta devam edebilme.",
              low="Süreklilik kırılgan — rutinler ve seri takibi (streak) destekleyici olur."),
        ],
        "questions": [
            L("netlik", "Sınavdan sonra hangi okulda ya da bölümde olmak istediğimi biliyorum."),
            L("netlik", "Hedefimi düşündüğümde gözümde net bir resim canlanıyor."),
            L("netlik", "Bu yıl için somut bir puan ya da net hedefim var."),
            L("netlik", "Hedefime neden ulaşmak istediğimi tek cümleyle söyleyebilirim."),
            L("icsel", "Yeni şeyler öğrenmek bana keyif verir."),
            L("icsel", "Bir konuyu tam anladığımda büyük tatmin duyarım."),
            L("icsel", "Kimse söylemese de kendi isteğimle çalışırım."),
            L("icsel", "Zor bir soruyu çözmek bana heyecan verir."),
            L("dissal", "Ailemi mutlu etmek, çalışmam için önemli bir sebep."),
            L("dissal", "Takdir edilmek ya da ödül kazanmak beni çalışmaya iter."),
            L("dissal", "Arkadaşlarımdan geride kalmamak için çalışırım."),
            L("dissal", "İyi bir gelecek ve meslek için çalışmam gerektiğini düşünürüm."),
            L("ozyeterlik", "Düzenli çalışırsam hedefime ulaşabileceğime inanıyorum."),
            L("ozyeterlik", "Zorluklarla karşılaşınca üstesinden gelebileceğimi düşünürüm."),
            L("ozyeterlik", "Geçmişte başardığım işler bana güven veriyor."),
            L("ozyeterlik", "Başarının büyük ölçüde kendi kontrolümde olduğunu düşünürüm."),
            L("azim", "Kötü bir deneme sonucu beni yolumdan döndürmez."),
            L("azim", "Sıkıldığım zamanlarda bile çalışmayı sürdürebilirim."),
            L("azim", "Uzun vadeli hedefler için bugünden fedakârlık yapabilirim."),
            L("azim", "Bir işi yarım bırakmak beni rahatsız eder."),
        ],
    },
    # =========================================================================
    # 11. BECERİ SETİ — Kariyer Keşif (AI Kariyer Sentezi girdisi)
    # =========================================================================
    {
        "code": "beceri-seti",
        "title": "Beceri Seti Öz-Değerlendirme",
        "category": SURVEY_CATEGORY_KARIYER,
        "scoring_type": SCORING_DIMENSIONS,
        "estimated_minutes": 10,
        "sort_order": 30,
        "description": (
            "8 beceri alanında öğrencinin kendini değerlendirmesi. Mesleki İlgi "
            "(neyi sever) ile birlikte 'neyi yapabilir' haritasını tamamlar — "
            "kariyer hedefi belirleme denkleminin ikinci yarısı."
        ),
        "report_note": (
            "Beceri (yapabilirim) + İlgi (severim) kesişimine bakın: ikisi de "
            "yüksek olan alanlar doğal hedef bölgesidir. Akademik gerçeklikle "
            "(deneme netleri, ders performansı) birlikte değerlendirin."
        ),
        "dimensions": [
            D("ifade", "Sözel İfade & İletişim",
              "Konuşma, yazma ve ikna gücü.",
              high="Hukuk, iletişim, öğretmenlik, medya gibi ifade-yoğun alanlara taşınabilir."),
            D("analitik", "Sayısal & Analitik Düşünme",
              "Veri, mantık ve sayısal akıl yürütme.",
              high="Mühendislik, ekonomi, veri bilimi gibi analitik alanlara taşınabilir."),
            D("problem", "Problem Çözme & Karar Verme",
              "Sorun karşısında çözüm üretme.",
              high="Her alanda değerli; mühendislik, tıp, yöneticilikte kritik beceri."),
            D("yaraticilik", "Yaratıcılık",
              "Yeni ve özgün fikir üretme.",
              high="Tasarım, mimarlık, yazılım, içerik üretimi gibi yaratıcı alanlara taşınabilir."),
            D("sosyalb", "Sosyal Beceri & Empati",
              "İnsanları anlama ve birlikte çalışma.",
              high="Psikoloji, öğretmenlik, sağlık, insan kaynakları gibi insan-odaklı alanlara taşınabilir."),
            D("liderlik", "Liderlik & Organizasyon",
              "Yönlendirme, planlama, sorumluluk alma.",
              high="Yöneticilik, işletme, organizasyon gerektiren her alana taşınabilir."),
            D("teknik", "El Becerisi & Teknik",
              "Elle yapma, kurma, pratik zekâ.",
              high="Cerrahi, diş hekimliği, teknik mühendislikler, zanaat alanlarına taşınabilir."),
            D("dijital", "Dijital & Teknoloji",
              "Teknolojiyi hızlı öğrenme ve üretme.",
              high="Yazılım, oyun, siber güvenlik, dijital tasarım alanlarına taşınabilir."),
        ],
        "questions": [
            L("ifade", "Düşüncelerimi konuşarak açık ve etkili anlatırım."),
            L("ifade", "Yazıyla kendimi iyi ifade ederim."),
            L("ifade", "Topluluk önünde konuşmakta çok zorlanmam."),
            L("ifade", "Karşımdaki kişiyi fikrime ikna edebilirim."),
            L("analitik", "Sayısal verilerle çalışmakta iyiyimdir."),
            L("analitik", "Karmaşık bir problemi parçalara ayırıp çözerim."),
            L("analitik", "Mantık yürüterek sonuca ulaşmakta hızlıyımdır."),
            L("analitik", "Grafik ve tabloları kolay yorumlarım."),
            L("problem", "Beklenmedik bir sorunla karşılaşınca soğukkanlı kalır, çözüm üretirim."),
            L("problem", "Karar verirken seçenekleri artı ve eksileriyle değerlendiririm."),
            L("problem", "Daha önce denenmemiş yolları denemekten çekinmem."),
            L("problem", "Zor durumlarda pratik çözümler bulurum."),
            L("yaraticilik", "Aklıma sık sık yeni ve farklı fikirler gelir."),
            L("yaraticilik", "Bir konuya başkalarının düşünmediği açılardan bakabilirim."),
            L("yaraticilik", "Elimdeki malzemelerle özgün bir şeyler üretmeyi severim."),
            L("yaraticilik", "Hayal gücümün güçlü olduğunu düşünürüm."),
            L("sosyalb", "İnsanların duygularını kolay anlarım."),
            L("sosyalb", "Farklı kişilerle kolayca iletişim kurarım."),
            L("sosyalb", "Ekip içinde uyumlu çalışırım."),
            L("sosyalb", "Aralarında sorun olan arkadaşlarımı uzlaştırabilirim."),
            L("liderlik", "Grup çalışmalarında genellikle yönlendiren kişi olurum."),
            L("liderlik", "Bir işi planlayıp görev dağılımı yapmakta iyiyimdir."),
            L("liderlik", "Sorumluluk almaktan çekinmem."),
            L("liderlik", "İnsanları ortak bir hedef etrafında bir araya getirebilirim."),
            L("teknik", "Elimle bir şeyler yapmakta (tamir, montaj, maket) iyiyimdir."),
            L("teknik", "Bir cihazın nasıl çalıştığını kurcalayarak çözebilirim."),
            L("teknik", "Pratik ve somut işlerde kendime güvenirim."),
            L("teknik", "Yeni araç-gereç kullanmayı hızlı öğrenirim."),
            L("dijital", "Yeni bir uygulamayı ya da programı hızla öğrenirim."),
            L("dijital", "Bilgisayar/tablette içerik üretebilirim (sunum, video, tasarım...)."),
            L("dijital", "Teknolojik sorunları çoğunlukla kendi başıma çözerim."),
            L("dijital", "Kodlama, robotik ya da oyun geliştirme gibi alanlar ilgimi çeker."),
        ],
    },
]


def seed(reset: bool = False) -> tuple[int, int]:
    created = 0
    skipped = 0
    with SessionLocal() as db:
        if reset:
            codes = [s["code"] for s in SEED_SURVEYS]
            existing = (
                db.query(SurveyTemplate)
                .filter(SurveyTemplate.code.in_(codes))
                .all()
            )
            for t in existing:
                db.delete(t)  # cascade: sorular + atamalar
            db.commit()
        for spec in SEED_SURVEYS:
            exists = (
                db.query(SurveyTemplate.id)
                .filter(SurveyTemplate.code == spec["code"])
                .first()
            )
            if exists:
                skipped += 1
                continue
            t = SurveyTemplate(
                code=spec["code"],
                title=spec["title"],
                description=spec.get("description", ""),
                category=spec["category"],
                scoring_type=spec["scoring_type"],
                dimensions_json=json.dumps(
                    spec.get("dimensions", []), ensure_ascii=False
                ),
                report_note=spec.get("report_note", ""),
                source_attribution=spec.get("source_attribution", ""),
                estimated_minutes=spec.get("estimated_minutes", 10),
                sort_order=spec.get("sort_order", 100),
                is_active=True,
            )
            db.add(t)
            db.flush()
            for i, q in enumerate(spec["questions"], start=1):
                db.add(SurveyQuestion(
                    template_id=t.id,
                    order_no=i,
                    text=q["text"],
                    qtype=q["qtype"],
                    dimension_key=q.get("dimension_key"),
                    options_json=None,
                    reverse=bool(q.get("reverse", False)),
                ))
            created += 1
        db.commit()
    return created, skipped


if __name__ == "__main__":
    reset = "--reset" in sys.argv
    created, skipped = seed(reset=reset)
    print(f"Anket seed tamam: {created} oluşturuldu, {skipped} atlandı (mevcut).")
