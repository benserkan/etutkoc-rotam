import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, Alert, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { BookPickStep, CountStep, SectionPickStep } from "@/components/student/book-source-picker";
import { ApiError } from "@/lib/api";
import {
  getBookSections,
  getStudentBooks,
  requestAdd,
  requestReplace,
  type BookSectionOption,
  type PickBook,
} from "@/lib/student";

export default function RequestSourceRoute() {
  const qc = useQueryClient();
  const params = useLocalSearchParams<{ mode?: string; task?: string; date?: string }>();
  const mode = params.mode === "add" ? "add" : "replace";
  const taskId = params.task ? Number(params.task) : null;
  const dateIso = typeof params.date === "string" ? params.date : null;
  const title = mode === "add" ? "Yeni görev iste" : "Kaynak değiştir";

  const [step, setStep] = React.useState<"book" | "section" | "count">("book");
  const [book, setBook] = React.useState<PickBook | null>(null);
  const [section, setSection] = React.useState<BookSectionOption | null>(null);
  const [count, setCount] = React.useState("");
  const [message, setMessage] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const booksQ = useQuery({ queryKey: ["student", "books"], queryFn: getStudentBooks });
  const sectionsQ = useQuery({
    queryKey: ["student", "sections", book?.book_id],
    queryFn: () => getBookSections(book!.book_id),
    enabled: !!book && step === "section",
  });

  function pickBook(b: PickBook) {
    setBook(b);
    setSection(null);
    setStep("section");
  }
  function pickSection(s: BookSectionOption) {
    setSection(s);
    setCount(String(Math.max(1, Math.min(s.remaining, 5))));
    setError(null);
    setStep("count");
  }
  function goBack() {
    if (step === "count") setStep("section");
    else if (step === "section") setStep("book");
    else router.back();
  }

  async function submit() {
    if (!book || !section) return;
    const n = Number(count);
    if (!(n > 0)) return;
    setBusy(true);
    setError(null);
    try {
      if (mode === "add") {
        if (!dateIso) throw new ApiError(400, "no_date", "Gün bulunamadı.");
        await requestAdd(dateIso, {
          book_id: book.book_id,
          section_id: section.id,
          proposed_count: n,
          message: message.trim() || undefined,
        });
      } else {
        if (!taskId) throw new ApiError(400, "no_task", "Görev bulunamadı.");
        await requestReplace(taskId, {
          new_book_id: book.book_id,
          new_section_id: section.id,
          new_count: n,
          message: message.trim() || undefined,
        });
      }
      await qc.invalidateQueries({ queryKey: ["student"] });
      Alert.alert("Talebin gönderildi", "Koçunun onayına iletildi. Taleplerim'den takip edebilirsin.", [
        { text: "Tamam", onPress: () => router.back() },
      ]);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Gönderilemedi. Bağlantını kontrol et.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-row items-center gap-1 px-2 py-2">
        <Pressable
          onPress={goBack}
          hitSlop={8}
          className="size-10 items-center justify-center rounded-full active:bg-slate-200"
          accessibilityLabel="Geri"
        >
          <Ionicons name="chevron-back" size={26} color="#334155" />
        </Pressable>
        <Text className="text-base font-semibold text-slate-800">{title}</Text>
      </View>

      {step === "book" ? (
        booksQ.isLoading ? (
          <Center />
        ) : (
          <BookPickStep groups={booksQ.data?.subjects ?? []} onPick={pickBook} />
        )
      ) : null}

      {step === "section" && book ? (
        sectionsQ.isLoading ? (
          <Center />
        ) : (
          <SectionPickStep bookName={book.book_name} sections={sectionsQ.data?.items ?? []} onPick={pickSection} />
        )
      ) : null}

      {step === "count" && book && section ? (
        <CountStep
          bookName={book.book_name}
          sectionLabel={section.label}
          max={Math.max(1, section.remaining)}
          count={count}
          setCount={setCount}
          message={message}
          setMessage={setMessage}
          busy={busy}
          error={error}
          submitLabel={mode === "add" ? "Görev iste" : "Değişiklik iste"}
          onSubmit={submit}
        />
      ) : null}
    </SafeAreaView>
  );
}

function Center() {
  return (
    <View className="flex-1 items-center justify-center">
      <ActivityIndicator size="large" color="#0e7490" />
    </View>
  );
}
