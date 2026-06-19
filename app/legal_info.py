"""Tek kaynak şirket / satıcı bilgileri.

Mesafeli satış sözleşmesi, iade-iptal koşulları, kullanım şartları, KVKK ve
gizlilik sayfaları ile footer BU sözlükten beslenir (tek yerde düzenle, her yere
yansır). iyzico üye işyeri başvurusu + Mesafeli Sözleşmeler Yönetmeliği zorunlu
satıcı bilgilerini içerir.

DOLDURULACAK işaretli alanları ticaret sicil / vergi levhası / imza sirküsünden
gerçek değerlerle değiştir. `is_complete()` False döndürdüğü sürece sayfalarda
"taslak" uyarısı görünür.
"""

from __future__ import annotations

# Henüz girilmemiş resmi bilgi için sentinel. Gerçek değerle değiştirilince
# sayfadaki uyarı otomatik kalkar.
TBD = "DOLDURULACAK"

COMPANY: dict[str, str] = {
    # --- Kimlik (Trabzon Ticaret Sicili Tasdiknamesi, 17.06.2026) ---
    "unvan": "ETÜTKOÇ Akademi Kişisel Gelişim Özel Eğitim ve Öğretim "
             "Hizmetleri Limited Şirketi",
    "marka": "ETÜTKOÇ Rotam",
    "website": "https://rotam.etutkoc.com",
    # --- İletişim ---
    "email": "destek@etutkoc.com",
    "satis_email": "rotam@etutkoc.com",
    "telefon": "+90 505 673 85 61",
    "adres": "İskenderpaşa Mah. Gazipaşa Cad. Timurcıoğlu Apartmanı "
             "No: 12 / İç Kapı No: 6, Ortahisar / Trabzon",
    # --- Resmi tescil (Ticaret Sicili Tasdiknamesi) ---
    "mersis": "0381113961000001",
    "vergi_dairesi": "Karadeniz Vergi Dairesi (Trabzon)",
    "vergi_no": "3811139610",
    "ticaret_sicil_no": "26268 (Trabzon)",
    "kep": "",                 # opsiyonel KEP adresi (yoksa boş bırak)
}


def is_complete() -> bool:
    """Resmi tescil bilgilerinin hepsi girildi mi? (footer/uyarı için)."""
    required = ("telefon", "adres", "mersis", "vergi_dairesi", "vergi_no",
                "ticaret_sicil_no")
    return all(COMPANY.get(k) and COMPANY[k] != TBD for k in required)
