/**
 * Koç rehberi içeriği — TEK KAYNAK: coach-guide-content.json
 * (aynı dosyayı scripts/generate_guide_audio.py TTS üretimi için okur).
 *
 * shot-boxes.json, scripts/capture_guide_shots.py tarafından ÜRETİLİR:
 * her ekran görüntüsündeki hedef öğelerin (buton, panel...) yüzde
 * koordinatları. Ekran görüntüleri 1440×900 sabit görünümde çekilir —
 * oynatıcıdaki sahne alanı aynı oranda (aspect 16/10) olduğundan yüzde
 * kutuları birebir oturur.
 */
import rawContent from "./coach-guide-content.json";
import rawStudentContent from "./student-guide-content.json";
import rawParentContent from "./parent-guide-content.json";
import rawBoxes from "./shot-boxes.json";

export interface GuideBox {
  x: number; // % (0-100)
  y: number;
  w: number;
  h: number;
}

export interface GuideStepDef {
  caption: string;
  shot: string | null; // shots/{shot}.png — null = avatar sahnesi
  target: string | null; // shot-boxes.json'daki vurgu kutusu anahtarı
  click: boolean; // imleç animasyonu hedefe gidip tıklasın mı
  /** true → sahne vurgu kutusuna yumuşakça yakınlaşır (zoom in/out) */
  zoom?: boolean;
}

export interface GuideActionDef {
  label: string;
  href: string;
  checkKey: string; // backend checklist anahtarı
  doneLabel: string;
  /** "Nereden, hangi düğmeyle" yol tarifi — kart üzerinde daima görünür */
  hint: string;
  /** true → uygulama İSTEĞE BAĞLI: kapı kurmaz, yalnız "istersen dene" önerisi */
  optional?: boolean;
}

export interface GuideChapterDef {
  key: string;
  title: string;
  subtitle: string;
  steps: GuideStepDef[];
  action: GuideActionDef | null;
}

export interface CoachGuideContent {
  guideKey: string;
  narrator: string;
  chapters: GuideChapterDef[];
}

export const COACH_GUIDE = rawContent as CoachGuideContent;
export const STUDENT_GUIDE = rawStudentContent as CoachGuideContent;
export const PARENT_GUIDE = rawParentContent as CoachGuideContent;

/** guide_key → içerik (oynatıcı + rehber sayfası buradan çözer). */
export const GUIDES: Record<string, CoachGuideContent> = {
  [COACH_GUIDE.guideKey]: COACH_GUIDE,
  [STUDENT_GUIDE.guideKey]: STUDENT_GUIDE,
  [PARENT_GUIDE.guideKey]: PARENT_GUIDE,
};

export const GUIDE_STATIC_BASE = "/static/guide";

/**
 * Varlık sürümü — ses/ekran dosyaları AYNI URL üstüne yeniden üretildiğinde
 * tarayıcı önbelleği bayat kalmasın diye. MP3/PNG yeniden üretince ARTIR
 * (aksi halde kullanıcı eski sesi duyar — 2026-07-23 saha bulgusu).
 */
const GUIDE_ASSET_VERSION = "20260727b";

export const GUIDE_AVATAR_SRC = `${GUIDE_STATIC_BASE}/rota-avatar.png?v=${GUIDE_ASSET_VERSION}`;

export function shotSrc(shot: string): string {
  return `${GUIDE_STATIC_BASE}/shots/${shot}.png?v=${GUIDE_ASSET_VERSION}`;
}

export function audioSrc(chapterKey: string, stepIdx: number): string {
  return `${GUIDE_STATIC_BASE}/audio/${chapterKey}/${stepIdx}.mp3?v=${GUIDE_ASSET_VERSION}`;
}

type BoxMap = Record<string, { targets?: Record<string, GuideBox> }>;

export function boxFor(shot: string | null, target: string | null): GuideBox | null {
  if (!shot || !target) return null;
  const entry = (rawBoxes as BoxMap)[shot];
  const box = entry?.targets?.[target];
  return box ?? null;
}

/** Sesin yokluğunda altyazı süresi tahmini (okuma hızı ~ 2.6 kelime/sn + pay). */
export function estimateDurationMs(caption: string): number {
  const words = caption.trim().split(/\s+/).length;
  return Math.max(4000, Math.round((words / 2.4) * 1000) + 1200);
}
