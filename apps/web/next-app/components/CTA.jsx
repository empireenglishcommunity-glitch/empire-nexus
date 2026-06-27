export default function CTA() {
  return (
    <section className="py-24 px-6 bg-sovereign-black border-t border-imperial-gold/10">
      <div className="max-w-3xl mx-auto text-center">
        <h2 className="font-arabic text-3xl font-bold mb-6">
          <span className="text-imperial-gold">النظام جاهز.</span> أنت جاهز؟
        </h2>
        <p className="font-arabic text-xl text-steel mb-10">
          ٤٥ دقيقة/يوم. ٨ أسابيع. نطقك يتغيّر.
        </p>
        <a
          href="#pricing"
          className="inline-block px-12 py-5 bg-imperial-gold text-sovereign-black font-arabic font-bold text-xl rounded-sm hover:shadow-[0_0_40px_rgba(212,175,55,0.3)] transition-all"
        >
          ابنِ إمبراطوريتك الآن
        </a>
        <p className="font-arabic text-sm text-steel mt-6">ضمان ٧ أيام · إلغاء أي وقت</p>
      </div>
    </section>
  );
}
