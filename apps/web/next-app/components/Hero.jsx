export default function Hero() {
  return (
    <section className="relative min-h-screen flex items-center justify-center">
      <div className="absolute inset-0 bg-gradient-to-b from-sovereign-black via-midnight-navy to-sovereign-black" />
      <div className="relative z-10 max-w-4xl mx-auto px-6 text-center">
        <h1 className="font-arabic text-4xl md:text-6xl lg:text-7xl font-bold leading-tight mb-6">
          <span className="text-parchment">لم يُبنَ هذا لتتعلم الإنجليزي.</span>
          <br />
          <span className="text-imperial-gold">بُنيَ لتصبح متحدثًا بالإنجليزي.</span>
        </h1>
        <p className="font-body text-lg text-steel mb-4" dir="ltr">
          This wasn&apos;t built to teach you English. It was built to turn you{" "}
          <span className="text-imperial-gold font-semibold">INTO</span> an English speaker.
        </p>
        <p className="font-arabic text-xl text-parchment/80 mb-10 max-w-2xl mx-auto">
          نظام يومي كامل — نطق أمريكي من اليوم الأول — مجتمع يدعمك — نتائج تقدر تقيسها
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <a
            href="#pricing"
            className="px-10 py-4 bg-imperial-gold text-sovereign-black font-bold text-lg rounded-sm hover:shadow-[0_0_30px_rgba(212,175,55,0.3)] transition-all font-arabic"
          >
            ابنِ إمبراطوريتك
          </a>
          <a
            href="#system"
            className="px-10 py-4 border border-steel/30 text-parchment text-lg rounded-sm hover:border-imperial-gold/50 hover:text-imperial-gold transition-all font-arabic"
          >
            كيف يعمل النظام؟
          </a>
        </div>
        <div className="mt-16 flex flex-wrap items-center justify-center gap-8 text-steel text-sm font-arabic">
          <div>
            <span className="text-imperial-gold font-bold text-lg">6+</span> أعضاء يبنون إمبراطوريتهم
          </div>
          <div>
            <span className="text-imperial-gold font-bold text-lg">45</span> دقيقة/يوم
          </div>
          <div>
            <span className="text-imperial-gold font-bold text-lg">8</span> أسابيع للمستوى الأول
          </div>
        </div>
      </div>
    </section>
  );
}
