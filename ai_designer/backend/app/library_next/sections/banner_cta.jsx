// SECTION: banner (owns banner anchors).
function BannerCta() {
  return (
    <section className="px-4 pb-24 md:px-6">
      <div className="relative mx-auto max-w-7xl overflow-hidden rounded-[2rem]">
        <img src="/assets/banner.jpg" alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }} className="h-80 w-full object-cover" />
        <div className="absolute inset-0 flex items-end bg-gradient-to-t from-black/80 via-black/25 to-transparent">
          <div className="flex w-full flex-wrap items-end justify-between gap-6 p-10">
            <div className="max-w-md">
              <h3 className="mb-2 font-display text-3xl font-bold text-white">Banner headline over the photo</h3>
              <p className="text-sm text-white/85">One inviting sentence.</p>
            </div>
            <Link href="/register" className="rounded-full bg-white px-7 py-3.5 font-semibold text-black shadow-xl transition hover:bg-white/90">Get Started</Link>
          </div>
        </div>
      </div>
    </section>
  );
}
