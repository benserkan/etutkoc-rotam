import { Ionicons } from "@expo/vector-icons";
import { createAudioPlayer, setAudioModeAsync, type AudioPlayer } from "expo-audio";
import * as React from "react";
import {
  Animated,
  Image,
  Pressable,
  ScrollView,
  Text,
  View,
} from "react-native";

import {
  audioUrl,
  boxFor,
  estimateDurationMs,
  GUIDE_AVATAR_URL,
  shotUrl,
  type GuideChapterDef,
  type GuideContent,
  type GuideProgressAction,
  type GuideResponse,
} from "@/lib/guide";

/**
 * Mobil rehber oynatıcısı — web guide-player'ın RN portu (sadeleştirilmiş).
 *
 * Sahne: 1440×900 oranlı ekran görüntüsü + yüzde-koordinatlı vurgu kutusu +
 * zoom (kutuya yakınlaşma) + altyazı + Türkçe seslendirme (backend /static
 * MP3 akışı; yüklenemezse süre tahmini). Adım bitince sunucuya `watch`
 * yazılır → oturum düşse de "Kaldığın yerden devam".
 *
 * KURAL (web saha düzeltmesi 8): ses effect'i yalnız kimlik bağımlılığı
 * taşır [playing, chapterKey, stepIdx]; ilerletme/işaretleme ref'lerden
 * okunur — aksi halde her render sesi baştan başlatır.
 */

interface Props {
  content: GuideContent;
  guide: GuideResponse;
  onProgress: (body: {
    action: GuideProgressAction;
    chapter?: string;
    step?: number;
  }) => void;
}

const SCENE_ASPECT = 1440 / 900;

