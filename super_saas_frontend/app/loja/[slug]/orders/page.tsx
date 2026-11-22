import { redirect } from "next/navigation";

export default function OrdersPage({ params }: { params: { slug: string } }) {
  redirect(`/account/orders?tenant=${encodeURIComponent(params.slug)}`);
}
