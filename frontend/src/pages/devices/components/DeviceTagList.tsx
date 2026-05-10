import { Badge } from '../../../components/ui';

interface DeviceTagListProps {
  tags: string[];
}

export function DeviceTagList({ tags }: DeviceTagListProps) {
  if (!tags || tags.length === 0) {
    return <span className="text-gray-400 text-xs">—</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {tags.map((tag) => (
        <Badge key={tag} variant="default" className="text-xs">
          {tag}
        </Badge>
      ))}
    </div>
  );
}
