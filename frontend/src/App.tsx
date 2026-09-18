import { useEffect, useMemo, useState, type ReactNode } from "react";
import { buildRouteLookup } from "./bookingLink";
import {
  api,
  type AffordabilityReport,
  type BacktestReport,
  type BookingAdvice as BookingAdviceData,
  type ByCarrierIndex,
  type CarrierFinancialContext as CarrierFinancialContextData,
  type CitizenFareReport,
  type CitizenReportCount,
  type ComplianceStatus,
  type CoverageReport,
  type CpiDivergence as CpiDivergenceData,
  type ElasticityPoint,
  type FareQuote,
  type IndexDailyPoint,
  type News,
  type OperatorOverview,
  type PriceGrid,
  type RegulatorFlag,
  type RouteOut,
  type RoutePriceHistory,
  type SpikeWatch as SpikeWatchData,
} from "./api";
import { getToken, landingTabFor, setToken, type AuthUser } from "./auth";
import { AccountControl } from "./components/AccountControl";
import { Affordability } from "./components/Affordability";
import { AirlineDashboard } from "./components/AirlineDashboard";
import { BookingAdvice } from "./components/BookingAdvice";
import { CarrierFinancialContext } from "./components/CarrierFinancialContext";
import { CarrierIndexChart } from "./components/CarrierIndexChart";
import { CitizenReportForm } from "./components/CitizenReportForm";
import { CitizenReports } from "./components/CitizenReports";
import { CpiDivergence } from "./components/CpiDivergence";
import { DataSources } from "./components/DataSources";
import { DateWatch } from "./components/DateWatch";
import { ElasticityChart } from "./components/ElasticityChart";
import { ErrorState } from "./components/ErrorState";
import { FaresTable } from "./components/FaresTable";
import { Footer } from "./components/Footer";
import { Header } from "./components/Header";
import { HeroStat } from "./components/HeroStat";
import { KpiCards } from "./components/KpiCards";
import { LoadingSkeleton } from "./components/LoadingSkeleton";
import { LoginPage } from "./components/LoginPage";
import { MyReports } from "./components/MyReports";
import { NewsFeed } from "./components/NewsFeed";
import { PageSummary } from "./components/PageSummary";
import { PriceHistory } from "./components/PriceHistory";
import { RegulatorFlags } from "./components/RegulatorFlags";
import { RouteFilter } from "./components/RouteFilter";
import { SectorHeatmap } from "./components/SectorHeatmap";
import { SpikeWatch } from "./components/SpikeWatch";
import { TAB_KEYS, TabNav, visibleTabs, type TabKey } from "./components/TabNav";
import { TrendChart } from "./components/TrendChart";
import { useUrlState } from "./urlState";

function isTabKey(value: string | null): value is TabKey {
  return value != null && (TAB_KEYS as string[]).includes(value);
}

interface DashboardData {
  routes: RouteOut[];
  daily: IndexDailyPoint[];
  backtest: BacktestReport;
  compliance: ComplianceStatus[];
  coverage: CoverageReport;
  elasticity: ElasticityPoint[];
  priceGrid: PriceGrid;
  fares: FareQuote[];
  spikeWatch: SpikeWatchData;
  cpiDivergence: CpiDivergenceData;
  affordability: AffordabilityReport;
  byCarrierIndex: ByCarrierIndex;
}

function TabPanel({ tabKey, active, children }: { tabKey: TabKey; active: TabKey; children: ReactNode }) {
  if (tabKey !== active) return null;
  return (
    <div
      role="tabpanel"
      id={`panel-${tabKey}`}
      aria-labelledby={`tab-${tabKey}`}
      tabIndex={0}
      className="flex flex-col gap-4"
    >
      {children}
    </div>
  );
}

