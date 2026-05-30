"""P2 — 35 WhatsApp şablonunu DB'ye **idempotent** yükle.

Kullanım:
    python scripts/seed_whatsapp_templates.py
    python scripts/seed_whatsapp_templates.py --reset   # tüm seed'leri siler+yeniden yazar (DİKKAT: kullanıcı edit'lerini siler)

Idempotent: mevcut `key` varsa ATLAR — süper adminin sonradan yaptığı metin/değişken
düzenlemeleri korunur. `--reset` ile zorlanırsa hepsi silinip yeniden yazılır.

Değişken sözdizimi: `{{degisken_adi}}` (Jinja deseni; P4'te wa.me URL üretimi
sırasında doldurulur).
"""
from __future__ import annotations

import json
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal
from app.models import (
    CATEGORY_ADMIN_SISTEM,
    CATEGORY_ADMIN_YONETICI,
    CATEGORY_KURUM_OGRENCI,
    CATEGORY_KURUM_OGRETMEN,
    CATEGORY_KURUM_VELI,
    CATEGORY_OGRENCI,
    CATEGORY_VELI,
    TARGET_INSTITUTION_ADMIN,
    TARGET_SUPER_ADMIN,
    TARGET_TEACHER,
    WhatsAppTemplate,
)


# Değişken yardımcısı (label_tr + örnek değer ile)
def V(key: str, label: str, example: str) -> dict:
    return {"key": key, "label_tr": label, "example": example}


# Yaygın değişkenler
V_VELI = V("veli_adi", "Velinin adı", "Ayşe Yılmaz")
V_OGRENCI = V("ogrenci_adi", "Öğrencinin adı", "Mehmet")
V_KOC = V("koc_adi", "Koçun/öğretmenin adı", "Burak Bey")
V_KURUM = V("kurum_adi", "Kurum adı", "Etüt Akademi")
V_LINK = V("link", "Panel/link", "https://rotam.etutkoc.com/parent")
V_TARIH = V("tarih", "Tarih", "12.06.2026")
V_SAAT = V("saat", "Saat", "14:30")
V_YER = V("yer", "Yer/adres", "Etüt Salonu A")
V_SINAV_AD = V("sinav_adi", "Sınav adı", "LGS")
V_GUN_SAYISI = V("gun_sayisi", "Gün sayısı", "30")
V_NET = V("net", "Net puanı", "78.50")
V_DENEME_AD = V("deneme_adi", "Deneme adı", "Etüt Deneme 7")
V_TAMAMLANAN = V("tamamlanan", "Tamamlanan görev sayısı", "15")
V_PLANLANAN = V("planlanan", "Planlanan görev sayısı", "20")
V_YUZDE = V("yuzde", "Yüzde", "75")
V_BASARI = V("basari", "Başarı/durum açıklaması", "haftalık hedefini tutturdu")
V_NEDEN = V("neden", "Neden/açıklama", "son 5 günde program girişi yok")
V_BAYRAM = V("bayram_adi", "Bayram/özel gün", "Ramazan Bayramı")
V_KALAN_GOREV = V("kalan_gorev", "Kalan görev sayısı", "3")
V_BASLIK = V("baslik", "Başlık", "Önemli duyuru")
V_MESAJ = V("mesaj", "Serbest mesaj metni", "Yarınki etkinlik iptal edilmiştir.")
V_ETKINLIK = V("etkinlik_adi", "Etkinlik adı", "Sınıflar arası bilgi yarışması")
V_TUTAR = V("tutar", "Tutar (₺)", "1.500")
V_SON_TARIH = V("son_tarih", "Son tarih", "30.06.2026")
V_OZELLIK = V("ozellik_adi", "Özellik adı", "Aksiyon Merkezi")
V_BASLANGIC = V("baslangic", "Başlangıç saati", "03:00")
V_BITIS = V("bitis", "Bitiş saati", "05:00")
V_TALEP_NO = V("talep_no", "Talep numarası", "#12345")
V_DURUM = V("durum", "Durum açıklaması", "çözüldü")
V_PAKET = V("paket_adi", "Paket adı", "Solo Pro")


