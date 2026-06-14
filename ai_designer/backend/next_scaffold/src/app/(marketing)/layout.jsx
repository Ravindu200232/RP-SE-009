// Marketing shell: public pages render inside the deterministic Navbar.
import Navbar from '@/components/shell/Navbar';

export default function MarketingLayout({ children }) {
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      <main className="flex-1">{children}</main>
    </div>
  );
}
