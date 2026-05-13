import { clsx } from 'clsx';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ currentPage, totalPages, onPageChange }: PaginationProps) {
  const pages = getPageNumbers(currentPage, totalPages);

  return (
    <div className="flex items-center justify-center gap-1">
      <button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage <= 1}
        className={clsx(
          'px-3 py-2 text-sm rounded-lg transition-colors',
          currentPage <= 1
            ? 'text-slate-400 cursor-not-allowed'
            : 'text-slate-600 hover:bg-slate-100'
        )}
      >
        Previous
      </button>

      {pages.map((page, index) => (
        <button
          key={index}
          onClick={() => typeof page === 'number' && onPageChange(page)}
          disabled={page === '...'}
          className={clsx(
            'px-3 py-2 text-sm rounded-lg transition-colors min-w-[40px]',
            page === currentPage
              ? 'bg-primary-600 text-white'
              : page === '...'
              ? 'text-slate-400 cursor-default'
              : 'text-slate-600 hover:bg-slate-100'
          )}
        >
          {page}
        </button>
      ))}

      <button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage >= totalPages}
        className={clsx(
          'px-3 py-2 text-sm rounded-lg transition-colors',
          currentPage >= totalPages
            ? 'text-slate-400 cursor-not-allowed'
            : 'text-slate-600 hover:bg-slate-100'
        )}
      >
        Next
      </button>
    </div>
  );
}

function getPageNumbers(current: number, total: number): (number | string)[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages: (number | string)[] = [];

  if (current <= 4) {
    pages.push(1, 2, 3, 4, 5, '...', total);
  } else if (current >= total - 3) {
    pages.push(1, '...', total - 4, total - 3, total - 2, total - 1, total);
  } else {
    pages.push(1, '...', current - 1, current, current + 1, '...', total);
  }

  return pages;
}
