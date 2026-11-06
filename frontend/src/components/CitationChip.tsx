interface CitationChipProps {
  id: number;
  onSelect: (id: number) => void;
}

export function CitationChip({ id, onSelect }: CitationChipProps) {
  return (
    <a
      href={`#src-${id}`}
      aria-label={`Source ${id}`}
      onClick={(event) => {
        event.preventDefault();
        onSelect(id);
      }}
      className="mx-0.5 inline-flex h-[22px] min-w-[22px] items-center justify-center rounded-[5px] bg-chip px-[5px] align-[2px] font-mono text-xs font-semibold text-primary no-underline"
    >
      {id}
    </a>
  );
}
