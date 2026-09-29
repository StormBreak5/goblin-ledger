import Image from 'next/image';
import Link from 'next/link';
import AuthNav from '@/components/AuthNav';

export default function Header() {
  return (
    <header className="w-full border-b border-[var(--color-border)] bg-[var(--color-surface-solid)]/80 backdrop-blur-md sticky top-0 z-50">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-3">
          <div className="relative w-10 h-10">
            <Image 
              src="/logo.png" 
              alt="Goblin Ledger Logo" 
              fill 
              className="object-contain"
            />
          </div>
          <span className="font-bold text-lg text-[var(--color-text-title)] tracking-wider">
            GOBLIN LEDGER
          </span>
        </Link>
        
        <div className="flex items-center gap-6">
          <nav className="hidden md:flex gap-6">
            <Link href="/" className="text-[var(--color-text-secondary)] hover:text-[var(--color-text-main)] transition-colors">
              Busca
            </Link>
          </nav>
          <div className="flex items-center gap-4 text-sm">
            <AuthNav />
          </div>
        </div>
      </div>
    </header>
  );
}
