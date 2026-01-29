import { redirect } from "next/navigation";

export default function TenantIndex({ params }: { params: { tenantId: string } }) {
  redirect(`/t/${params.tenantId}/dashboard`);
}
