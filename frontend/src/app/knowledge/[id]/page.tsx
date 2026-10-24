import { KnowledgeDetail } from '@/components/knowledge/knowledge';
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <KnowledgeDetail id={id} />;
}
