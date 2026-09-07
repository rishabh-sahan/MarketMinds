import { Link } from 'react-router-dom';
import { Logo, ThemeToggle } from '../components/layout/AppShell';
import { Button, Icon } from '../components/ui';
import { classNames as cx } from '../lib/format';
import { PHASES, PHASE_BLURBS, PIPELINE } from '../lib/pipeline';

/**
 * How to use MarketMinds — the short version.
 *
 * Deliberately dense. Someone reading this has not signed in and wants to know
 * what the thing does before committing ten minutes to a run; a long page gets
 * skimmed and the important parts get missed.
 *
 * The stages are derived from `lib/pipeline.js` rather than retyped. An earlier
 * version of this page described the pipeline as two stages when the system has
 * five — the kind of drift that only happens when the same fact is written down
 * twice.
 */

const STAGES = PHASES.map((phase) => ({
  name: phase,
  blurb: PHASE_BLURBS[phase],
  agents: PIPELINE.filter((agent) => agent.phase === phase),
}));

const STEPS = [
  {
    icon: 'key',
    title: 'Add a model key',
    body: 'Settings → paste a key from Google, OpenAI, Anthropic, Sarvam or any supported provider. It stays in your browser and is never stored on our server.',
  },
  {
    icon: 'plus',
    title: 'Enter an NSE ticker',
    body: 'RELIANCE, HAL, TCS. The symbol and trade date are checked against the exchange before anything runs, so typos and market holidays fail immediately.',
  },
  {
    icon: 'verdict',
    title: 'Read the argument',
    body: 'Five to fifteen minutes later you get a rating — and the full debate behind it. Close the tab if you like; the run continues and waits in History.',
  },
];

const FAQ = [
  ['Do I need an account?', 'Only to start a run. Browsing and the sample analyses are open to everyone. Your own runs stay private to you.'],
  ['Whose API key is used?', 'Yours, from your browser, for your run only. It is never written to our database or logs.'],
  ['Why does it take minutes?', 'Twelve agents making real model calls and arguing across rounds. Nothing is cached or pre-written.'],
  ['Does it improve?', 'Yes. Each call is scored against what actually happened versus the Nifty, and that lesson feeds the next run on that stock.'],
  ['Can I trade on it?', 'No. This is a research and educational tool. It can be confidently wrong and knows nothing about your circumstances.'],
  ['What do I get to keep?', 'A PDF with the rating, every agent report in order, and the run metadata.'],
];

// `wide` is for the three-step row, which needs the extra width to sit side by
// side without squeezing each column into a column of single words.
function Section({ eyebrow, title, wide = false, children }) {
  return (
    <section
      className={cx(
        'mx-auto w-full px-5 py-10 sm:py-12',
        wide ? 'max-w-5xl' : 'max-w-3xl',
      )}
    >
      <div className="mb-6">
        {eyebrow ? (
          <span className="text-[11.5px] font-semibold tracking-wide text-accent uppercase">
            {eyebrow}
          </span>
        ) : null}
        <h2 className="mt-1 text-[21px] font-semibold tracking-[-0.02em] text-ink sm:text-[23px]">
          {title}
        </h2>
      </div>
      {children}
    </section>
  );
}

