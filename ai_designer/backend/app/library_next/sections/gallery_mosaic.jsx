// SECTION: gallery (no copy anchors). Mosaic with hover zoom, inspired by the
// user's LMS gallery.
function GalleryMosaic() {
  const tiles = [
    { src: '/assets/gallery1.jpg', cls: 'md:col-span-2 md:row-span-2 h-64 md:h-full' },
    { src: '/assets/gallery2.jpg', cls: 'h-64' },
    { src: '/assets/gallery3.jpg', cls: 'h-64' },
    { src: '/assets/feature2.jpg', cls: 'md:col-span-2 h-64' },
  ];
  return (
    <section className="px-4 pb-24 md:px-6">
      <div className="mx-auto grid max-w-7xl gap-5 md:grid-cols-4 md:grid-rows-2">
        {tiles.map((t) => (
          <div key={t.src} className={'group overflow-hidden rounded-2xl ' + t.cls}>
            <img src={t.src} alt="" onError={(e) => { e.currentTarget.style.display = 'none'; }}
              className="h-full w-full object-cover transition duration-500 group-hover:scale-105" />
          </div>
        ))}
      </div>
    </section>
  );
}
