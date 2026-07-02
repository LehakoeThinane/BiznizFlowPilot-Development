import type { ReactNode } from "react";

interface DataTableColumn<T> {
  key: keyof T | string;
  title: string;
  render?: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: Array<DataTableColumn<T>>;
  rows: T[];
  emptyMessage?: string;
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  rows,
  emptyMessage = "No data",
}: DataTableProps<T>) {
  if (!rows.length) {
    return (
      <div className="erp-panel p-6 text-sm text-on-surface-variant">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="erp-panel overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-[#111e35] text-left">
          <tr>
            {columns.map((column) => (
              <th key={String(column.key)} className="px-4 py-3 font-semibold uppercase tracking-wide text-[11px] text-on-surface-variant">
                {column.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-t border-border/80 transition-colors hover:bg-white/2">
              {columns.map((column) => (
                <td key={String(column.key)} className="px-4 py-3 text-on-surface">
                  {column.render
                    ? column.render(row)
                    : String(row[column.key as keyof T] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
