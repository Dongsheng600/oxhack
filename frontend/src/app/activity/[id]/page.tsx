import { ActivityDetail } from '@/components/activity/activity';
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ActivityDetail id={id} />;
}
