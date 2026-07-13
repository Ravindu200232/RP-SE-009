import DevOpsCenterPrototype from "../../components/DevOpsCenterPrototype";

type JobPageProps = { params: Promise<{ jobId: string }> };

export default async function JobPage({ params }: JobPageProps) {
  const { jobId } = await params;
  return <DevOpsCenterPrototype jobId={jobId} />;
}
