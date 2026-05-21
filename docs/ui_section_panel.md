# Standart Bölüm Panel Tasarımı

**Karar tarihi:** 2026-05-18
**Macro:** `app/templates/_macros/section_panel.html`
**Karar sebebi:** Admin sayfalarındaki kartlar beyaz arkaplanda yan yana duruyordu, hangisinin hangi bölüme ait olduğu belli olmuyordu. ⓘ tooltip ile gizli açıklamalar mobilde çalışmıyordu.

---

## Tasarım dili (bundan sonra her admin sayfasında)

Her admin sayfası **bölümlere** ayrılır, her bölüm bir **panel**dir:

```
┌──────────────────────────────────────────────────────────────┐
│ ░ KATEGORİ (uppercase, küçük, renkli)                         │ ← renkli üst şerit
│ 💰 Bölüm Başlığı (büyük, koyu)               [Aksiyon →]     │   (border-b-2)
│ Açıklama metni — ne olduğunu + nasıl kullanılacağını anlatır │
├──────────────────────────────────────────────────────────────┤
│  açık gri arkaplan (bg-slate-50/60) üzerinde beyaz iç kartlar│
│  ┌────────┐  ┌────────┐  ┌────────┐                          │
│  │ kart 1 │  │ kart 2 │  │ kart 3 │                          │
│  └────────┘  └────────┘  └────────┘                          │
└──────────────────────────────────────────────────────────────┘
```

**Anahtar prensipler:**
- ⓘ tooltip ile gizli açıklama YASAK — her zaman görünür metin
- Her bölüm rounded-xl beyaz panel + shadow-sm → sınırlar net
- İç kartlar açık gri zeminde otursun → beyaz iç kartlar görsel olarak öne çıkar
- Renkli üst şerit + kategori etiketi + ikon = bölüm türünü hemen anlamak

---

## Renk paleti

| Renk | Kullanım alanı |
|------|---------------|
| `indigo` | Genel bakış · varsayılan · hesap özetleri |
| `emerald` | Satış · ticari · başarı |
| `rose` | Müşteri sağlığı · erken uyarı · kritik |
| `amber` | Sessizleşme · dikkat · uyarı |
| `slate` | Sistem · altyapı · nötr |
| `violet` | Audit · olaylar · kayıt |
| `cyan` | Trend · zaman serisi · grafik |
| `blue` | Karşılaştırma · analiz · A/B |
| `purple` | Bağımsız öğretmen · özel kategori |

---

## Kullanım

### En basit hâli

```jinja
{% from "_macros/section_panel.html" import panel %}

{% call panel(
    color='emerald',
    title='Ticari & Ödemeler',
) %}
  <p>İçerik buraya — istediğin HTML.</p>
{% endcall %}
```

### Tam parametreli

```jinja
{% call panel(
    color='emerald',
    category='Satış · Ödemeler · CRM',
    icon='💰',
    title='Ticari & Ödemeler',
    description='Günlük satış ve ödeme operasyonları için kısayollar. Aşağıdaki her kart bir alt-pano açar.',
    action_url='/admin/security-monitor/revenue',
    action_label='Ticari panoyu aç',
) %}
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
    <a href="..." class="p-3 rounded-lg bg-white border border-indigo-200 hover:border-indigo-400 hover:shadow-sm transition">
      <div class="text-xl">📊</div>
      <div class="text-sm font-medium text-slate-900 mt-1">İç Kart Başlık</div>
      <div class="text-xs text-slate-500">Kısa alt metin</div>
    </a>
  </div>
{% endcall %}
```

### Tablo / liste bölümleri (iç padding yok)

Tablo veya `<ul>` listesi gibi kendi padding'i olan içerikler için iç bg'yi kaldır:

```jinja
{% call panel(
    color='violet',
    category='Sistem Olayları',
    icon='📜',
    title='Son Audit Olayları',
    description='Sistemde yapılan son işlemler.',
    action_url='/admin/audit',
    action_label='Tümünü gör',
    inner_bg='none'
) %}
  <table class="w-full text-xs">
    {# ... #}
  </table>
{% endcall %}
```

---

## Tüm parametreler

| Parametre | Varsayılan | Açıklama |
|-----------|-----------|----------|
| `color` | `'indigo'` | Tailwind renk paleti adı (üst şerit + kategori + aksiyon link rengi) |
| `category` | `None` | Küçük uppercase etiket (örn. "Satış · Ödemeler · CRM") |
| `icon` | `None` | Başlık önündeki emoji |
| `title` | `''` | Ana başlık (zorunlu) |
| `description` | `None` | Başlık altında **her zaman görünür** açıklama (HTML kabul eder, `\|safe` filtresi otomatik) |
| `action_url` | `None` | Sağ üst köşedeki linkin URL'i |
| `action_label` | `None` | Sağ üst köşedeki linkin metni |
| `inner_padding` | `'p-4'` | İç alan padding sınıfı |
| `inner_bg` | `'bg-slate-50/60'` | İç alan arkaplanı. `'none'` verirse arkaplan kaldırılır (tablo için) |
| `margin_bottom` | `'mb-6'` | Panel altı boşluk |

---

## Negatif / olmaması gerekenler

- ❌ **Çıplak `<h2>` + `<div class="grid">` pattern'i** — bölüm sınırı yok, hangi başlığın hangi grid'e ait olduğu belirsiz
- ❌ **ⓘ tooltip ile gizli açıklama** — mobilde hover olmaz
- ❌ **Tüm sayfa boyunca beyaz arkaplan** — kart hiyerarşisi okunmaz
- ❌ **`text-sm font-semibold text-slate-700 uppercase tracking-wider` h2** — küçük, ayrıştırıcı değil; macro `text-base font-semibold text-slate-900` kullanıyor

---

## Uygulandığı sayfalar

- ✅ `/admin` (dashboard.html) — 5 bölüm panel
- ✅ `/admin/security-monitor/activity` — 7 bölüm panel
- ✅ Drill partial'lar (`_activity_drill_users`, `_activity_drill_heatmap`)
- ⏭ Yeni admin sayfaları → bu macro'yu kullan

---

## Migration ipucu

Eski pattern:
```jinja
<div class="mb-2 flex items-baseline justify-between">
  <h2 class="text-sm font-semibold text-slate-700 uppercase tracking-wider">💰 Ticari</h2>
  <a href="..." class="text-xs">Aç →</a>
</div>
<div class="grid grid-cols-X gap-3 mb-6">
  {# kartlar — açıklamasız #}
</div>
```

Yeni pattern:
```jinja
{% from "_macros/section_panel.html" import panel %}
{% call panel(color='emerald', icon='💰', title='Ticari', description='...', action_url='...', action_label='Aç') %}
  <div class="grid grid-cols-X gap-3">
    {# kartlar #}
  </div>
{% endcall %}
```