# 35 ŞABLON
SEED_TEMPLATES: list[dict] = [
    # ========== A. Koç → Veli (10) ==========
    {
        "key": "veli_yeni_program",
        "category": CATEGORY_VELI,
        "target_role": TARGET_TEACHER,
        "name_tr": "Yeni program yayınlandı",
        "description": "Haftalık programın yayınlandığını veliye bildirir.",
        "content_template": (
            "Merhaba {{veli_adi}}, {{ogrenci_adi}} için bu haftanın çalışma "
            "programını yayınladım. Panele girip görebilirsiniz: {{link}}\n— {{koc_adi}}"
        ),
        "variables": [V_VELI, V_OGRENCI, V_LINK, V_KOC],
        "sort_order": 10,
    },
    {
        "key": "veli_haftalik_ozet",
        "category": CATEGORY_VELI,
        "target_role": TARGET_TEACHER,
        "name_tr": "Haftalık özet",
        "description": "Geçen haftanın tamamlama özeti.",
        "content_template": (
            "Merhaba {{veli_adi}}, {{ogrenci_adi}} bu hafta planlanan "
            "{{planlanan}} görevden {{tamamlanan}} tanesini tamamladı (%{{yuzde}}). "
            "Detaylar için: {{link}}"
        ),
        "variables": [V_VELI, V_OGRENCI, V_PLANLANAN, V_TAMAMLANAN, V_YUZDE, V_LINK],
        "sort_order": 20,
    },
    {
        "key": "veli_deneme_sonucu",
        "category": CATEGORY_VELI,
        "target_role": TARGET_TEACHER,
        "name_tr": "Deneme sonucu",
        "description": "Deneme sonucu + net bilgisi.",
        "content_template": (
            "Merhaba {{veli_adi}}, {{ogrenci_adi}} {{deneme_adi}} sınavında "
            "{{net}} net yaptı. Detaylar panelde: {{link}}\n— {{koc_adi}}"
        ),
        "variables": [V_VELI, V_OGRENCI, V_DENEME_AD, V_NET, V_LINK, V_KOC],
        "sort_order": 30,
    },
    {
        "key": "veli_bu_hafta_dikkat",
        "category": CATEGORY_VELI,
        "target_role": TARGET_TEACHER,
        "name_tr": "Bu hafta dikkat (geride)",
        "description": "Öğrenci geride kaldığında veliye uyarı.",
        "content_template": (
            "Merhaba {{veli_adi}}, {{ogrenci_adi}} bu hafta beklenenin altında "
            "ilerliyor ({{neden}}). Birlikte konuşup destek olabilir miyiz?\n— {{koc_adi}}"
        ),
        "variables": [V_VELI, V_OGRENCI, V_NEDEN, V_KOC],
        "sort_order": 40,
    },
    {
        "key": "veli_tebrik",
        "category": CATEGORY_VELI,
        "target_role": TARGET_TEACHER,
        "name_tr": "Tebrik / motivasyon",
        "description": "Başarı için tebrik mesajı (ek not eklenebilir).",
        "content_template": (
            "Merhaba {{veli_adi}}, {{ogrenci_adi}} {{basari}}. Devam etmesi için "
            "siz de tebrik ederseniz çok motive olur.\n— {{koc_adi}}"
        ),
        "variables": [V_VELI, V_OGRENCI, V_BASARI, V_KOC],
        "allow_freeform_note": True,
        "sort_order": 50,
    },
    {
        "key": "veli_gorusme_rica",
        "category": CATEGORY_VELI,
        "target_role": TARGET_TEACHER,
        "name_tr": "Veli görüşmesi rica",
        "description": "Veli ile görüşme talebi (tarih + saat seçicili).",
        "content_template": (
            "Merhaba {{veli_adi}}, {{ogrenci_adi}}'in durumunu konuşmak için "
            "{{tarih}} {{saat}}'te kısa bir görüşme yapabilir miyiz?\n— {{koc_adi}}"
        ),
        "variables": [V_VELI, V_OGRENCI, V_TARIH, V_SAAT, V_KOC],
        "requires_date": True,
        "sort_order": 60,
    },
    {
        "key": "veli_sinav_yaklasiyor",
        "category": CATEGORY_VELI,
        "target_role": TARGET_TEACHER,
        "name_tr": "Sınav yaklaşıyor",
        "description": "LGS/YKS yaklaşan günlerde veli hatırlatma.",
        "content_template": (
            "Merhaba {{veli_adi}}, {{sinav_adi}}'a {{gun_sayisi}} gün kaldı. "
            "{{ogrenci_adi}}'in son hafta planını panelden inceleyebilirsiniz: {{link}}"
        ),
        "variables": [V_VELI, V_SINAV_AD, V_GUN_SAYISI, V_OGRENCI, V_LINK],
        "sort_order": 70,
    },
    {
        "key": "veli_panel_daveti",
        "category": CATEGORY_VELI,
        "target_role": TARGET_TEACHER,
        "name_tr": "Veli paneli daveti",
        "description": "Henüz panele kayıt olmamış veliye davet.",
        "content_template": (
            "Merhaba {{veli_adi}}, {{ogrenci_adi}}'in çalışma sürecini sizinle "
            "paylaşmak için Etütkoç Rotam veli panelini açtım. Şu linkten kayıt "
            "olabilirsiniz: {{link}}\n— {{koc_adi}}"
        ),
        "variables": [V_VELI, V_OGRENCI, V_LINK, V_KOC],
        "sort_order": 80,
    },
    {
        "key": "veli_genel_duyuru",
        "category": CATEGORY_VELI,
        "target_role": TARGET_TEACHER,
        "name_tr": "Genel duyuru (serbest mesaj)",
        "description": "Veliye özel/serbest bir mesaj göndermek için.",
        "content_template": "Merhaba {{veli_adi}}, {{mesaj}}\n— {{koc_adi}}",
        "variables": [V_VELI, V_MESAJ, V_KOC],
        "allow_freeform_note": True,
        "sort_order": 90,
    },
    {
        "key": "veli_bayram",
        "category": CATEGORY_VELI,
        "target_role": TARGET_TEACHER,
        "name_tr": "Bayram / özel gün",
        "description": "Bayram ve özel günler için sıcak mesaj.",
        "content_template": (
            "Merhaba {{veli_adi}}, {{bayram_adi}}'nızı içtenlikle kutlarım. "
            "Sağlık, huzur ve birlik dolu günler dilerim.\n— {{koc_adi}}"
        ),
        "variables": [V_VELI, V_BAYRAM, V_KOC],
        "allow_bulk": True,
        "sort_order": 100,
    },

    # ========== B. Koç → Öğrenci (5) ==========
    {
        "key": "ogrenci_bugun_eksik",
        "category": CATEGORY_OGRENCI,
        "target_role": TARGET_TEACHER,
        "name_tr": "Bugün hala eksiksin",
        "description": "Bugünün görevlerini tamamlamamış öğrenciye dürtü.",
        "content_template": (
            "{{ogrenci_adi}}, bugün hâlâ {{kalan_gorev}} görevin var. Akşam "
            "kapatabilirsen harika olur. Yardım gerekirse yazın.\n— {{koc_adi}}"
        ),
        "variables": [V_OGRENCI, V_KALAN_GOREV, V_KOC],
        "sort_order": 10,
    },
    {
        "key": "ogrenci_yeni_program",
        "category": CATEGORY_OGRENCI,
        "target_role": TARGET_TEACHER,
        "name_tr": "Yeni program",
        "description": "Yeni haftalık programın yayınlandığı bilgisi.",
        "content_template": (
            "{{ogrenci_adi}}, bu haftanın programını paylaştım. Panelden "
            "kontrol et: {{link}}\n— {{koc_adi}}"
        ),
        "variables": [V_OGRENCI, V_LINK, V_KOC],
        "sort_order": 20,
    },
    {
        "key": "ogrenci_sinav_yaklasiyor",
        "category": CATEGORY_OGRENCI,
        "target_role": TARGET_TEACHER,
        "name_tr": "Sınav yaklaşıyor",
        "description": "Sınava sayılı gün kala motivasyon.",
        "content_template": (
            "{{ogrenci_adi}}, {{sinav_adi}}'a {{gun_sayisi}} gün kaldı. Son "
            "düzlüğe odaklan; ben yanındayım.\n— {{koc_adi}}"
        ),
        "variables": [V_OGRENCI, V_SINAV_AD, V_GUN_SAYISI, V_KOC],
        "sort_order": 30,
    },
    {
        "key": "ogrenci_tebrik",
        "category": CATEGORY_OGRENCI,
        "target_role": TARGET_TEACHER,
        "name_tr": "Tebrik (hedef tutturma)",
        "description": "Hedef tutturduğunda tebrik.",
        "content_template": (
            "{{ogrenci_adi}}, harikasın! {{basari}}. Bu tempoyu koru.\n— {{koc_adi}}"
        ),
        "variables": [V_OGRENCI, V_BASARI, V_KOC],
        "allow_freeform_note": True,
        "sort_order": 40,
    },
    {
        "key": "ogrenci_motivasyon",
        "category": CATEGORY_OGRENCI,
        "target_role": TARGET_TEACHER,
        "name_tr": "Çalışma motivasyonu",
        "description": "Serbest motivasyon mesajı.",
        "content_template": "{{ogrenci_adi}}, {{mesaj}}\n— {{koc_adi}}",
        "variables": [V_OGRENCI, V_MESAJ, V_KOC],
        "allow_freeform_note": True,
        "sort_order": 50,
    },

    # ========== C. Kurum yön. → Öğretmen (5) ==========
    {
        "key": "kurum_ogretmen_yeni_ogrenci",
        "category": CATEGORY_KURUM_OGRETMEN,
        "target_role": TARGET_INSTITUTION_ADMIN,
        "name_tr": "Yeni öğrenci atandı",
        "description": "Koça yeni öğrenci ataması bildirir.",
        "content_template": (
            "Merhaba {{koc_adi}}, panelinize {{ogrenci_adi}} adında yeni "
            "öğrenci atandı. Lütfen kontrol edip programını oluşturun: {{link}}"
        ),
        "variables": [V_KOC, V_OGRENCI, V_LINK],
        "sort_order": 10,
    },
    {
        "key": "kurum_ogretmen_duyuru",
        "category": CATEGORY_KURUM_OGRETMEN,
        "target_role": TARGET_INSTITUTION_ADMIN,
        "name_tr": "Kurumsal duyuru (toplu)",
        "description": "Tüm öğretmenlere ortak duyuru.",
        "content_template": (
            "Merhaba {{koc_adi}}, kurumsal duyuru:\n\n{{mesaj}}\n\n— {{kurum_adi}}"
        ),
        "variables": [V_KOC, V_MESAJ, V_KURUM],
        "allow_bulk": True,
        "allow_freeform_note": True,
        "sort_order": 20,
    },
    {
        "key": "kurum_ogretmen_karne",
        "category": CATEGORY_KURUM_OGRETMEN,
        "target_role": TARGET_INSTITUTION_ADMIN,
        "name_tr": "Performans karnesi hazır",
        "description": "Aylık öğretmen karnesi hazır olduğunda.",
        "content_template": (
            "Merhaba {{koc_adi}}, performans karneniz hazır. Panelden "
            "incelemenizi rica ederim: {{link}}"
        ),
        "variables": [V_KOC, V_LINK],
        "sort_order": 30,
    },
    {
        "key": "kurum_ogretmen_veli_guveni",
        "category": CATEGORY_KURUM_OGRETMEN,
        "target_role": TARGET_INSTITUTION_ADMIN,
        "name_tr": "Veli güveni düşüş uyarısı",
        "description": "Belirli öğrenci için veli güveni düştüğünde koça uyarı.",
        "content_template": (
            "Merhaba {{koc_adi}}, {{ogrenci_adi}} için veli güveni düşüşte "
            "({{neden}}). Veli ile temas etmenizi rica ederim."
        ),
        "variables": [V_KOC, V_OGRENCI, V_NEDEN],
        "sort_order": 40,
    },
    {
        "key": "kurum_ogretmen_toplanti",
        "category": CATEGORY_KURUM_OGRETMEN,
        "target_role": TARGET_INSTITUTION_ADMIN,
        "name_tr": "İç toplantı duyurusu",
        "description": "Öğretmen toplantısı (tarih + saat seçicili).",
        "content_template": (
            "Merhaba {{koc_adi}}, {{tarih}} {{saat}}'te {{yer}}'de iç "
            "toplantımız var. Katılımınızı bekliyoruz.\n— {{kurum_adi}}"
        ),
        "variables": [V_KOC, V_TARIH, V_SAAT, V_YER, V_KURUM],
        "requires_date": True,
        "allow_bulk": True,
        "sort_order": 50,
    },

    # ========== D. Kurum yön. → Veli (toplu, 5) ==========
    {
        "key": "kurum_veli_toplanti",
        "category": CATEGORY_KURUM_VELI,
        "target_role": TARGET_INSTITUTION_ADMIN,
        "name_tr": "Veli toplantısı duyurusu",
        "description": "Veli toplantısı duyurusu (tarih + saat + yer).",
        "content_template": (
            "Sayın {{veli_adi}}, {{tarih}} {{saat}}'te {{yer}}'de veli "
            "toplantımızı gerçekleştireceğiz. Katılımınızı bekliyoruz.\n— {{kurum_adi}}"
        ),
        "variables": [V_VELI, V_TARIH, V_SAAT, V_YER, V_KURUM],
        "requires_date": True,
        "allow_bulk": True,
        "sort_order": 10,
    },
    {
        "key": "kurum_veli_bayram",
        "category": CATEGORY_KURUM_VELI,
        "target_role": TARGET_INSTITUTION_ADMIN,
        "name_tr": "Bayram mesajı (veli)",
        "description": "Tüm velilere bayram tebriği.",
        "content_template": (
            "Sayın {{veli_adi}}, {{bayram_adi}}'nızı kutlarız. Sağlık ve "
            "huzur dolu günler dileriz.\n— {{kurum_adi}}"
        ),
        "variables": [V_VELI, V_BAYRAM, V_KURUM],
        "allow_bulk": True,
        "sort_order": 20,
    },
    {
        "key": "kurum_veli_etkinlik",
        "category": CATEGORY_KURUM_VELI,
        "target_role": TARGET_INSTITUTION_ADMIN,
        "name_tr": "Kurumsal duyuru / etkinlik",
        "description": "Veliye etkinlik veya kurumsal duyuru.",
        "content_template": (
            "Sayın {{veli_adi}}, {{baslik}}\n\n{{mesaj}}\n\n— {{kurum_adi}}"
        ),
        "variables": [V_VELI, V_BASLIK, V_MESAJ, V_KURUM],
        "allow_bulk": True,
        "allow_freeform_note": True,
        "sort_order": 30,
    },
    {
        "key": "kurum_veli_odeme",
        "category": CATEGORY_KURUM_VELI,
        "target_role": TARGET_INSTITUTION_ADMIN,
        "name_tr": "Ödeme hatırlatması",
        "description": "Borçlu veliye ödeme hatırlatma.",
        "content_template": (
            "Sayın {{veli_adi}}, {{tutar}} ₺ tutarındaki ödemenizin son "
            "tarihi {{son_tarih}}. Lütfen iletişime geçiniz.\n— {{kurum_adi}}"
        ),
        "variables": [V_VELI, V_TUTAR, V_SON_TARIH, V_KURUM],
        "sort_order": 40,
    },
    {
        "key": "kurum_veli_tatil",
        "category": CATEGORY_KURUM_VELI,
        "target_role": TARGET_INSTITUTION_ADMIN,
        "name_tr": "Tatil / kapanış duyurusu",
        "description": "Tatil veya geçici kapanış duyurusu.",
        "content_template": (
            "Sayın {{veli_adi}}, {{tarih}} tarihinde {{neden}} nedeniyle "
            "kurumumuz kapalı olacaktır. Bilgilerinize.\n— {{kurum_adi}}"
        ),
        "variables": [V_VELI, V_TARIH, V_NEDEN, V_KURUM],
        "requires_date": True,
        "allow_bulk": True,
        "sort_order": 50,
    },

    # ========== E. Kurum yön. → Öğrenci (toplu, 3) ==========
    {
        "key": "kurum_ogrenci_etkinlik",
        "category": CATEGORY_KURUM_OGRENCI,
        "target_role": TARGET_INSTITUTION_ADMIN,
        "name_tr": "Yarışma / etkinlik daveti",
        "description": "Kurumun düzenlediği etkinlik öğrencilere duyurulur.",
        "content_template": (
            "Merhaba {{ogrenci_adi}}, {{etkinlik_adi}} {{tarih}} {{saat}}'te "
            "{{yer}}'de. Seni bekliyoruz!\n— {{kurum_adi}}"
        ),
        "variables": [V_OGRENCI, V_ETKINLIK, V_TARIH, V_SAAT, V_YER, V_KURUM],
        "requires_date": True,
        "allow_bulk": True,
        "sort_order": 10,
    },
    {
        "key": "kurum_ogrenci_bayram",
        "category": CATEGORY_KURUM_OGRENCI,
        "target_role": TARGET_INSTITUTION_ADMIN,
        "name_tr": "Bayram mesajı (öğrenci)",
        "description": "Öğrencilere bayram tebriği.",
        "content_template": (
            "Merhaba {{ogrenci_adi}}, {{bayram_adi}}'n kutlu olsun! "
            "Güzel günler dileriz.\n— {{kurum_adi}}"
        ),
        "variables": [V_OGRENCI, V_BAYRAM, V_KURUM],
        "allow_bulk": True,
        "sort_order": 20,
    },
    {
        "key": "kurum_ogrenci_tatil",
        "category": CATEGORY_KURUM_OGRENCI,
        "target_role": TARGET_INSTITUTION_ADMIN,
        "name_tr": "Tatil duyurusu (öğrenci)",
        "description": "Öğrencilere tatil bildirimi.",
        "content_template": (
            "Merhaba {{ogrenci_adi}}, {{tarih}} tarihinde tatil olacağız. "
            "Tatilde de program akmaya devam ediyor; gör ayarla!\n— {{kurum_adi}}"
        ),
        "variables": [V_OGRENCI, V_TARIH, V_KURUM],
        "requires_date": True,
        "allow_bulk": True,
        "sort_order": 30,
    },

    # ========== F. Süper admin → Yönetici/Koç (5) ==========
    {
        "key": "admin_yonetici_sistem_duyuru",
        "category": CATEGORY_ADMIN_YONETICI,
        "target_role": TARGET_SUPER_ADMIN,
        "name_tr": "Sistem duyurusu",
        "description": "Önemli sistem duyurusu (manuel).",
        "content_template": "Merhaba {{koc_adi}}, {{baslik}}\n\n{{mesaj}}\n\n— Etütkoç Rotam",
        "variables": [V_KOC, V_BASLIK, V_MESAJ],
        "allow_bulk": True,
        "allow_freeform_note": True,
        "sort_order": 10,
    },
    {
        "key": "admin_yonetici_yeni_ozellik",
        "category": CATEGORY_ADMIN_YONETICI,
        "target_role": TARGET_SUPER_ADMIN,
        "name_tr": "Yeni özellik tanıtımı",
        "description": "Yeni özelliği duyurmak için.",
        "content_template": (
            "Merhaba {{koc_adi}}, {{ozellik_adi}} özelliğini yayına aldık. "
            "Detaylar: {{link}}\n— Etütkoç Rotam"
        ),
        "variables": [V_KOC, V_OZELLIK, V_LINK],
        "allow_bulk": True,
        "sort_order": 20,
    },
    {
        "key": "admin_yonetici_bakim",
        "category": CATEGORY_ADMIN_YONETICI,
        "target_role": TARGET_SUPER_ADMIN,
        "name_tr": "Bakım bildirimi",
        "description": "Planlı bakım duyurusu.",
        "content_template": (
            "Merhaba {{koc_adi}}, {{tarih}} {{baslangic}}-{{bitis}} arasında "
            "sistemde bakım çalışması yapılacak. Bilgilerinize.\n— Etütkoç Rotam"
        ),
        "variables": [V_KOC, V_TARIH, V_BASLANGIC, V_BITIS],
        "requires_date": True,
        "allow_bulk": True,
        "sort_order": 30,
    },
    {
        "key": "admin_yonetici_abonelik",
        "category": CATEGORY_ADMIN_YONETICI,
        "target_role": TARGET_SUPER_ADMIN,
        "name_tr": "Ödeme / abonelik hatırlatma",
        "description": "Abonelik yenileme hatırlatması.",
        "content_template": (
            "Merhaba {{koc_adi}}, {{paket_adi}} aboneliğinizin son ödeme "
            "tarihi {{son_tarih}}. Yenileme: {{link}}\n— Etütkoç Rotam"
        ),
        "variables": [V_KOC, V_PAKET, V_SON_TARIH, V_LINK],
        "sort_order": 40,
    },
    {
        "key": "admin_yonetici_talep_yanit",
        "category": CATEGORY_ADMIN_YONETICI,
        "target_role": TARGET_SUPER_ADMIN,
        "name_tr": "Talep yanıtı",
        "description": "Açılmış bir talebe yanıt.",
        "content_template": (
            "Merhaba {{koc_adi}}, {{talep_no}} numaralı talebiniz {{durum}}. "
            "Detaylar panelde: {{link}}\n— Etütkoç Rotam"
        ),
        "variables": [V_KOC, V_TALEP_NO, V_DURUM, V_LINK],
        "sort_order": 50,
    },

    # ========== G. Süper admin → Sistem geneli (2) ==========
    {
        "key": "admin_sistem_kvkk",
        "category": CATEGORY_ADMIN_SISTEM,
        "target_role": TARGET_SUPER_ADMIN,
        "name_tr": "KVKK / hizmet şartları güncelleme",
        "description": "Hizmet şartları/KVKK güncellemesi tüm kullanıcılara.",
        "content_template": (
            "Merhaba, Etütkoç Rotam aydınlatma metni / hizmet şartları "
            "güncellenmiştir. Lütfen okumak için tıklayın: {{link}}\n— Etütkoç Rotam"
        ),
        "variables": [V_LINK],
        "allow_bulk": True,
        "sort_order": 10,
    },
    {
        "key": "admin_sistem_bakim",
        "category": CATEGORY_ADMIN_SISTEM,
        "target_role": TARGET_SUPER_ADMIN,
        "name_tr": "Bakım / kesinti bildirimi",
        "description": "Sistem geneli bakım/kesinti duyurusu.",
        "content_template": (
            "Merhaba, {{tarih}} {{baslangic}}-{{bitis}} arası Etütkoç Rotam "
            "platformunda kısa süreli kesinti olabilir. Bilgilerinize.\n— Etütkoç Rotam"
        ),
        "variables": [V_TARIH, V_BASLANGIC, V_BITIS],
        "requires_date": True,
        "allow_bulk": True,
        "sort_order": 20,
    },
]


