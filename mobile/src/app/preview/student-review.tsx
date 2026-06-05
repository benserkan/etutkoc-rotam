import { SafeAreaView } from "react-native-safe-area-context";
import { ReviewView } from "@/components/student/review-view";

export default function ReviewPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <ReviewView
        card={{ id: 1, topic_id: 1, topic_name: "Üslü Sayılar", subject_name: "Matematik", state: "review", review_count: 4 }}
        index={2} total={8} done={false} busy={false} onRate={() => {}} onClose={() => {}}
      />
    </SafeAreaView>
  );
}
