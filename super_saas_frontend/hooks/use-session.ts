import { useQuery } from "@tanstack/react-query";

import { authApi } from "@/lib/auth";

export const useSession = () =>
  useQuery({
    queryKey: ["session"],
    queryFn: () => authApi.me(),
    retry: false,
  });
