import type { ReactNode } from "react";
import { SetGlyph } from "./Brand";
import { FilterDropdown, type FilterOption } from "./FilterDropdown";

export interface SetFilterOption extends FilterOption {
  glyphCode?: string;
  meta?: ReactNode;
}

// Searchable, scrollable set picker: trigger shows the selected set's glyph + code, the open list
// shows glyph + full name plus optional trailing meta (a count, a LIVE badge). Shared so the
// Episodes and Leaderboard set switchers stay identical.
export function SetFilterDropdown({
  label,
  value,
  options,
  onChange,
  variant,
  align,
  searchable,
  searchPlaceholder = "Search sets or codes…",
  className,
  triggerClassName,
}: {
  label?: string;
  value: string;
  options: SetFilterOption[];
  onChange: (next: string) => void;
  variant?: "desktop" | "mobile";
  align?: "left" | "right";
  searchable?: boolean;
  searchPlaceholder?: string;
  className?: string;
  triggerClassName?: string;
}) {
  const byValue = new Map(options.map((option) => [option.value, option]));
  const glyphFor = (code: string) => byValue.get(code)?.glyphCode ?? code;

  const renderValue = (option: FilterOption) =>
    option.value ? (
      <span className="flex items-center gap-2 truncate">
        <SetGlyph code={glyphFor(option.value)} size={20} />
        {option.value}
      </span>
    ) : (
      option.label
    );

  const renderOption = (option: FilterOption) => (
    <span className="flex w-full min-w-0 items-center gap-2.5">
      {option.value ? <SetGlyph code={glyphFor(option.value)} size={20} /> : <span className="w-5 shrink-0" />}
      <span className="flex-1 truncate">{option.label}</span>
      {byValue.get(option.value)?.meta ?? null}
    </span>
  );

  return (
    <FilterDropdown
      label={label}
      value={value}
      options={options}
      onChange={onChange}
      variant={variant}
      align={align}
      renderValue={renderValue}
      renderOption={renderOption}
      searchable={searchable}
      searchPlaceholder={searchPlaceholder}
      className={className}
      triggerClassName={triggerClassName}
    />
  );
}
