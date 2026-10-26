"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

export default function ConversationDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();

  useEffect(() => {
    if (params?.id) {
      router.replace(`/space?conversationId=${params.id}`);
    } else {
      router.replace("/space?drawer=conversations");
    }
  }, [params, router]);

  return null;
}