function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [tabParam, setTabParam] = useUrlState("tab", "overview");
  const [routeParam, setRouteParam] = useUrlState("route", null);
  const routeFilterId = routeParam != null && routeParam !== "" ? Number(routeParam) : null;
  const [routeElasticity, setRouteElasticity] = useState<ElasticityPoint[] | null>(null);
  const [bookingAdvice, setBookingAdvice] = useState<BookingAdviceData | null>(null);
  const [priceHistory, setPriceHistory] = useState<RoutePriceHistory | null>(null);
  const [routeDataLoading, setRouteDataLoading] = useState(false);
  const [news, setNews] = useState<News | null>(null);
  const [newsLoading, setNewsLoading] = useState(true);
  const [financialContext, setFinancialContext] = useState<CarrierFinancialContextData[] | null>(null);
  const [flags, setFlags] = useState<RegulatorFlag[] | null>(null);
  const [flagsLoading, setFlagsLoading] = useState(false);
  const [reportCount, setReportCount] = useState<CitizenReportCount | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [citizenReports, setCitizenReports] = useState<CitizenFareReport[] | null>(null);
  const [myReports, setMyReports] = useState<CitizenFareReport[] | null>(null);
  const [operatorOverview, setOperatorOverview] = useState<OperatorOverview | null>(null);
  const [operatorFlags, setOperatorFlags] = useState<RegulatorFlag[] | null>(null);
  const [operatorFares, setOperatorFares] = useState<FareQuote[] | null>(null);
  const [operatorLoading, setOperatorLoading] = useState(false);
  // ?signin=1 so the login page is refreshable and linkable, and so the
  // browser back button leaves it the way it leaves any other view.
  const [signinParam, setSigninParam] = useUrlState("signin", null);
  const [signinReason, setSigninReason] = useState<string | null>(null);

  // A ?tab= that this role has no tab for (an airline link opened while
  // signed out, say) falls back to the public overview rather than
  // rendering a panel with no way to navigate away from it.
  const allowedTabs = visibleTabs(user?.role ?? null);
  const activeTab: TabKey =
    isTabKey(tabParam) && allowedTabs.includes(tabParam) ? tabParam : "overview";

  async function load() {
    setRefreshing(true);
    try {
      const [
        routes,
        daily,
        backtest,
        compliance,
        coverage,
        elasticity,
        priceGrid,
        fares,
        spikeWatch,
        cpiDivergence,
        affordability,
        byCarrierIndex,
      ] = await Promise.all([
        api.routes(),
        api.indexDaily(),
        api.backtest(),
        api.compliance(),
        api.coverage(),
        api.elasticity(),
        api.priceGrid(),
        api.fares(),
        api.spikeWatch(),
        api.cpiDivergence(),
        api.affordability(),
        api.indexByCarrier(),
      ]);
      setData({
        routes,
        daily,
        backtest,
        compliance,
        coverage,
        elasticity,
        priceGrid,
        fares,
        spikeWatch,
        cpiDivergence,
        affordability,
        byCarrierIndex,
      });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    // Fetched once, not on the 60s poll: the backend already caches these
    // real headlines for 15 minutes (see app.news.fetch_news), and a slow
    // or unreachable news source should never delay the real fare/index
    // data the rest of the dashboard depends on.
    api
      .news()
      .then(setNews)
      .catch(() => setNews(null))
      .finally(() => setNewsLoading(false));
  }, []);

  useEffect(() => {
    // Also fetched once, not on the 60s poll: these are quarterly filings
    // that change at most 4 times a year, and every request re-checks a
    // live compliance gate against each carrier's investor-relations page
    // (see app.index.financial_context) — no reason to repeat that every
    // minute for data this slow-moving.
    api
      .carriersFinancialContext()
      .then(setFinancialContext)
      .catch(() => setFinancialContext(null));
  }, []);

  useEffect(() => {
    // Restore a session left in this tab. A token that the server no longer
    // accepts (expired, or the account was deactivated) resolves to signed
    // out rather than an error — a stale session should never break a page
    // that does not need one.
    if (getToken() == null) return;
    api
      .me()
      .then(setUser)
      .catch(() => {
        setToken(null);
        setUser(null);
        setSigninReason("Your session has ended. Sign in again to continue.");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function loadReportCount() {
    // Public aggregate — no account needed, and it carries no report content
    // or contact details, only how many exist and how many await triage.
    api.citizenReportCount().then(setReportCount).catch(() => setReportCount(null));
  }

  function loadMyReports() {
    // Signed-in only; there is nothing to show an anonymous visitor, and the
    // endpoint would 401.
    if (getToken() == null) return;
    api.myReports().then(setMyReports).catch(() => setMyReports(null));
  }

  function loadOperatorData() {
    setOperatorLoading(true);
    Promise.all([api.operatorOverview(), api.operatorFlags(), api.operatorFares()])
      .then(([overview, flags, fares]) => {
        setOperatorOverview(overview);
        setOperatorFlags(flags);
        setOperatorFares(fares);
      })
      .catch(() => {
        setOperatorOverview(null);
        setOperatorFlags(null);
        setOperatorFares(null);
      })
      .finally(() => setOperatorLoading(false));
  }

  function handleSignedIn(nextUser: AuthUser, token: string) {
    setToken(token);
    setUser(nextUser);
    setSigninParam(null);
    setSigninReason(null);
    setTabParam(landingTabFor(nextUser.role));
    if (nextUser.role === "operator") loadOperatorData();
    if (nextUser.role === "regulator") loadRegulatorData();
    loadMyReports();
  }

  function handleSignedOut() {
    setToken(null);
    setUser(null);
    // Drop everything that was only visible to that session, so no
    // restricted data stays on screen after the session it belonged to has
    // ended — including the flag queue, which is not public.
    setFlags(null);
    setCitizenReports(null);
    setMyReports(null);
    setOperatorOverview(null);
    setOperatorFlags(null);
    setOperatorFares(null);
    setSigninReason(null);
    if (activeTab === "airline" || activeTab === "regulator") setTabParam("overview");
  }

  function handleRequestSignIn() {
    setSigninReason(null);
    setSigninParam("1");
  }

  function handleDismissSignIn() {
    setSigninParam(null);
    setSigninReason(null);
  }

  function loadRegulatorData() {
    setFlagsLoading(true);
    api
      .regulatorFlags()
      .then(setFlags)
      .catch(() => setFlags(null))
      .finally(() => setFlagsLoading(false));
    api.citizenReports().then(setCitizenReports).catch(() => setCitizenReports(null));
    loadReportCount();
  }

  useEffect(() => {
    // Lazy per tab, and not on the 60s poll: flags only change when the
    // daily detection run writes new ones. The regulator fetch is guarded on
    // the role as well as the tab — without an account it would only 401.
    if (activeTab === "regulator" && user?.role === "regulator" && flags === null && !flagsLoading) {
      loadRegulatorData();
    }
    if (activeTab === "airline" && operatorOverview === null && !operatorLoading) {
      loadOperatorData();
    }
    if (activeTab === "report") {
      if (reportCount === null) loadReportCount();
      if (user && myReports === null) loadMyReports();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, user]);

  useEffect(() => {
    if (routeFilterId == null) {
      setRouteElasticity(null);
      setBookingAdvice(null);
      setPriceHistory(null);
      return;
    }
    let cancelled = false;
    setRouteDataLoading(true);
    Promise.all([api.elasticity(routeFilterId), api.bookingAdvice(routeFilterId), api.priceHistory(routeFilterId)])
      .then(([elasticity, advice, history]) => {
        if (cancelled) return;
        setRouteElasticity(elasticity);
        setBookingAdvice(advice);
        setPriceHistory(history);
      })
      .catch(() => {
        if (cancelled) return;
        setRouteElasticity([]);
        setBookingAdvice(null);
        setPriceHistory(null);
      })
      .finally(() => {
        if (!cancelled) setRouteDataLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [routeFilterId]);

  function handleTabChange(tab: TabKey) {
    setTabParam(tab);
    window.scrollTo(0, 0);
  }

  function handleRouteFilterChange(routeId: number | null) {
    setRouteParam(routeId != null ? String(routeId) : null);
  }

  const routeFilter = data?.routes.find((r) => r.id === routeFilterId) ?? null;
  const elasticityData = routeFilterId != null ? (routeElasticity ?? []) : (data?.elasticity ?? []);
  const routeLookup = useMemo(() => buildRouteLookup(data?.routes ?? []), [data?.routes]);

  // Signing in replaces the whole view rather than overlaying it: it is a
  // deliberate act, not a filter tweak. Already-signed-in visitors never see
  // it, so a stale ?signin=1 in a shared link just lands on the dashboard.
  if (signinParam != null && user == null) {
    return (
      <LoginPage onSignedIn={handleSignedIn} onDismiss={handleDismissSignIn} reason={signinReason} />
    );
  }

  return (
    <div className="min-h-screen bg-page">
      <div className="sticky top-0 z-20 border-b border-border bg-surface">
        <Header
          onRefresh={load}
          refreshing={refreshing}
          signIn={
            <AccountControl
              user={user}
              onRequestSignIn={handleRequestSignIn}
              onSignOut={handleSignedOut}
            />
          }
        />
        {data && <TabNav active={activeTab} onChange={handleTabChange} role={user?.role ?? null} />}
      </div>

      <main className="max-w-[1800px] mx-auto px-6 py-5 flex flex-col gap-4">
        {!data && error && <ErrorState message={error} onRetry={load} />}
        {!data && !error && <LoadingSkeleton />}

        {data && (
          <div className={refreshing ? "opacity-60 transition-opacity" : "transition-opacity"}>
            {error && (
              <div className="rounded-xl border border-border bg-warning/10 text-ink text-sm p-3 mb-4">
                Couldn't refresh just now ({error}) — showing the last data we had.
              </div>
            )}

            <div className="mb-4">
              <PageSummary daily={data.daily} />
            </div>

            <TabPanel tabKey="overview" active={activeTab}>
              <HeroStat daily={data.daily} backtest={data.backtest} />
              <CpiDivergence data={data.cpiDivergence} />
              <KpiCards backtest={data.backtest} coverage={data.coverage} />
              <TrendChart data={data.daily} />
              <CarrierIndexChart data={data.byCarrierIndex} />
              <CarrierFinancialContext data={financialContext} />
              <NewsFeed news={news} loading={newsLoading} />
              <Footer backtest={data.backtest} coverage={data.coverage} />
            </TabPanel>

            <TabPanel tabKey="trip" active={activeTab}>
              <DateWatch routes={data.routes} />
            </TabPanel>

            <TabPanel tabKey="festivals" active={activeTab}>
              <SpikeWatch calendar={data.spikeWatch.calendar} routeLookup={routeLookup} />
            </TabPanel>

            <TabPanel tabKey="routes" active={activeTab}>
              <RouteFilter routes={data.routes} value={routeFilterId} onChange={handleRouteFilterChange} />
              <BookingAdvice advice={bookingAdvice} route={routeFilter} loading={routeDataLoading} />
              <PriceHistory data={priceHistory} route={routeFilter} loading={routeDataLoading} />
              <SectorHeatmap cells={data.priceGrid.cells} routeFilter={routeFilter} routeLookup={routeLookup} />
              <ElasticityChart data={elasticityData} routeFilter={routeFilter} />
              <FaresTable rows={data.fares} routeFilter={routeFilter} routeLookup={routeLookup} />
            </TabPanel>

            <TabPanel tabKey="affordability" active={activeTab}>
              <Affordability data={data.affordability} />
            </TabPanel>

            <TabPanel tabKey="report" active={activeTab}>
              <CitizenReportForm
                count={reportCount}
                signedIn={user != null}
                onRequestSignIn={handleRequestSignIn}
                onSubmitted={() => {
                  loadReportCount();
                  loadMyReports();
                }}
              />
              <MyReports reports={myReports} />
            </TabPanel>

            <TabPanel tabKey="airline" active={activeTab}>
              <AirlineDashboard
                overview={operatorOverview}
                flags={operatorFlags}
                fares={operatorFares}
                routeLookup={routeLookup}
                loading={operatorLoading}
                onResponded={loadOperatorData}
              />
            </TabPanel>

            <TabPanel tabKey="regulator" active={activeTab}>
              <section className="card-shadow rounded-2xl border border-border bg-surface p-5">
                <h2 className="text-[15px] font-semibold text-ink">Regulator view</h2>
                <p className="text-sm text-ink-secondary mt-0.5 max-w-3xl leading-relaxed">
                  Monitoring and evidence, not enforcement. This view flags real fares that ran unusually high
                  against their own history and assembles the real, dated context behind them. It issues nothing
                  and sends nothing to any airline — any action is a human's decision, taken through official
                  channels.
                </p>
                <p className="text-sm text-ink-muted mt-2 max-w-3xl leading-relaxed">
                  Not public. A flag names a carrier, a route and a date, and however carefully it is labelled
                  as a statistical observation it would be read as an accusation — so it stays on this desk.
                  The named carrier can see and answer its own flags, which is due process rather than
                  disclosure.
                </p>
              </section>

              <RegulatorFlags flags={flags} loading={flagsLoading} onReviewed={loadRegulatorData} />

              <CitizenReports reports={citizenReports} onReviewed={loadRegulatorData} />
            </TabPanel>

            <TabPanel tabKey="sources" active={activeTab}>
              <DataSources rows={data.compliance} />
            </TabPanel>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
