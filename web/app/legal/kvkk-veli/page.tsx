import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";

/**
 * /legal/kvkk-veli — Veli Aydınlatma Metni.
 *
 * Jinja kaynağı: app/templates/legal/kvkk_parent.html (104 satır).
 * İçerik statik; Next.js'te ayrı page olarak sunulur (KVKK metni
 * standalone — parent layout dışı).
 */
export const metadata = { title: "Veli Aydınlatma Metni — ETÜTKOÇ Rotam" };

export default function ParentKvkkPage() {
  return (
    <div className="min-h-screen bg-muted/20 py-8 px-4">
      <div className="max-w-3xl mx-auto">
        <Card className="border-border shadow-sm">
          <CardContent className="p-8">
            <h1 className="text-2xl font-bold tracking-tight font-display mb-1">
              Veli Aydınlatma Metni
            </h1>
            <p className="text-sm text-muted-foreground mb-6">
              6698 Sayılı KVKK Çerçevesinde Veri İşleme
            </p>

            <div className="space-y-5 text-sm leading-relaxed text-foreground/90">
              <Section title="1. Veri Sorumlusu">
                ETÜTKOÇ Rotam (bundan sonra &ldquo;Platform&rdquo; olarak
                anılacaktır) tarafından, 6698 sayılı Kişisel Verilerin Korunması
                Kanunu (&ldquo;KVKK&rdquo;) kapsamında veri sorumlusu sıfatıyla,
                veli olarak sizin ve bağlantılı öğrencinin kişisel verileri
                aşağıda açıklanan çerçevede işlenmektedir. Sistemi kullanan
                eğitim koçunuz/öğretmeniniz, ilgili verilerin işlenmesinde
                birlikte veri sorumlusu konumunda olabilir.
              </Section>

              <Section title="2. İşlenen Kişisel Veriler">
                <ul className="list-disc pl-5 space-y-1.5">
                  <li>
                    <strong>Veliye ait:</strong> Ad-soyad, e-posta adresi,
                    (isteğe bağlı olarak) telefon numarası, IP adresi, oturum
                    kayıtları, bildirim tercihleri.
                  </li>
                  <li>
                    <strong>Öğrenciye ait, veli ile paylaşılan:</strong> Görev
                    tamamlama oranı, görev tipi dağılımı, çalışma istikrarı
                    (streak), tahmini ilerleme, öğretmenin sizinle özel olarak
                    paylaştığı notlar.
                  </li>
                  <li>
                    <strong>Veli ile paylaşılmayan:</strong> Deneme net
                    sayıları, ham puanlar, konu bazında doğru-yanlış oranları,
                    öğrenci-öğretmen arasındaki özel mesajlar. Bu veriler
                    sistemde tutulsa dahi veli arayüzünde gösterilmez.
                  </li>
                </ul>
              </Section>

              <Section title="3. İşleme Amaçları">
                <p>Kişisel verileriniz aşağıdaki amaçlarla işlenmektedir:</p>
                <ul className="list-disc pl-5 space-y-1.5 mt-2">
                  <li>
                    Velinin, öğrencisinin haftalık çalışma programını ve
                    ilerlemesini takip etmesini sağlamak.
                  </li>
                  <li>
                    Velinin tercihine göre günlük özet, haftalık rapor ve
                    önemli durum bildirimlerini e-posta ve/veya WhatsApp
                    üzerinden iletmek.
                  </li>
                  <li>
                    Hesap güvenliğini sağlamak, oturum geçmişini izlemek,
                    kötüye kullanımı önlemek.
                  </li>
                  <li>
                    Yasal yükümlülükleri yerine getirmek (KVKK ve ilgili
                    mevzuat).
                  </li>
                </ul>
              </Section>

              <Section title="4. Aktarım">
                Kişisel verileriniz; (i) bildirim gönderim altyapısı için
                kullanılan üçüncü taraf e-posta sağlayıcıları ve Meta WhatsApp
                Cloud API hizmetine yalnızca size mesaj iletmek için gerekli
                olan asgari ölçüde, (ii) yasal zorunluluk halinde yetkili kamu
                kurumlarına aktarılabilir. Verileriniz pazarlama amaçlı üçüncü
                kişilerle paylaşılmaz.
              </Section>

              <Section title="4.1 İletişim Kanalları">
                Bilgilendirme mesajları, davet kabulü sırasında veya{" "}
                <strong className="text-foreground">Bildirim Tercihleri</strong>
                {" "}sayfasından seçtiğiniz iki kanaldan (e-posta ve/veya
                WhatsApp) iletilir. Her bildirim türünü her iki kanal için ayrı
                ayrı açıp kapatabilirsiniz. WhatsApp mesajları, kişisel
                numaranıza yalnızca onaylanmış şablonlarla gönderilir; içerik
                Meta&apos;nın gizlilik koşullarına tabidir.
              </Section>

              <Section title="4.2 18 Yaş Altı Çocuk için WhatsApp">
                Çocuğunuzun (öğrenci kullanıcısının) WhatsApp üzerinden mesaj
                alması için <strong className="text-foreground">veli
                onayınız</strong> zorunludur. Davet kabul ekranında veya
                Bildirim Tercihleri sayfasında <em>&ldquo;Çocuğum WhatsApp
                mesajı alabilir&rdquo;</em> seçeneğini işaretlemezseniz, çocuğa
                doğrudan WhatsApp mesajı gönderilmez. Bilgilendirme yalnızca
                veli e-postası / WhatsApp&apos;ı veya panel üzerinden devam eder.
              </Section>

              <Section title="4.3 İletişim İptali">
                Her bildirim tipini ayrı ayrı{" "}
                <strong className="text-foreground">istediğiniz zaman</strong>{" "}
                Bildirim Tercihleri sayfasından kapatabilir, e-postaların
                altındaki &ldquo;tek tıkla kapat&rdquo; bağlantısı ile tüm
                bildirimleri durdurabilir veya WhatsApp gelen kutunuzdan
                &ldquo;DUR&rdquo; yazarak yalnızca WhatsApp bildirimlerini
                sonlandırabilirsiniz.
              </Section>

              <Section title="5. Saklama Süresi">
                Veli hesabı aktif olduğu sürece veriler işlenir. Hesap
                silindikten sonra kimliği belirsiz hale getirilemeyen kayıtlar
                (bildirim günlüğü vb.) yasal saklama süresi sonunda silinir.
              </Section>

              <Section title="6. Haklarınız">
                <p>KVKK 11. madde kapsamında:</p>
                <ul className="list-disc pl-5 space-y-1.5 mt-2">
                  <li>Verilerinizin işlenip işlenmediğini öğrenme,</li>
                  <li>İşlenen verileriniz hakkında bilgi talep etme,</li>
                  <li>Düzeltilmesini, silinmesini veya yok edilmesini isteme,</li>
                  <li>Otomatik sistemlerle yapılan analizlere itiraz etme,</li>
                  <li>
                    Bildirimlere konu olan kanal/iletişim tercihinizi her zaman
                    değiştirme
                  </li>
                </ul>
                <p className="mt-2">
                  haklarına sahipsiniz. Talepleriniz için sizi davet eden
                  eğitim koçunuza ya da Platform üzerindeki &ldquo;Bildirim
                  Tercihleri&rdquo; sayfasına ulaşabilirsiniz.
                </p>
              </Section>

              <Section title="7. Onay">
                Davet kabulü sırasında &ldquo;Aydınlatma metnini okudum,
                anladım ve kabul ediyorum&rdquo; kutusunu işaretlemeniz, bu
                metnin tarafınızca okunduğu ve verilerin işlenmesine rıza
                gösterildiğine dair açık irade beyanı olarak kabul edilecektir.
              </Section>

              <p className="text-xs text-muted-foreground italic pt-4 border-t border-border">
                Not: Bu metin, hukuki danışmanlık niteliği taşımaz. Kurumsal
                kullanımda mevzuat değişiklikleri ve sözleşme özelinde gözden
                geçirilmesi gerekebilir.
              </p>
            </div>

            <div className="mt-6 pt-4 border-t border-border flex flex-wrap items-center justify-between gap-2 text-sm">
              <Link
                href="/parent"
                className="inline-flex items-center gap-1 text-[#117A86] hover:underline"
              >
                <ArrowLeft className="size-4" aria-hidden />
                Geri dön
              </Link>
              <span className="text-xs text-muted-foreground">
                Son güncelleme: 2026-05-30
              </span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h2 className="text-base font-semibold text-foreground mb-2">{title}</h2>
      <div>{children}</div>
    </section>
  );
}