def main() -> int:
    reset = "--reset" in sys.argv

    with SessionLocal() as db:
        if reset:
            print("--reset: tüm seed kayıtları siliniyor...")
            keys = [t["key"] for t in SEED_TEMPLATES]
            db.query(WhatsAppTemplate).filter(WhatsAppTemplate.key.in_(keys)).delete(
                synchronize_session=False
            )
            db.commit()

        existing_keys = {
            row[0]
            for row in db.query(WhatsAppTemplate.key).all()
        }

        created = 0
        skipped = 0
        for spec in SEED_TEMPLATES:
            if spec["key"] in existing_keys:
                skipped += 1
                continue
            tmpl = WhatsAppTemplate(
                key=spec["key"],
                category=spec["category"],
                target_role=spec.get("target_role", "any"),
                name_tr=spec["name_tr"],
                description=spec.get("description", ""),
                content_template=spec["content_template"],
                variables_json=json.dumps(spec.get("variables", []), ensure_ascii=False),
                requires_date=bool(spec.get("requires_date", False)),
                allow_bulk=bool(spec.get("allow_bulk", False)),
                allow_freeform_note=bool(spec.get("allow_freeform_note", False)),
                sort_order=int(spec.get("sort_order", 100)),
                is_active=True,
            )
            db.add(tmpl)
            created += 1

        db.commit()

    print(
        f"WhatsApp şablonları seed: created={created} skipped={skipped} "
        f"toplam_spec={len(SEED_TEMPLATES)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