export default function Guide() {
  return (
    <div className="min-h-screen bg-bg">
      <header className="sticky top-0 z-20 border-b border-line bg-bg/85 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-5">
          <Logo />
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Button as={Link} to="/" size="sm" icon="arrowLeft">
              Home
            </Button>
          </div>
        </div>
      </header>

      {/* ------------------------------------------------------------ hero */}
      <section className="mx-auto max-w-3xl px-5 pt-12 pb-2 sm:pt-16">
        <h1 className="text-[30px] leading-[1.12] font-semibold tracking-[-0.03em] text-ink sm:text-[38px]">
          One ticker in.
          <br />
          <span className="text-accent">A reasoned verdict out.</span>
        </h1>
        <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-ink-secondary">
          Twelve AI agents research one Indian stock, argue about what the evidence means, and
          issue a rating you can audit line by line. Here is the whole thing in two minutes.
        </p>
      </section>

      {/* --------------------------------------------------------- 3 steps */}
      <Section eyebrow="Using it" title="Three steps" wide>
        {/* Side by side, so the whole workflow is visible without scrolling.
            Stacks on narrow screens, where three columns would be unreadable. */}
        <ol className="grid gap-3 md:grid-cols-3">
          {STEPS.map((step, i) => (
            <li
              key={step.title}
              className="flex flex-col rounded-xl border border-line bg-surface p-5"
            >
              <div className="flex items-center gap-2.5">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-accent text-[12.5px] font-semibold text-on-accent">
                  {i + 1}
                </span>
                <Icon name={step.icon} size={15} className="text-accent" />
              </div>
              <h3 className="mt-3 text-[14.5px] font-semibold text-ink">{step.title}</h3>
              <p className="mt-1.5 text-[13.5px] leading-relaxed text-ink-secondary">
                {step.body}
              </p>
            </li>
          ))}
        </ol>
      </Section>

      {/* -------------------------------------------------------- pipeline */}
      <div className="border-y border-line bg-surface">
        <Section
          eyebrow="Inside a run"
          title={`${PIPELINE.length} agents, ${STAGES.length} stages`}
        >
          <ol className="relative space-y-3 border-l border-line pl-6">
            {STAGES.map((stage, i) => (
              <li key={stage.name} className="relative">
                {/* Sits on the rail, marking where this stage begins. */}
                <span className="absolute top-1 -left-[31px] flex h-[22px] w-[22px] items-center justify-center rounded-full border border-accent-border bg-bg text-[11px] font-semibold text-accent-text">
                  {i + 1}
                </span>
                <div className="rounded-xl border border-line bg-bg p-4">
                  <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
                    <h3 className="text-[14.5px] font-semibold text-ink">{stage.name}</h3>
                    <p className="text-[13px] text-ink-secondary">{stage.blurb}</p>
                  </div>
                  <div className="mt-2.5 flex flex-wrap gap-1.5">
                    {stage.agents.map((agent) => (
                      <span
                        key={agent.agent}
                        title={agent.role}
                        className="inline-flex items-center gap-1.5 rounded-md border border-line bg-surface px-2 py-1 text-[12px] text-ink-secondary"
                      >
                        <Icon name={agent.icon} size={11} className="text-accent" />
                        {agent.agent}
                      </span>
                    ))}
                  </div>
                </div>
              </li>
            ))}
          </ol>

          <p className="mt-4 flex gap-2.5 rounded-xl border border-accent-border bg-accent-soft p-4 text-[13.5px] leading-relaxed text-ink-secondary">
            <Icon name="spark" size={14} className="mt-0.5 shrink-0 text-accent" />
            <span>
              The point is not that the agents agree. It is that you can read exactly where they
              did not, and judge which side had the better evidence.
            </span>
          </p>
        </Section>
      </div>

      {/* ------------------------------------------------- reading the result */}
      <Section eyebrow="The output" title="What to look at first">
        <div className="grid gap-2.5 sm:grid-cols-2">
          {[
            ['verdict', 'The disagreement', 'A Buy both sides reached differs from one the risk committee fought over. Open the debates before trusting the headline.'],
            ['tool', 'The tool calls', 'Each agent shows what it actually fetched. Thin data means its confidence is worth less — and you can see that.'],
            ['memory', 'The Memory page', 'Past calls scored against the Nifty. The only place the system marks its own homework.'],
            ['download', 'The PDF', 'Rating, metadata and every report in pipeline order. The artefact worth keeping.'],
          ].map(([icon, title, body]) => (
            <div key={title} className="rounded-xl border border-line bg-surface p-4">
              <h3 className="flex items-center gap-2 text-[13.5px] font-semibold text-ink">
                <Icon name={icon} size={14} className="text-accent" />
                {title}
              </h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-ink-secondary">{body}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* ------------------------------------------------------------- faq */}
      <div className="border-y border-line bg-surface">
        <Section eyebrow="Good to know" title="Quick answers">
          <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
            {FAQ.map(([q, a]) => (
              <div key={q}>
                <dt className="text-[13.5px] font-semibold text-ink">{q}</dt>
                <dd className="mt-1 text-[13px] leading-relaxed text-ink-secondary">{a}</dd>
              </div>
            ))}
          </dl>
        </Section>
      </div>

      {/* ------------------------------------------------------------- cta */}
      <section className="mx-auto max-w-3xl px-5 py-14 text-center sm:py-16">
        <h2 className="text-[22px] font-semibold tracking-[-0.02em] text-ink">
          Pick a stock you already have an opinion about
        </h2>
        <p className="mx-auto mt-2 max-w-sm text-[13.5px] leading-relaxed text-ink-secondary">
          It is far more interesting when you can argue back.
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-2.5">
          <Button as={Link} to="/runs/new" variant="primary" size="lg" icon="play">
            Start an analysis
          </Button>
          <Button as={Link} to="/dashboard" size="lg" iconRight="arrowRight">
            See sample runs
          </Button>
        </div>
        <p className="mt-6 text-[12px] text-ink-muted">
          Research and educational use only. Not financial advice.
        </p>
      </section>
    </div>
  );
}
