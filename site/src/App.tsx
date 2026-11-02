import { lazy, Suspense, useEffect } from "react";
import { content } from "./data/content";
import { useTour } from "./features/tour/useTour";
import { SiteHeader } from "./sections/SiteHeader";
import { Pipeline, Results, Features, QuickStart, Scope, Faq } from "./sections/Sections";
import { ClosingCta, SiteFooter } from "./sections/SiteFooter";
import "./styles/site.css";

const Simulator = lazy(() => import("./features/simulator/Simulator"));

function App() {
  const {
    active,
    setActive,
    paused,
    setPaused,
    holding,
    setHeld: setHolding,
  } = useTour(content.tour.length);

  useEffect(() => {
    const targets = [document.getElementById("win"), document.getElementById("tl")].filter(
      Boolean,
    );
    const pause = () => setHolding(true);
    const resume = () => setHolding(false);
    const visibility = () => setHolding(document.hidden);
    targets.forEach((target) => {
      target?.addEventListener("mouseenter", pause);
      target?.addEventListener("mouseleave", resume);
      target?.addEventListener("focusin", pause);
      target?.addEventListener("focusout", resume);
    });
    document.addEventListener("visibilitychange", visibility);
    return () => {
      targets.forEach((target) => {
        target?.removeEventListener("mouseenter", pause);
        target?.removeEventListener("mouseleave", resume);
        target?.removeEventListener("focusin", pause);
        target?.removeEventListener("focusout", resume);
      });
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [setHolding]);

  useEffect(() => {
    const callout = document.querySelector(".rv-wrap");
    if (!callout || !("IntersectionObserver" in window)) return undefined;
    callout.classList.add("arm");
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          callout.classList.add("in");
          observer.disconnect();
        }
      },
      { threshold: 0.25 },
    );
    observer.observe(callout);
    return () => observer.disconnect();
  }, []);

  return (
    <>
      <div className="wrap">
        <SiteHeader
          active={active}
          setActive={setActive}
          paused={paused}
          holding={holding}
          onToggle={() => setPaused((value) => !value)}
        />
        <main id="main">
          <Pipeline />
          <Suspense
            fallback={
              <section className="sec">
                <p className="lead2">Loading the local replication lab…</p>
              </section>
            }
          >
            <Simulator />
          </Suspense>
          <Results />
          <Features />
          <QuickStart />
          <Scope />
          <Faq />
          <ClosingCta />
        </main>
      </div>
      <SiteFooter />
    </>
  );
}

export default App;