export function GuidePlayer({ content, guide, onProgress }: Props) {
  const chapters = content.chapters;
  const doneSet = React.useMemo(
    () => new Set(guide.state.chapters_done),
    [guide.state.chapters_done],
  );

  const initialChapterIdx = React.useMemo(() => {
    const cur = guide.state.current_chapter;
    if (cur) {
      const i = chapters.findIndex((c) => c.key === cur);
      if (i >= 0) return i;
    }
    const firstOpen = chapters.findIndex((c) => !doneSet.has(c.key));
    return firstOpen >= 0 ? firstOpen : 0;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount'ta bir kez
  }, []);

  const [chapterIdx, setChapterIdx] = React.useState(initialChapterIdx);
  const [stepIdx, setStepIdx] = React.useState(0);
  const [playing, setPlaying] = React.useState(false);
  const [finished, setFinished] = React.useState(false); // bölüm sonu kartı
  const [guideDone, setGuideDone] = React.useState(
    guide.state.status === "completed",
  );

  const chapter = chapters[Math.min(chapterIdx, chapters.length - 1)];
  const step = chapter.steps[Math.min(stepIdx, chapter.steps.length - 1)];

  // İzlenen adımlar (sunucudan tohum + yerel güncelleme)
  const [played, setPlayed] = React.useState<Record<string, Set<number>>>(() => {
    const out: Record<string, Set<number>> = {};
    for (const [k, arr] of Object.entries(guide.state.steps_watched ?? {})) {
      out[k] = new Set(arr);
    }
    return out;
  });
  const playedRef = React.useRef(played);
  playedRef.current = played;

  const startedRef = React.useRef(guide.state.status !== "not_started");

  const markPlayed = React.useCallback(
    (chKey: string, idx: number) => {
      const cur = playedRef.current[chKey];
      if (cur?.has(idx)) return;
      setPlayed((p) => {
        const next = { ...p };
        next[chKey] = new Set(next[chKey] ?? []);
        next[chKey].add(idx);
        return next;
      });
      onProgress({ action: "watch", chapter: chKey, step: idx });
    },
    [onProgress],
  );

  // Adım bitti → işaretle + ilerle (ses effect'i ref üzerinden çağırır)
  const advanceRef = React.useRef<() => void>(() => {});
  advanceRef.current = () => {
    markPlayed(chapter.key, stepIdx);
    if (stepIdx < chapter.steps.length - 1) {
      setStepIdx((i) => i + 1);
    } else {
      setPlaying(false);
      setFinished(true);
    }
  };

  // ---- Ses motoru (dar bağımlılık + ref'ler) ----
  const playerRef = React.useRef<AudioPlayer | null>(null);
  React.useEffect(() => {
    if (!playing) return;
    let dead = false;
    let advanced = false;
    let started = false;
    let iv: ReturnType<typeof setInterval> | null = null;
    let fallback: ReturnType<typeof setTimeout> | null = null;

    const finish = () => {
      if (dead || advanced) return;
      advanced = true;
      cleanup();
      advanceRef.current();
    };
    const cleanup = () => {
      if (iv) clearInterval(iv);
      if (fallback) clearTimeout(fallback);
      const p = playerRef.current;
      playerRef.current = null;
      if (p) {
        try {
          p.pause();
          p.remove();
        } catch {
          /* yoksay */
        }
      }
    };

    const cap = chapter.steps[stepIdx]?.caption ?? "";
    void setAudioModeAsync({ playsInSilentMode: true }).catch(() => {});
    try {
      const p = createAudioPlayer({ uri: audioUrl(chapter.key, stepIdx) });
      playerRef.current = p;
      p.play();
      iv = setInterval(() => {
        const cur = playerRef.current;
        if (!cur) return;
        if (cur.playing) {
          started = true;
          return;
        }
        if (started) finish();
      }, 500);
      // Ses hiç başlamazsa (ağ/dosya sorunu) → tahmini süreyle ilerle
      fallback = setTimeout(() => {
        if (!started) {
          fallback = setTimeout(finish, estimateDurationMs(cap));
        }
      }, 4000);
    } catch {
      fallback = setTimeout(finish, estimateDurationMs(cap));
    }

    return () => {
      dead = true;
      cleanup();
    };
  }, [playing, chapter.key, stepIdx, chapter.steps]);

  // Bölüm değişince adım/kart durumu sıfırlanır
  const openChapter = (idx: number) => {
    setChapterIdx(idx);
    setStepIdx(0);
    setFinished(false);
    setPlaying(false);
  };

  const play = () => {
    if (!startedRef.current) {
      startedRef.current = true;
      onProgress({ action: "start" });
    }
    setFinished(false);
    setPlaying(true);
  };

  const chapterPlayed = played[chapter.key] ?? new Set<number>();
  const firstUnwatched = React.useMemo(() => {
    for (let i = 0; i < chapter.steps.length; i++) {
      if (!chapterPlayed.has(i)) return i;
    }
    return chapter.steps.length - 1;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapter.key, played]);

  const completeChapter = () => {
    onProgress({ action: "chapter_done", chapter: chapter.key });
    if (chapterIdx < chapters.length - 1) {
      openChapter(chapterIdx + 1);
    } else {
      setGuideDone(true);
    }
  };

  if (guideDone) {
    return (
      <View className="items-center gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-8">
        <Ionicons name="checkmark-circle" size={44} color="#059669" />
        <Text className="text-center text-lg font-bold text-emerald-800">
          Rehberi tamamladın!
        </Text>
        <Text className="text-center text-sm text-emerald-700">
          İstediğin bölüme yukarıdan her zaman geri dönebilirsin.
        </Text>
        <Pressable
          onPress={() => setGuideDone(false)}
          className="rounded-xl border border-emerald-300 px-4 py-2 active:bg-emerald-100"
        >
          <Text className="text-sm font-semibold text-emerald-800">
            Bölümlere dön
          </Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View className="gap-3">
      {/* Bölüm rayı */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View className="flex-row gap-1.5 px-0.5">
          {chapters.map((c, i) => {
            const active = i === chapterIdx;
            const done = doneSet.has(c.key);
            return (
              <Pressable
                key={c.key}
                onPress={() => openChapter(i)}
                className={
                  active
                    ? "flex-row items-center gap-1 rounded-full bg-cyan-700 px-3 py-1.5"
                    : "flex-row items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1.5 active:bg-slate-100"
                }
              >
                {done ? (
                  <Ionicons
                    name="checkmark-circle"
                    size={13}
                    color={active ? "#a5f3fc" : "#059669"}
                  />
                ) : null}
                <Text
                  className={
                    active
                      ? "text-xs font-bold text-white"
                      : "text-xs font-medium text-slate-700"
                  }
                >
                  {i + 1}. {c.title}
                </Text>
              </Pressable>
            );
          })}
        </View>
      </ScrollView>

      <Text className="text-xs text-slate-500">{chapter.subtitle}</Text>

      {/* Sahne */}
      <Scene chapter={chapter} stepIdx={stepIdx} playing={playing} />

      {/* Altyazı */}
      <View className="min-h-[64px] rounded-2xl border border-slate-200 bg-white px-4 py-3">
        <Text className="text-[13px] leading-5 text-slate-800">
          {step.caption}
        </Text>
      </View>

      {/* Kontroller */}
      <View className="flex-row items-center justify-between">
        <View className="flex-row items-center gap-2">
          <Pressable
            onPress={() => {
              setFinished(false);
              setStepIdx((i) => Math.max(0, i - 1));
            }}
            disabled={stepIdx === 0}
            className={
              stepIdx === 0
                ? "size-10 items-center justify-center rounded-full bg-slate-100"
                : "size-10 items-center justify-center rounded-full bg-slate-200 active:bg-slate-300"
            }
            accessibilityLabel="Önceki adım"
          >
            <Ionicons name="play-skip-back" size={16} color={stepIdx === 0 ? "#cbd5e1" : "#334155"} />
          </Pressable>
          <Pressable
            onPress={() => (playing ? setPlaying(false) : play())}
            className="size-12 items-center justify-center rounded-full bg-cyan-700 active:bg-cyan-800"
            accessibilityLabel={playing ? "Duraklat" : "Oynat"}
          >
            <Ionicons name={playing ? "pause" : "play"} size={20} color="white" />
          </Pressable>
          <Pressable
            onPress={() => {
              setPlaying(false);
              if (stepIdx < chapter.steps.length - 1) {
                setStepIdx((i) => i + 1);
              } else {
                setFinished(true);
              }
            }}
            className="size-10 items-center justify-center rounded-full bg-slate-200 active:bg-slate-300"
            accessibilityLabel="Sonraki adım"
          >
            <Ionicons name="play-skip-forward" size={16} color="#334155" />
          </Pressable>
        </View>
        <Text className="text-xs font-semibold text-slate-500">
          Adım {stepIdx + 1}/{chapter.steps.length}
        </Text>
      </View>

      {/* Kaldığın yerden devam */}
      {!playing && !finished && firstUnwatched > stepIdx ? (
        <Pressable
          onPress={() => {
            setStepIdx(firstUnwatched);
            play();
          }}
          className="flex-row items-center justify-center gap-1.5 rounded-xl border border-cyan-300 bg-cyan-50 px-4 py-2.5 active:bg-cyan-100"
        >
          <Ionicons name="play-circle-outline" size={16} color="#0e7490" />
          <Text className="text-sm font-semibold text-cyan-800">
            Kaldığın yerden devam et (Adım {firstUnwatched + 1})
          </Text>
        </Pressable>
      ) : null}

      {/* Bölüm sonu kartı */}
      {finished ? (
        <ChapterEndCard
          chapter={chapter}
          checklist={guide.checklist}
          preexisting={guide.preexisting}
          isLast={chapterIdx === chapters.length - 1}
          onComplete={completeChapter}
          onReplay={() => {
            setFinished(false);
            setStepIdx(0);
            play();
          }}
        />
      ) : null}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Sahne — shot + vurgu kutusu + zoom (Animated) / avatar sahnesi
// ---------------------------------------------------------------------------

function Scene({
  chapter,
  stepIdx,
  playing,
}: {
  chapter: GuideChapterDef;
  stepIdx: number;
  playing: boolean;
}) {
  const step = chapter.steps[Math.min(stepIdx, chapter.steps.length - 1)];
  const box = boxFor(step.shot, step.target);
  const [size, setSize] = React.useState({ w: 0, h: 0 });

  const tx = React.useRef(new Animated.Value(0)).current;
  const ty = React.useRef(new Animated.Value(0)).current;
  const sc = React.useRef(new Animated.Value(1)).current;

  React.useEffect(() => {
    // Zoom hedefi: kutu merkezi görüntü merkezine gelsin (RN transform merkez
    // odaklıdır; web'deki transform-origin karşılığı elle hesaplanır).
    let scale = 1;
    let dx = 0;
    let dy = 0;
    if (step.zoom && box && size.w > 0) {
      scale = Math.min(2.2, Math.max(1.25, Math.min(55 / box.w, 55 / box.h)));
      const cx = ((box.x + box.w / 2) / 100 - 0.5) * size.w;
      const cy = ((box.y + box.h / 2) / 100 - 0.5) * size.h;
      const maxX = ((scale - 1) * size.w) / 2;
      const maxY = ((scale - 1) * size.h) / 2;
      dx = Math.min(maxX, Math.max(-maxX, -scale * cx));
      dy = Math.min(maxY, Math.max(-maxY, -scale * cy));
    }
    Animated.parallel([
      Animated.timing(tx, { toValue: dx, duration: 700, useNativeDriver: true }),
      Animated.timing(ty, { toValue: dy, duration: 700, useNativeDriver: true }),
      Animated.timing(sc, { toValue: scale, duration: 700, useNativeDriver: true }),
    ]).start();
  }, [step.zoom, step.shot, step.target, box, size.w, size.h, tx, ty, sc]);

  return (
    <View
      className="w-full overflow-hidden rounded-2xl border border-slate-300 bg-slate-900"
      style={{ aspectRatio: SCENE_ASPECT }}
      onLayout={(e) =>
        setSize({
          w: e.nativeEvent.layout.width,
          h: e.nativeEvent.layout.height,
        })
      }
    >
      {step.shot ? (
        <Animated.View
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            transform: [{ translateX: tx }, { translateY: ty }, { scale: sc }],
          }}
        >
          <Image
            source={{ uri: shotUrl(step.shot) }}
            style={{ width: "100%", height: "100%" }}
            resizeMode="cover"
          />
          {box ? (
            <View
              pointerEvents="none"
              style={{
                position: "absolute",
                left: `${box.x}%`,
                top: `${box.y}%`,
                width: `${box.w}%`,
                height: `${box.h}%`,
                borderWidth: 2,
                borderColor: "#f59e0b",
                borderRadius: 6,
                backgroundColor: "rgba(245, 158, 11, 0.12)",
              }}
            />
          ) : null}
        </Animated.View>
      ) : (
        <View className="flex-1 items-center justify-center gap-3 bg-cyan-950">
          <View
            className={
              playing
                ? "size-24 items-center justify-center rounded-full border-4 border-cyan-400"
                : "size-24 items-center justify-center rounded-full border-4 border-cyan-800"
            }
          >
            <Image
              source={{ uri: GUIDE_AVATAR_URL }}
              style={{ width: 80, height: 80, borderRadius: 40 }}
            />
          </View>
          <Text className="text-sm font-semibold text-cyan-100">Rota</Text>
        </View>
      )}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Bölüm sonu kartı — checklist bilgisi (kapı yok, yumuşak öneri)
// ---------------------------------------------------------------------------

function ChapterEndCard({
  chapter,
  checklist,
  preexisting,
  isLast,
  onComplete,
  onReplay,
}: {
  chapter: GuideChapterDef;
  checklist: Record<string, boolean>;
  preexisting: Record<string, boolean>;
  isLast: boolean;
  onComplete: () => void;
  onReplay: () => void;
}) {
  const action = chapter.action;
  const fresh = action ? checklist[chapter.key] === true : false;
  const already = action ? preexisting[chapter.key] === true : false;

  return (
    <View className="gap-2.5 rounded-2xl border border-slate-200 bg-white p-4">
      <Text className="text-sm font-bold text-slate-900">
        Bölüm bitti: {chapter.title}
      </Text>

      {action ? (
        fresh ? (
          <View className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2.5">
            <Text className="text-xs font-semibold text-emerald-800">
              {action.doneLabel} — harika, bunu gerçekten yaptın!
            </Text>
          </View>
        ) : already ? (
          <View className="rounded-xl border border-sky-200 bg-sky-50 px-3 py-2.5">
            <Text className="text-xs font-semibold text-sky-800">
              Bunu zaten yapmışsın — istersen pekiştir, istersen devam et.
            </Text>
          </View>
        ) : (
          <View className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2.5">
            <Text className="text-xs font-semibold text-amber-900">
              {action.label}
            </Text>
            <Text className="mt-1 text-[11px] text-amber-800">{action.hint}</Text>
            <Text className="mt-1 text-[11px] text-amber-700">
              {action.optional
                ? "İstersen dene — zorunlu değil."
                : "Uygulamada ya da web panelinde deneyebilirsin; rehber seni beklemez."}
            </Text>
          </View>
        )
      ) : null}

      <View className="flex-row gap-2">
        <Pressable
          onPress={onReplay}
          className="flex-1 items-center rounded-xl border border-slate-300 px-4 py-2.5 active:bg-slate-100"
        >
          <Text className="text-sm font-semibold text-slate-700">
            Baştan izle
          </Text>
        </Pressable>
        <Pressable
          onPress={onComplete}
          className="flex-1 items-center rounded-xl bg-cyan-700 px-4 py-2.5 active:bg-cyan-800"
        >
          <Text className="text-sm font-bold text-white">
            {isLast ? "Rehberi bitir" : "Bölümü tamamla"}
          </Text>
        </Pressable>
      </View>
    </View>
  );
}
