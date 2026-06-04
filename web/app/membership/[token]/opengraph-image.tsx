import { ImageResponse } from "next/og";

/**
 * /membership/[token] WhatsApp link önizleme görseli (1200×630 PNG).
 *
 * Kare logo yerine markalı geniş banner → WhatsApp kartı sigortam.net kalitesinde
 * görünür. Türkçe metin GÖRSELE konmaz (font riski); amaç/değer metni OG
 * title+description'da (WhatsApp kendi fontuyla render eder) + mesaj gövdesinde
 * taşınır. Görsel = marka (logo PNG, glyph'ler piksel olduğu için font gerekmez)
 * + cyan marka gradyanı.
 */
export const alt = "ETÜTKOÇ Rotam";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const LOGO = "https://rotam.etutkoc.com/etutkoc-logo.png";

export default async function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #0e7490 0%, #155e75 55%, #134e4a 100%)",
          fontFamily: "sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            background: "white",
            borderRadius: 44,
            padding: "84px 110px",
            boxShadow: "0 30px 70px rgba(0,0,0,0.28)",
          }}
        >
          <div
            style={{
              display: "flex",
              width: 520,
              height: 124,
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element -- ImageResponse içi */}
            <img
              src={LOGO}
              alt="ETÜTKOÇ Rotam"
              width={520}
              height={124}
              style={{ objectFit: "contain" }}
            />
          </div>
          <div
            style={{
              marginTop: 24,
              display: "flex",
              fontSize: 30,
              letterSpacing: 3,
              color: "#0e7490",
              fontWeight: 600,
            }}
          >
            rotam.etutkoc.com
          </div>
        </div>
      </div>
    ),
    { ...size },
  );
}
