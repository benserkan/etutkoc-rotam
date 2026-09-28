"use client";

import * as React from "react";
import { QRCodeSVG } from "qrcode.react";
import { Download, Printer } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";

/**
 * Toplu öğrenci kaydı sonrası GİRİŞ KARTLARI (2026-09-28).
 *
 * Geçici şifreler sunucuda saklanmaz, yalnız kayıt yanıtında bir kez döner.
 * Kurum/koç bu şifreleri sınıfta dağıtabilsin diye iki çıktı:
 *  - "Giriş kartlarını yazdır": A4'e 8 kesilebilir kart (ad, sınıf/şube,
 *    e-posta, geçici şifre, giriş adresi + QR, uygulama bilgisi)
 *  - "Excel'e indir": aynı bilgiler; Türkçe Excel'in doğrudan açtığı
 *    noktalı virgüllü, BOM'lu CSV
 * İkisi de tamamen tarayıcıda üretilir — şifre hiçbir yere gönderilmez.
 */

export type LoginCardStudent = {
  full_name: string;
  email: string;
  grade_label: string;
  class_group?: string | null;
  temp_password: string;
};

const LOGIN_HOST = "rotam.etutkoc.com";
const LOGIN_URL = `https://${LOGIN_HOST}/login`;
const APP_NOTE = "Android telefonda Google Play'de “ETÜTKOÇ Rotam” uygulamasını da kullanabilirsin.";

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function classLine(s: LoginCardStudent): string {
  return [s.grade_label && s.grade_label !== "—" ? s.grade_label.replace("🎓 ", "") : "", s.class_group ?? ""]
    .filter(Boolean)
    .join(" · ");
}

function buildHtml(students: LoginCardStudent[], qrSvg: string): string {
  const cards = students
    .map(
      (s) => `
    <div class="card">
      <div class="head">
        <span class="brand">etütkoç <b>·</b> rotam</span>
        <span class="tag">Giriş kartı</span>
      </div>
      <div class="name">${esc(s.full_name)}</div>
      ${classLine(s) ? `<div class="cls">${esc(classLine(s))}</div>` : ""}
      <div class="body">
        <div class="fields">
          <div class="lbl">Giriş adresi</div>
          <div class="val">${LOGIN_HOST}</div>
          <div class="lbl">E-posta</div>
          <div class="val mono">${esc(s.email)}</div>
          <div class="lbl">Geçici şifre</div>
          <div class="pw">${esc(s.temp_password)}</div>
        </div>
        <div class="qr">${qrSvg}<div class="qrcap">Tara, giriş yap</div></div>
      </div>
      <div class="foot">İlk girişte kendi şifreni belirleyeceksin. Bu kartı kimseyle paylaşma.<br/>${esc(APP_NOTE)}</div>
    </div>`,
    )
    .join("");

  return `<!doctype html><html lang="tr"><head><meta charset="utf-8"/>
<title>Öğrenci giriş kartları</title>
<style>
  @page { size: A4; margin: 10mm; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif; color: #0f172a; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0; }
  .card { border: 1px dashed #94a3b8; padding: 5mm 6mm; height: 68mm; overflow: hidden;
          break-inside: avoid; page-break-inside: avoid; display: flex; flex-direction: column; }
  .head { display: flex; justify-content: space-between; align-items: center; }
  .brand { font-weight: 700; color: #0e7490; font-size: 12pt; }
  .brand b { color: #d97706; }
  .tag { font-size: 7.5pt; text-transform: uppercase; letter-spacing: .06em; color: #64748b; }
  .name { font-size: 13pt; font-weight: 700; margin-top: 2mm; overflow-wrap: anywhere; }
  .cls { font-size: 9pt; color: #475569; }
  .body { display: flex; gap: 4mm; margin-top: 2mm; flex: 1; min-height: 0; }
  .fields { flex: 1; min-width: 0; }
  .lbl { font-size: 7pt; text-transform: uppercase; letter-spacing: .05em; color: #64748b; margin-top: 1.2mm; }
  .val { font-size: 9.5pt; overflow-wrap: anywhere; }
  .mono { font-family: "SF Mono", Consolas, monospace; }
  .pw { font-family: "SF Mono", Consolas, monospace; font-size: 14pt; font-weight: 700; letter-spacing: .08em;
        background: #fef3c7; color: #78350f; padding: .6mm 2mm; border-radius: 1.5mm; display: inline-block; }
  .qr { width: 24mm; text-align: center; flex-shrink: 0; }
  .qr svg { width: 24mm; height: 24mm; }
  .qrcap { font-size: 6.5pt; color: #64748b; margin-top: .5mm; }
  .foot { font-size: 7pt; color: #475569; border-top: 1px solid #e2e8f0; padding-top: 1.2mm; margin-top: 1.5mm; }
  .print-color { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
</style></head>
<body class="print-color"><div class="grid">${cards}</div></body></html>`;
}

function csvCell(v: string): string {
  return /[";\n\r]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
}

export function LoginCardsActions({ students }: { students: LoginCardStudent[] }) {
  const qrRef = React.useRef<HTMLDivElement>(null);

  function print() {
    const qrSvg = qrRef.current?.innerHTML ?? "";
    try {
      const frame = document.createElement("iframe");
      frame.setAttribute("aria-hidden", "true");
      frame.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;";
      document.body.appendChild(frame);
      const doc = frame.contentDocument;
      if (!doc) throw new Error("no_frame");
      doc.open();
      doc.write(buildHtml(students, qrSvg));
      doc.close();
      window.setTimeout(() => {
        try {
          frame.contentWindow?.focus();
          frame.contentWindow?.print();
        } catch {
          toast.error("Yazdırma penceresi açılamadı.");
        }
        window.setTimeout(() => frame.remove(), 60_000);
      }, 300);
    } catch {
      toast.error("Giriş kartları hazırlanamadı.");
    }
  }

  function downloadCsv() {
    const header = ["Ad Soyad", "Sınıf", "Şube", "E-posta", "Geçici şifre", "Giriş adresi"];
    const rows = students.map((s) => [
      s.full_name,
      s.grade_label && s.grade_label !== "—" ? s.grade_label.replace("🎓 ", "") : "",
      s.class_group ?? "",
      s.email,
      s.temp_password,
      LOGIN_HOST,
    ]);
    const text = [header, ...rows].map((r) => r.map(csvCell).join(";")).join("\r\n");
    const blob = new Blob(["﻿" + text], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ogrenci-giris-bilgileri-${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 5_000);
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button type="button" onClick={print} data-testid="login-cards-print">
        <Printer className="size-4" aria-hidden />
        Giriş kartlarını yazdır
      </Button>
      <Button type="button" variant="outline" onClick={downloadCsv} data-testid="login-cards-csv">
        <Download className="size-4" aria-hidden />
        Excel&apos;e indir
      </Button>
      {/* QR yalnız yazdırma çıktısına kopyalanır; ekranda görünmez. */}
      <div ref={qrRef} className="hidden" aria-hidden>
        <QRCodeSVG value={LOGIN_URL} size={160} level="M" />
      </div>
    </div>
  );
}
