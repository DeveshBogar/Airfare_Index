import { useEffect, useMemo, useState, type ReactNode } from "react";
import { buildRouteLookup } from "./bookingLink";
import {
  api,
  type AffordabilityReport,
  type BacktestReport,
  type BookingAdvice as BookingAdviceData,
  type ByCarrierIndex,
  type CarrierFinancialContext as CarrierFinancialContextData,
  type ComplianceStatus,
  type CoverageReport,
  type CpiDivergence as CpiDivergenceData,
  type ElasticityPoint,
  type FareQuote,
  type IndexDailyPoint,
  type News,
  type PriceGrid,
  type RouteOut,
  type RoutePriceHistory,
  type SpikeWatch as SpikeWatchData,
} from "./api";
import { Affordability } from "./components/Affordability";
import { BookingAdvice } from "./components/BookingAdvice";
import { CarrierFinancialContext } from "./components/CarrierFinancialContext";
import { CarrierIndexChart } from "./components/CarrierIndexChart";
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
import { NewsFeed } from "./components/NewsFeed";
import { PageSummary } from "./components/PageSummary";
import { PriceHistory } from "./components/PriceHistory";
import { RouteFilter } from "./components/RouteFilter";
import { SectorHeatmap } from "./components/SectorHeatmap";
import { SpikeWatch } from "./components/SpikeWatch";
import { TAB_KEYS, TabNav, type TabKey } from "./components/TabNav";
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
  const activeTab: TabKey = isTabKey(tabParam) ? tabParam : "overview";
  const [routeParam, setRouteParam] = useUrlState("route", null);
  const routeFilterId = routeParam != null && routeParam !== "" ? Number(routeParam) : null;
  const [routeElasticity, setRouteElasticity] = useState<ElasticityPoint[] | null>(null);
  const [bookingAdvice, setBookingAdvice] = useState<BookingAdviceData | null>(null);
  const [priceHistory, setPriceHistory] = useState<RoutePriceHistory | null>(null);
  const [routeDataLoading, setRouteDataLoading] = useState(false);
  const [news, setNews] = useState<News | null>(null);
  const [newsLoading, setNewsLoading] = useState(true);
  const [financialContext, setFinancialContext] = useState<CarrierFinancialContextData[] | null>(null);

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

  return (
    <div className="min-h-screen bg-page">
      <div className="sticky top-0 z-20 border-b border-border bg-surface">
        <Header onRefresh={load} refreshing={refreshing} />
        {data && <TabNav active={activeTab} onChange={handleTabChange} />}
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
