import { Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { BookPickStep } from "@/components/student/book-source-picker";
import type { PickSubjectGroup } from "@/lib/student";

/** UX önizleme — kaynak değiştir/yeni görev iste: kitap seçimi (mock). Faz 7'de kaldırılacak. */
const GROUPS: PickSubjectGroup[] = [
  {
    subject_id: 1, subject_name: "Matematik",
    books: [
      { book_id: 1, book_name: "Karekök Yayınları", book_type: "soru_bankasi", remaining_tests: 42 },
      { book_id: 2, book_name: "Apotemi 8. Sınıf", book_type: "soru_bankasi", remaining_tests: 18 },
    ],
  },
  {
    subject_id: 2, subject_name: "Fen Bilimleri",
    books: [
      { book_id: 3, book_name: "3D Yayınları", book_type: "soru_bankasi", remaining_tests: 30 },
      { book_id: 4, book_name: "Paraf IQ Fen", book_type: "soru_bankasi", remaining_tests: 24 },
    ],
  },
  {
    subject_id: 3, subject_name: "Türkçe",
    books: [{ book_id: 5, book_name: "Bilgi Sarmal", book_type: "soru_bankasi", remaining_tests: 36 }],
  },
];

export default function SourcePickPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="px-4 py-2">
        <Text className="text-base font-semibold text-slate-800">Kaynak değiştir</Text>
      </View>
      <BookPickStep groups={GROUPS} onPick={() => {}} />
    </SafeAreaView>
  );
}
