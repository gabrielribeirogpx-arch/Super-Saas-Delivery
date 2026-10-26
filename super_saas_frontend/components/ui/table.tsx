import * as React from "react";

import { cn } from "@/lib/utils";

interface TableProps extends React.HTMLAttributes<HTMLTableElement> {
  containerClassName?: string;
  mobileCards?: boolean;
}

const Table = React.forwardRef<HTMLTableElement, TableProps>(
  ({ className, containerClassName, mobileCards = false, ...props }, ref) => (
    <div
      className={cn(
        "w-full overflow-auto",
        mobileCards && "mobile-table-container",
        containerClassName,
      )}
    >
      <table
        ref={ref}
        role="table"
        className={cn(
          "w-full caption-bottom text-sm",
          mobileCards && "mobile-table-cards",
          className,
        )}
        {...props}
      />
    </div>
  ),
);
Table.displayName = "Table";

const TableHeader = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <thead
    role="rowgroup"
    ref={ref}
    className={cn("border-b border-slate-200 bg-slate-50", className)}
    {...props}
  />
));
TableHeader.displayName = "TableHeader";

const TableBody = React.forwardRef<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>(({ className, ...props }, ref) => (
  <tbody
    role="rowgroup"
    ref={ref}
    className={cn("[&_tr]:border-b", className)}
    {...props}
  />
));
TableBody.displayName = "TableBody";

const TableRow = React.forwardRef<
  HTMLTableRowElement,
  React.HTMLAttributes<HTMLTableRowElement>
>(({ className, ...props }, ref) => (
  <tr
    role="row"
    ref={ref}
    className={cn(
      "border-slate-200 transition-colors hover:bg-slate-50",
      className,
    )}
    {...props}
  />
));
TableRow.displayName = "TableRow";

const TableHead = React.forwardRef<
  HTMLTableCellElement,
  React.ThHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <th
    role="columnheader"
    scope="col"
    ref={ref}
    className={cn(
      "h-12 px-4 text-left align-middle font-medium text-slate-500",
      className,
    )}
    {...props}
  />
));
TableHead.displayName = "TableHead";

interface TableCellProps extends React.TdHTMLAttributes<HTMLTableCellElement> {
  mobileLabel?: string;
  mobileActions?: boolean;
}

const TableCell = React.forwardRef<HTMLTableCellElement, TableCellProps>(
  (
    { className, mobileLabel, mobileActions = false, children, ...props },
    ref,
  ) => (
    <td
      ref={ref}
      role="cell"
      data-mobile-label={mobileLabel}
      data-mobile-actions={mobileActions || undefined}
      className={cn("p-4 align-middle", className)}
      {...props}
    >
      {mobileLabel ? (
        <>
          <span aria-hidden="true" className="mobile-table-label">
            {mobileLabel}
          </span>
          <div
            className={cn(
              "mobile-table-value",
              mobileActions && "flex flex-wrap items-center justify-end gap-2",
            )}
          >
            {children}
          </div>
        </>
      ) : (
        children
      )}
    </td>
  ),
);
TableCell.displayName = "TableCell";

const TableCaption = React.forwardRef<
  HTMLTableCaptionElement,
  React.HTMLAttributes<HTMLTableCaptionElement>
>(({ className, ...props }, ref) => (
  <caption
    ref={ref}
    className={cn("mt-4 text-sm text-slate-500", className)}
    {...props}
  />
));
TableCaption.displayName = "TableCaption";

export {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
  TableCaption,
};
