import { SafeAreaView } from "react-native-safe-area-context";

import { BooksView } from "@/components/student/books-view";
import type { StudentBooksProgress } from "@/lib/student";

const MOCK: StudentBooksProgress = {
  total_tests: 1200, reserved_tests: 180, completed_tests: 640, remaining_tests: 380,
  subjects: [
    {
      subject_id: 1, subject_name: "Matematik", total_tests: 480, reserved_tests: 60, completed_tests: 300, remaining_tests: 120,
      books: [
        { student_book_id: 1, book_id: 1, book_name: "Matematik Soru Bankası", book_type: "soru_bankasi", total_tests: 320, reserved_tests: 40, completed_tests: 220, remaining_tests: 60 },
        { student_book_id: 2, book_id: 2, book_name: "Deneme Seti", book_type: "deneme", total_tests: 160, reserved_tests: 20, completed_tests: 80, remaining_tests: 60 },
      ],
    },
    {
      subject_id: 2, subject_name: "Fen Bilimleri", total_tests: 400, reserved_tests: 80, completed_tests: 200, remaining_tests: 120,
      books: [
        { student_book_id: 3, book_id: 3, book_name: "Fen Soru Bankası", book_type: "soru_bankasi", total_tests: 400, reserved_tests: 80, completed_tests: 200, remaining_tests: 120 },
      ],
    },
    {
      subject_id: 3, subject_name: "Türkçe", total_tests: 320, reserved_tests: 40, completed_tests: 140, remaining_tests: 140,
      books: [
        { student_book_id: 4, book_id: 4, book_name: "Türkçe Paragraf", book_type: "soru_bankasi", total_tests: 320, reserved_tests: 40, completed_tests: 140, remaining_tests: 140 },
      ],
    },
  ],
};

export default function StudentBooksPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <BooksView data={MOCK} />
    </SafeAreaView>
  );
}
